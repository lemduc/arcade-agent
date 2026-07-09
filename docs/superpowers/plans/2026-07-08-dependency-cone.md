# dependency_cone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `dependency_cone` tool that, given an entity FQN or file path, returns its upstream and/or downstream dependency cone with depth control, on top of a shared cycle-safe traversal helper that `diff_impact` is refactored to reuse.

**Architecture:** A new pure module `algorithms/traversal.py` provides `adjacency_with_relations` (build forward/reverse adjacency with edge relations) and `walk_cone` (multi-source BFS with distance, first-hop relation, cycle-safety, and optional `max_nodes` cap). `diff_impact` is refactored to obtain its downstream dependents from these helpers (behavior identical; its tests are the regression guard). `tools/dependency_cone.py` resolves the seed (entity or file, reusing `diff_impact._paths_match`), walks the requested direction(s), and rolls reached entities up into compact per-direction blocks. An MCP wrapper mirrors the existing tool wrappers.

**Tech Stack:** Python 3.12+, pytest, ruff, the `@tool` registry, `mcp` (FastMCP) for the adapter.

## Global Constraints

- Python 3.12+ — PEP 585 builtin generics (`list[str]`, `dict[str, X]`, `str | None`).
- Type hints on every function param and return; Google-style docstrings (Args/Returns).
- Never read a visibility/public field off `Entity` — it does not exist. Cone membership is purely structural (edges).
- `Entity` fields available: `fqn, name, package, file_path, kind, language, imports, superclass, interfaces, properties`. `Edge` fields: `source, target, relation`. `DependencyGraph`: `entities: dict[fqn, Entity]`, `edges: list[Edge]`, `packages`, `.to_adjacency()`.
- Run tests with `/home/lemduc/personal_workspace/arcade-agent/.venv/bin/python -m pytest`. Lint with `.venv/bin/ruff check`.
- Work on the `feat/agent-context-tools` branch (stacked on PR #12). Do not touch any file outside those listed per task.
- Only create/modify NEW files plus the two shared files explicitly named (`tools/diff_impact.py`, `tools/adapters/mcp.py`). No unrelated refactoring.
- Commit messages: conventional-commit style, footer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

## File Structure

- Create: `src/arcade_agent/algorithms/traversal.py` — `adjacency_with_relations`, `walk_cone` (pure graph helpers, no tool/registry deps).
- Create: `tests/test_traversal.py` — unit tests for the helpers.
- Modify: `src/arcade_agent/tools/diff_impact.py` — replace inline reverse-BFS (lines ~111–144) with helper calls.
- Create: `src/arcade_agent/tools/dependency_cone.py` — the `@tool`.
- Create: `tests/test_dependency_cone.py` — tool tests.
- Modify: `src/arcade_agent/tools/adapters/mcp.py` — add the `dependency_cone` MCP wrapper.

---

## Task 1: Shared traversal helper (`algorithms/traversal.py`)

**Files:**
- Create: `src/arcade_agent/algorithms/traversal.py`
- Test: `tests/test_traversal.py`

**Interfaces:**
- Produces:
  - `adjacency_with_relations(graph: DependencyGraph, *, reverse: bool = False) -> dict[str, list[tuple[str, str]]]` — maps a node FQN to `[(neighbor_fqn, relation), ...]`. Forward (`reverse=False`): `source -> [(target, rel)]`. Reverse (`reverse=True`): `target -> [(source, rel)]`.
  - `walk_cone(adjacency: dict[str, list[tuple[str, str]]], seeds: Iterable[str], max_depth: int, max_nodes: int | None = None, valid_nodes: set[str] | None = None) -> tuple[list[dict], bool]` — multi-source BFS. Returns `(nodes, truncated)`; each node is `{"fqn": str, "distance": int, "via_relation": str}`, sorted by `(distance, fqn)`. `visited` is pre-seeded with `seeds` (seeds excluded, cycles safe). A neighbor is recorded only if `valid_nodes` is `None` or it is in `valid_nodes`, but the walk still traverses through non-recorded neighbors. `max_nodes` keeps the closest nodes and sets `truncated=True` if any are dropped.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_traversal.py`:

```python
"""Tests for the shared graph traversal helpers."""

from arcade_agent.algorithms.traversal import adjacency_with_relations, walk_cone


def test_adjacency_forward(sample_graph):
    adj = adjacency_with_relations(sample_graph, reverse=False)
    # Calculator imports MathHelper (source -> target)
    assert ("com.example.util.MathHelper", "import") in adj["com.example.calc.Calculator"]


def test_adjacency_reverse(sample_graph):
    adj = adjacency_with_relations(sample_graph, reverse=True)
    # MathHelper is imported by both calculators (target -> source)
    sources = {src for src, _rel in adj["com.example.util.MathHelper"]}
    assert sources == {
        "com.example.calc.Calculator",
        "com.example.calc.AdvancedCalculator",
    }


def test_walk_cone_records_distance_and_first_relation():
    adjacency = {"a": [("b", "import")], "b": [("c", "calls")]}
    nodes, truncated = walk_cone(adjacency, ["a"], max_depth=3)
    by_fqn = {n["fqn"]: n for n in nodes}
    assert by_fqn["b"]["distance"] == 1
    assert by_fqn["b"]["via_relation"] == "import"
    # c is reached at depth 2 but carries the FIRST hop's relation
    assert by_fqn["c"]["distance"] == 2
    assert by_fqn["c"]["via_relation"] == "import"
    assert truncated is False


def test_walk_cone_excludes_seeds():
    adjacency = {"a": [("b", "import")]}
    nodes, _ = walk_cone(adjacency, ["a"], max_depth=3)
    assert all(n["fqn"] != "a" for n in nodes)


def test_walk_cone_respects_max_depth():
    adjacency = {"a": [("b", "import")], "b": [("c", "calls")]}
    nodes, _ = walk_cone(adjacency, ["a"], max_depth=1)
    assert {n["fqn"] for n in nodes} == {"b"}


def test_walk_cone_is_cycle_safe():
    adjacency = {"a": [("b", "calls")], "b": [("a", "calls")]}
    nodes, _ = walk_cone(adjacency, ["a"], max_depth=10)
    # Terminates, and does not re-report the seed
    assert {n["fqn"] for n in nodes} == {"b"}


def test_walk_cone_valid_nodes_filters_records_but_still_traverses():
    adjacency = {"a": [("ext", "import")], "ext": [("c", "calls")]}
    nodes, _ = walk_cone(
        adjacency, ["a"], max_depth=3, valid_nodes={"a", "c"}
    )
    fqns = {n["fqn"] for n in nodes}
    # "ext" is traversed (so c is reachable) but not recorded
    assert "ext" not in fqns
    assert "c" in fqns
    assert nodes[[n["fqn"] for n in nodes].index("c")]["distance"] == 2


def test_walk_cone_max_nodes_truncates_closest_first():
    adjacency = {"a": [("b", "r"), ("c", "r")], "b": [("d", "r")]}
    nodes, truncated = walk_cone(adjacency, ["a"], max_depth=3, max_nodes=2)
    assert truncated is True
    assert len(nodes) == 2
    # closest (distance 1) kept before the distance-2 node
    assert {n["fqn"] for n in nodes} == {"b", "c"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_traversal.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'arcade_agent.algorithms.traversal'`.

- [ ] **Step 3: Write the implementation**

Create `src/arcade_agent/algorithms/traversal.py`:

```python
"""Cycle-safe dependency-graph traversal helpers.

Pure functions shared by ``diff_impact`` and ``dependency_cone``. They operate
on a plain adjacency mapping so they carry no dependency on the tool registry.
"""

from collections import deque
from collections.abc import Iterable

from arcade_agent.parsers.graph import DependencyGraph


def adjacency_with_relations(
    graph: DependencyGraph, *, reverse: bool = False
) -> dict[str, list[tuple[str, str]]]:
    """Build an adjacency map that preserves edge relations.

    Args:
        graph: Dependency graph to read edges from.
        reverse: When False, map ``source -> [(target, relation)]`` (forward
            dependencies). When True, map ``target -> [(source, relation)]``
            (reverse dependencies — who depends on a node).

    Returns:
        Mapping of node FQN to a list of ``(neighbor_fqn, relation)`` pairs.
    """
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge in graph.edges:
        if reverse:
            adjacency.setdefault(edge.target, []).append((edge.source, edge.relation))
        else:
            adjacency.setdefault(edge.source, []).append((edge.target, edge.relation))
    return adjacency


def walk_cone(
    adjacency: dict[str, list[tuple[str, str]]],
    seeds: Iterable[str],
    max_depth: int,
    max_nodes: int | None = None,
    valid_nodes: set[str] | None = None,
) -> tuple[list[dict], bool]:
    """Breadth-first walk of a cone from ``seeds`` over ``adjacency``.

    A ``visited`` set pre-seeded with ``seeds`` both excludes the seeds from the
    result and makes the walk cycle-safe. Each reached node records the number
    of hops from the nearest seed (``distance``, 1 = direct) and the relation of
    the *first* hop taken to reach it (``via_relation``).

    Args:
        adjacency: Node FQN -> list of ``(neighbor_fqn, relation)`` pairs.
        seeds: Starting node FQNs (distance 0, never reported).
        max_depth: Maximum hops to walk (1 = direct neighbors only).
        max_nodes: Optional cap; the closest nodes are kept and ``truncated`` is
            set when any are dropped.
        valid_nodes: When given, only neighbors in this set are recorded, though
            the walk still traverses through non-recorded neighbors.

    Returns:
        ``(nodes, truncated)`` where ``nodes`` is a list of
        ``{"fqn", "distance", "via_relation"}`` sorted by ``(distance, fqn)``.
    """
    seed_list = list(seeds)
    visited: set[str] = set(seed_list)
    reached: dict[str, dict] = {}
    queue: deque[tuple[str, int, str | None]] = deque(
        (s, 0, None) for s in seed_list
    )

    while queue:
        node, dist, first_rel = queue.popleft()
        if dist >= max_depth:
            continue
        for neighbor, relation in adjacency.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            hop_rel = relation if first_rel is None else first_rel
            if valid_nodes is None or neighbor in valid_nodes:
                reached[neighbor] = {
                    "fqn": neighbor,
                    "distance": dist + 1,
                    "via_relation": hop_rel,
                }
            queue.append((neighbor, dist + 1, hop_rel))

    nodes = sorted(reached.values(), key=lambda d: (d["distance"], d["fqn"]))
    truncated = False
    if max_nodes is not None and len(nodes) > max_nodes:
        nodes = nodes[:max_nodes]
        truncated = True
    return nodes, truncated
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_traversal.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check src/arcade_agent/algorithms/traversal.py tests/test_traversal.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/arcade_agent/algorithms/traversal.py tests/test_traversal.py
git commit -m "feat: add shared cycle-safe graph traversal helper

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Refactor `diff_impact` onto the shared helper

**Files:**
- Modify: `src/arcade_agent/tools/diff_impact.py` (imports; replace the reverse-BFS block, lines ~111–144)
- Test: `tests/test_diff_impact.py` (existing — regression guard, unchanged)

**Interfaces:**
- Consumes: `adjacency_with_relations`, `walk_cone` from Task 1.
- Produces: no signature change. `diff_impact` still returns the same dict; `downstream_dependents` remains a list of `{"fqn", "distance", "via_relation"}` sorted by `(distance, fqn)`.

- [ ] **Step 1: Run the existing diff_impact tests (green baseline)**

Run: `.venv/bin/python -m pytest tests/test_diff_impact.py -q`
Expected: PASS (baseline before refactor).

- [ ] **Step 2: Add the import**

In `src/arcade_agent/tools/diff_impact.py`, the top imports currently are:

```python
from collections import deque

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool
```

Replace them with (drop the now-unused `deque`, add the helper import):

```python
from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.traversal import adjacency_with_relations, walk_cone
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool
```

- [ ] **Step 3: Replace the inline reverse-BFS block**

Find this block (section 3, roughly lines 111–144):

```python
    # -- 3. Downstream dependents (reverse-dependency closure) ----------------
    # Reverse adjacency: target -> list of (source, relation) that depend on it.
    reverse_adj: dict[str, list[tuple[str, str]]] = {}
    for edge in dep_graph.edges:
        reverse_adj.setdefault(edge.target, []).append((edge.source, edge.relation))

    # Multi-source BFS seeded at all changed entities (distance 0). A visited
    # set pre-loaded with the changed set both prevents cycles from looping and
    # excludes changed entities from the results.
    visited: set[str] = set(changed_fqns)
    downstream: dict[str, dict] = {}
    queue: deque[tuple[str, int, str | None]] = deque(
        (fqn, 0, None) for fqn in changed_fqns
    )
    while queue:
        node, dist, first_rel = queue.popleft()
        if dist >= max_depth:
            continue
        for src, rel in reverse_adj.get(node, []):
            if src in visited:
                continue
            visited.add(src)
            hop_rel = rel if first_rel is None else first_rel
            if src in dep_graph.entities:
                downstream[src] = {
                    "fqn": src,
                    "distance": dist + 1,
                    "via_relation": hop_rel,
                }
            queue.append((src, dist + 1, hop_rel))

    downstream_dependents = sorted(
        downstream.values(), key=lambda d: (d["distance"], d["fqn"])
    )
```

Replace it with:

```python
    # -- 3. Downstream dependents (reverse-dependency closure) ----------------
    # Walk reverse edges from the changed entities: who transitively depends on
    # them. valid_nodes restricts results to real graph entities (external edge
    # sources are traversed but not reported).
    reverse_adj = adjacency_with_relations(dep_graph, reverse=True)
    downstream_dependents, _ = walk_cone(
        reverse_adj,
        changed_fqns,
        max_depth,
        valid_nodes=set(dep_graph.entities),
    )
```

- [ ] **Step 4: Run the diff_impact tests to verify unchanged behavior**

Run: `.venv/bin/python -m pytest tests/test_diff_impact.py -q`
Expected: PASS — same results as the Step 1 baseline.

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check src/arcade_agent/tools/diff_impact.py`
Expected: `All checks passed!` (confirms no unused `deque` import remains).

- [ ] **Step 6: Commit**

```bash
git add src/arcade_agent/tools/diff_impact.py
git commit -m "refactor: use shared traversal helper in diff_impact

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `dependency_cone` tool (`tools/dependency_cone.py`)

**Files:**
- Create: `src/arcade_agent/tools/dependency_cone.py`
- Test: `tests/test_dependency_cone.py`

**Interfaces:**
- Consumes: `adjacency_with_relations`, `walk_cone` (Task 1); `_paths_match` from `arcade_agent.tools.diff_impact`.
- Produces: `dependency_cone(dep_graph: DependencyGraph, target: str, direction: str = "both", max_depth: int = 3, max_nodes: int | None = None) -> dict`. Output keys per the spec: `target`, `matched_by` (`"entity"`/`"file"`/`None`), `seed_entities`, `direction`, `max_depth`, and `upstream`/`downstream` blocks `{num_nodes, truncated, nodes, files}`; unresolved target returns a `note`; invalid direction returns an `error` + `valid_directions`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dependency_cone.py`:

```python
"""Tests for the dependency_cone tool."""

from arcade_agent.tools.dependency_cone import dependency_cone


def test_downstream_from_entity(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.util.MathHelper", direction="downstream"
    )
    assert result["matched_by"] == "entity"
    assert "upstream" not in result
    fqns = {n["fqn"] for n in result["downstream"]["nodes"]}
    assert fqns == {
        "com.example.calc.Calculator",
        "com.example.calc.AdvancedCalculator",
    }
    assert all(n["distance"] == 1 for n in result["downstream"]["nodes"])


def test_upstream_from_entity(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.calc.Calculator", direction="upstream"
    )
    assert "downstream" not in result
    fqns = {n["fqn"] for n in result["upstream"]["nodes"]}
    assert fqns == {"com.example.util.MathHelper"}


def test_both_directions(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.calc.Calculator", direction="both"
    )
    assert "upstream" in result and "downstream" in result
    # Calculator depends on MathHelper; AdvancedCalculator depends on Calculator
    assert {n["fqn"] for n in result["upstream"]["nodes"]} == {
        "com.example.util.MathHelper"
    }
    assert {n["fqn"] for n in result["downstream"]["nodes"]} == {
        "com.example.calc.AdvancedCalculator"
    }


def test_file_seed_resolves_all_entities_in_file(sample_graph):
    result = dependency_cone(
        sample_graph, "MathHelper.java", direction="downstream"
    )
    assert result["matched_by"] == "file"
    assert result["seed_entities"] == ["com.example.util.MathHelper"]
    assert result["downstream"]["num_nodes"] == 2


def test_files_rollup(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.util.MathHelper", direction="downstream"
    )
    assert result["downstream"]["files"] == [
        "AdvancedCalculator.java",
        "Calculator.java",
    ]


def test_max_depth_bounds_walk(sample_graph):
    # From MathHelper downstream: Calculator (d1) and AdvancedCalculator (d1);
    # AdvancedCalculator also reaches via Calculator at d2 but is already d1.
    result = dependency_cone(
        sample_graph, "com.example.util.MathHelper",
        direction="downstream", max_depth=1,
    )
    assert result["downstream"]["num_nodes"] == 2


def test_cycle_is_safe(sample_graph):
    # AdvancedCalculator -> Calculator and both -> MathHelper; ensure finite.
    result = dependency_cone(
        sample_graph, "com.example.calc.Calculator", direction="both", max_depth=10
    )
    assert isinstance(result["downstream"]["num_nodes"], int)


def test_max_nodes_truncates(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.util.MathHelper",
        direction="downstream", max_nodes=1,
    )
    assert result["downstream"]["truncated"] is True
    assert result["downstream"]["num_nodes"] == 1


def test_unresolved_target(sample_graph):
    result = dependency_cone(sample_graph, "does/not/exist.py")
    assert result["matched_by"] is None
    assert result["seed_entities"] == []
    assert "note" in result


def test_invalid_direction(sample_graph):
    result = dependency_cone(
        sample_graph, "com.example.calc.Calculator", direction="sideways"
    )
    assert "error" in result
    assert "both" in result["valid_directions"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dependency_cone.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'arcade_agent.tools.dependency_cone'`.

- [ ] **Step 3: Write the implementation**

Create `src/arcade_agent/tools/dependency_cone.py`:

```python
"""Tool: Compute the upstream/downstream dependency cone of an entity or file."""

from arcade_agent.algorithms.traversal import adjacency_with_relations, walk_cone
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.diff_impact import _paths_match
from arcade_agent.tools.registry import tool

_VALID_DIRECTIONS = ("upstream", "downstream", "both")


def _resolve_seeds(
    dep_graph: DependencyGraph, target: str
) -> tuple[set[str], str | None]:
    """Resolve a target (entity FQN or file path) to seed entity FQNs.

    Args:
        dep_graph: Dependency graph to resolve against.
        target: An entity FQN or a file path.

    Returns:
        ``(seeds, matched_by)`` where ``matched_by`` is ``"entity"``, ``"file"``,
        or ``None`` when nothing matched.
    """
    if target in dep_graph.entities:
        return {target}, "entity"
    seeds = {
        fqn
        for fqn, entity in dep_graph.entities.items()
        if _paths_match(entity.file_path, target)
    }
    if seeds:
        return seeds, "file"
    return set(), None


def _cone_block(
    dep_graph: DependencyGraph,
    adjacency: dict[str, list[tuple[str, str]]],
    seeds: set[str],
    max_depth: int,
    max_nodes: int | None,
) -> dict:
    """Walk one direction and roll reached entities up into a summary block.

    Args:
        dep_graph: Dependency graph (for the file rollup).
        adjacency: Forward or reverse adjacency to walk.
        seeds: Seed FQNs.
        max_depth: Maximum hops.
        max_nodes: Optional per-direction cap.

    Returns:
        Dict with ``num_nodes``, ``truncated``, ``nodes``, and ``files``.
    """
    nodes, truncated = walk_cone(
        adjacency,
        seeds,
        max_depth,
        max_nodes=max_nodes,
        valid_nodes=set(dep_graph.entities),
    )
    files = sorted(
        {dep_graph.entities[n["fqn"]].file_path for n in nodes}
    )
    return {
        "num_nodes": len(nodes),
        "truncated": truncated,
        "nodes": nodes,
        "files": files,
    }


@tool(
    name="dependency_cone",
    description="Return the upstream (what it depends on) and/or downstream "
    "(what depends on it) dependency cone of an entity or file, with depth "
    "control — the reachability view behind impact and comprehension questions.",
)
def dependency_cone(
    dep_graph: DependencyGraph,
    target: str,
    direction: str = "both",
    max_depth: int = 3,
    max_nodes: int | None = None,
) -> dict:
    """Compute the dependency cone of an entity or file.

    Args:
        dep_graph: Dependency graph to traverse.
        target: An entity FQN or a file path to seed the cone from.
        direction: ``"upstream"`` (what the seed depends on), ``"downstream"``
            (what depends on the seed), or ``"both"``.
        max_depth: Maximum hops to walk from the seed (1 = direct neighbors).
        max_nodes: Optional per-direction cap on returned nodes (closest kept).

    Returns:
        Dict with the resolved seeds and an ``upstream``/``downstream`` block for
        each requested direction; a clean empty result if nothing resolves, or an
        error dict for an invalid ``direction``.
    """
    if direction not in _VALID_DIRECTIONS:
        return {
            "target": target,
            "error": f"Invalid direction '{direction}'.",
            "valid_directions": list(_VALID_DIRECTIONS),
        }

    seeds, matched_by = _resolve_seeds(dep_graph, target)
    if not seeds:
        return {
            "target": target,
            "matched_by": None,
            "seed_entities": [],
            "direction": direction,
            "max_depth": max_depth,
            "note": f"No entity or file matched '{target}'.",
        }

    result: dict = {
        "target": target,
        "matched_by": matched_by,
        "seed_entities": sorted(seeds),
        "direction": direction,
        "max_depth": max_depth,
    }

    if direction in ("upstream", "both"):
        forward = adjacency_with_relations(dep_graph, reverse=False)
        result["upstream"] = _cone_block(
            dep_graph, forward, seeds, max_depth, max_nodes
        )

    if direction in ("downstream", "both"):
        reverse = adjacency_with_relations(dep_graph, reverse=True)
        result["downstream"] = _cone_block(
            dep_graph, reverse, seeds, max_depth, max_nodes
        )

    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dependency_cone.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Lint**

Run: `.venv/bin/ruff check src/arcade_agent/tools/dependency_cone.py tests/test_dependency_cone.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/arcade_agent/tools/dependency_cone.py tests/test_dependency_cone.py
git commit -m "feat: add dependency_cone tool (#13)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: MCP wrapper + full gate

**Files:**
- Modify: `src/arcade_agent/tools/adapters/mcp.py` (add the wrapper before `get_full_result`)
- Test: full suite + ruff

**Interfaces:**
- Consumes: `dependency_cone` (Task 3); the module's `_resolve`, `serialize_result`, `_apply_budget` helpers.
- Produces: an MCP `dependency_cone` tool exposed by the FastMCP server.

- [ ] **Step 1: Add the wrapper**

In `src/arcade_agent/tools/adapters/mcp.py`, locate the marker:

```python
    # -- get_full_result -------------------------------------------------------

    @server.tool()
    def get_full_result(
```

Insert immediately BEFORE that block:

```python
    # -- dependency_cone -------------------------------------------------------

    @server.tool()
    def dependency_cone(
        dep_graph: str,
        target: str,
        direction: str = "both",
        max_depth: int = 3,
        max_nodes: int | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return the upstream/downstream dependency cone of an entity or file.

        Args:
            dep_graph: Session ID from a previous 'parse' call.
            target: An entity FQN or a file path to seed the cone from.
            direction: "upstream", "downstream", or "both".
            max_depth: Maximum hops to walk (1 = direct neighbors).
            max_nodes: Optional per-direction cap on returned nodes.
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.dependency_cone import (
            dependency_cone as _dependency_cone,
        )

        graph_obj = _resolve(dep_graph, "DependencyGraph")
        result = _dependency_cone(
            dep_graph=graph_obj,
            target=target,
            direction=direction,
            max_depth=max_depth,
            max_nodes=max_nodes,
        )
        serialized = serialize_result(result)
        return json.dumps(_apply_budget(serialized, max_tokens), indent=2)
```

- [ ] **Step 2: Verify the tool registers and the server exposes it**

Run:

```bash
.venv/bin/python -c "
import arcade_agent.tools.dependency_cone
from arcade_agent import list_tools
assert 'dependency_cone' in {t.name for t in list_tools()}, 'not registered'
import asyncio
from arcade_agent.tools.adapters.mcp import get_server
names = {t.name for t in asyncio.run(get_server().list_tools())}
assert 'dependency_cone' in names, 'not exposed via MCP'
print('registered + exposed OK')
"
```

Expected: `registered + exposed OK`.

- [ ] **Step 3: Run the full suite (regression + new)**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — all prior tests plus the new `test_traversal.py` and `test_dependency_cone.py`.

- [ ] **Step 4: Lint the whole tree**

Run: `.venv/bin/ruff check src/ tests/`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add src/arcade_agent/tools/adapters/mcp.py
git commit -m "feat: expose dependency_cone via MCP adapter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Docs — mark roadmap #13 done

**Files:**
- Modify: `ROADMAP.md`
- Modify: `README.md` (tool table)

**Interfaces:** none (docs only).

- [ ] **Step 1: Update ROADMAP.md**

Change the `#13` line from:

```markdown
- [ ] **13. `dependency_cone` tool** — Given an entity/file, return full upstream/downstream dependency cone with depth control.
```

to:

```markdown
- [x] **13. `dependency_cone` tool** — Given an entity/file, return the upstream/downstream dependency cone with depth control and per-direction node caps. Shares the cycle-safe traversal helper with `diff_impact`.
```

Then in the priority table, move `13` out of the pending row into the Done row (Done becomes `1–9, 12, 13, 14, 15, 16a, 17`; the "Now" row keeps `10`).

- [ ] **Step 2: Update README.md tool table**

After the `diff_impact` row, add:

```markdown
| `dependency_cone` | Upstream/downstream dependency cone of an entity or file, with depth control |
```

- [ ] **Step 3: Commit**

```bash
git add ROADMAP.md README.md
git commit -m "docs: mark dependency_cone (#13) done

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Independent review

After Task 4 (or all tasks), dispatch one independent adversarial reviewer over
`algorithms/traversal.py`, `tools/dependency_cone.py`, the `diff_impact` refactor,
and both new test files. The reviewer verifies: (1) model fidelity — only real
`Entity`/`Edge` fields; (2) direction semantics are not inverted (downstream =
reverse edges = dependents; upstream = forward edges = dependencies); (3)
cycle-safety and `max_nodes` truncation behave as specified; (4) the
`diff_impact` refactor preserves behavior (its tests pass); (5) re-runs the full
suite and ruff. Address any high-severity findings before merge.

## Self-Review Notes

- **Spec coverage:** traversal helper (Task 1) ✓; `dependency_cone` signature +
  direction semantics + seed resolution + output shape + empty/invalid handling
  (Task 3) ✓; `diff_impact` refactor with tests as regression guard (Task 2) ✓;
  MCP wrapper (Task 4) ✓; testing list incl. cycle safety and truncation (Tasks
  1 & 3) ✓; independent review (final section) ✓; docs (Task 5) ✓.
- **Type consistency:** `walk_cone` returns `(list[dict], bool)` and is consumed
  as such in both `diff_impact` (Task 2) and `_cone_block` (Task 3);
  `adjacency_with_relations(..., reverse=Bool)` used identically in both;
  `_resolve_seeds -> (set[str], str | None)` matches its call site.
- **No placeholders:** every step contains full code or an exact command.
```
