# changelog_architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an architectural changelog between two versions of a codebase — components added/removed/renamed/split/merged, entities that changed component, smells gained/resolved, and metric deltas — and surface it in the CI pull-request comment.

**Architecture:** A new pure `algorithms/provenance.py` attributes every entity present in both versions to the `(source component, target component)` pair it moved between, then classifies components into disjoint structural buckets. `tools/compare.py`'s incorrect split/merge heuristic is replaced with this. A pure `changelog_architecture` tool composes structural changes with smell and metric deltas; `ingest` gains a `ref` parameter so callers can materialise two commits. A markdown exporter renders the result and `ci/arch_diff.py` prints it.

**Tech Stack:** Python 3.12+, dataclasses, pytest, ruff, mypy strict. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-07-28-changelog-architecture-design.md`
**Branch:** `feat/changelog-architecture` (already created, spec already committed)

## Global Constraints

- **Python 3.12+**, PEP 585 generics (`list[str]`, `str | None`). Never `typing.List`.
- **Type hints on every function**, including return types.
- **mypy:** the repo has **220 pre-existing strict-mode errors across 33 files** at the
  merge base (`b66ace4`) — `mypy src/` does **not** pass today and fixing that is out of
  scope. The binding requirement is: **the files you create or modify must be
  individually clean** (`mypy src/path/to/your_file.py` → "Success"), **and the
  tree-wide total must not rise above 220**. Check both.
- **`@dataclass` for domain objects.** Use `frozen=True` for the new value objects.
- **Google-style docstrings** with `Args:` / `Returns:` / `Raises:`.
- **Import order:** stdlib → third-party → local (`from arcade_agent.models.graph import ...`).
- **`ruff check src/ tests/`** must pass.
- **No new runtime dependencies.** Everything here uses the stdlib plus what is already installed.
- **Deterministic output.** Every list, tuple and dict in a returned structure is sorted by a stable key. No set iteration order may leak into output.
- **No LLM calls anywhere in this feature.**
- Run tests with `pytest` from the repo root with the venv active (`source .venv/bin/activate`).

### Import paths you will need (these are not where you would guess)

```python
from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool
```

`Architecture.membership()` returns `dict[str, str]` mapping entity FQN → component name, computed on demand. Use it; do not re-derive membership by hand.

---

### Task 1: `entity_flows` — attribute entity movement

**Files:**
- Create: `src/arcade_agent/algorithms/provenance.py`
- Test: `tests/test_algorithms/test_provenance.py`

**Interfaces:**
- Consumes: `Architecture`, `Component` from `arcade_agent.algorithms.architecture`.
- Produces: `Flow` (frozen dataclass with `source: str`, `target: str`, `entities: tuple[str, ...]`) and `entity_flows(arch_a: Architecture, arch_b: Architecture) -> tuple[Flow, ...]`. Tasks 2 and 5 depend on both names exactly as written.

- [ ] **Step 1: Write the failing test**

Create `tests/test_algorithms/test_provenance.py`:

```python
"""Tests for entity provenance between two architectures."""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.provenance import Flow, entity_flows


def _arch(**components: list[str]) -> Architecture:
    """Build an Architecture from name -> entity FQN list."""
    return Architecture(
        components=[
            Component(name=name, responsibility="", entities=list(entities))
            for name, entities in components.items()
        ],
        algorithm="test",
    )


def test_identical_architectures_produce_self_flows():
    arch = _arch(auth=["a.A", "a.B"])
    flows = entity_flows(arch, arch)
    assert flows == (Flow(source="auth", target="auth", entities=("a.A", "a.B")),)


def test_entity_moving_between_components_produces_cross_flow():
    arch_a = _arch(auth=["a.A", "a.B"], api=["x.X"])
    arch_b = _arch(auth=["a.A"], api=["x.X", "a.B"])
    flows = entity_flows(arch_a, arch_b)
    assert Flow(source="auth", target="api", entities=("a.B",)) in flows
    assert Flow(source="auth", target="auth", entities=("a.A",)) in flows


def test_entity_only_in_one_side_produces_no_flow():
    arch_a = _arch(auth=["a.A", "gone.G"])
    arch_b = _arch(auth=["a.A", "new.N"])
    flows = entity_flows(arch_a, arch_b)
    assert flows == (Flow(source="auth", target="auth", entities=("a.A",)),)


def test_flows_are_sorted_deterministically():
    arch_a = _arch(zeta=["z.Z"], alpha=["a.A"])
    arch_b = _arch(zeta=["z.Z"], alpha=["a.A"])
    flows = entity_flows(arch_a, arch_b)
    assert [f.source for f in flows] == ["alpha", "zeta"]


def test_empty_architectures_produce_no_flows():
    assert entity_flows(Architecture(), Architecture()) == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_algorithms/test_provenance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'arcade_agent.algorithms.provenance'`

- [ ] **Step 3: Write minimal implementation**

Create `src/arcade_agent/algorithms/provenance.py`:

```python
"""Entity provenance between two recovered architectures.

Answers "where did this component's entities come from", which is a
many-to-many question the 1:1 Hungarian matching in ``matching.py`` cannot
express. Used to classify splits and merges without double counting.
"""

from dataclasses import dataclass

from arcade_agent.algorithms.architecture import Architecture


@dataclass(frozen=True)
class Flow:
    """Entities that moved from one component to another between two versions.

    Attributes:
        source: Component name in the earlier architecture.
        target: Component name in the later architecture.
        entities: Sorted FQNs present in both architectures that took this path.
    """

    source: str
    target: str
    entities: tuple[str, ...]


def entity_flows(arch_a: Architecture, arch_b: Architecture) -> tuple[Flow, ...]:
    """Attribute every entity present in both architectures to a component pair.

    Entities present in only one architecture produce no flow: they are
    additions or deletions, not movements.

    Args:
        arch_a: The earlier architecture.
        arch_b: The later architecture.

    Returns:
        Flows sorted by (source, target), each with sorted entities.
    """
    membership_a = arch_a.membership()
    membership_b = arch_b.membership()

    buckets: dict[tuple[str, str], list[str]] = {}
    for fqn, source in membership_a.items():
        target = membership_b.get(fqn)
        if target is None:
            continue
        buckets.setdefault((source, target), []).append(fqn)

    return tuple(
        Flow(source=source, target=target, entities=tuple(sorted(entities)))
        for (source, target), entities in sorted(buckets.items())
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_algorithms/test_provenance.py -v`
Expected: 5 passed

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check src/ tests/ && mypy src/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/arcade_agent/algorithms/provenance.py tests/test_algorithms/test_provenance.py
git commit -m "feat(provenance): attribute entity movement between architectures"
```

---

### Task 2: `classify_structural_changes` — disjoint buckets with precedence

**Files:**
- Modify: `src/arcade_agent/algorithms/provenance.py`
- Test: `tests/test_algorithms/test_provenance.py` (append)

**Interfaces:**
- Consumes: `Flow`, `entity_flows` from Task 1.
- Produces: `Split`, `Merge`, `StructuralChanges` and
  `classify_structural_changes(arch_a, arch_b, *, min_entities: int = 3, min_share: float = 0.20) -> StructuralChanges`.
  `StructuralChanges` exposes `added`, `removed`, `renamed`, `split`, `merged`, `stable`, `flows`, `rename_map`.
  Tasks 3, 5 and 6 depend on these names exactly.

**The precedence rules are the whole point of this task.** Splits and merges outrank renames. A component of `arch_a` whose single significant outgoing flow lands on a merge target is *absorbed* and is reported only inside that merge. A component of `arch_b` whose single significant incoming flow comes from a split source is a *split product* and is reported only inside that split. Without these rules the same event is reported twice under two names — the exact defect this feature exists to fix.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_algorithms/test_provenance.py`:

```python
from arcade_agent.algorithms.provenance import (
    Merge,
    Split,
    classify_structural_changes,
)


def test_identity_is_all_stable():
    arch = _arch(auth=["a.A", "a.B", "a.C"])
    changes = classify_structural_changes(arch, arch)
    assert changes.stable == ("auth",)
    assert changes.added == ()
    assert changes.removed == ()
    assert changes.renamed == ()
    assert changes.split == ()
    assert changes.merged == ()


def test_pure_rename():
    arch_a = _arch(util=["u.A", "u.B", "u.C"])
    arch_b = _arch(common=["u.A", "u.B", "u.C"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.renamed == (("util", "common"),)
    assert changes.added == ()
    assert changes.removed == ()
    assert changes.rename_map == {"util": "common"}


def test_clean_split_does_not_also_report_an_addition():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.split == (
        Split(source="auth", targets=("auth", "authz"),
              entities={"auth": 3, "authz": 3}),
    )
    assert changes.added == ()
    assert changes.renamed == ()


def test_clean_merge_does_not_also_report_a_removal():
    arch_a = _arch(core=["c.A", "c.B", "c.C"], util=["u.X", "u.Y", "u.Z"])
    arch_b = _arch(core=["c.A", "c.B", "c.C", "u.X", "u.Y", "u.Z"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.merged == (
        Merge(target="core", sources=("core", "util"),
              entities={"core": 3, "util": 3}),
    )
    assert changes.removed == ()
    assert changes.renamed == ()


def test_precedence_absorbed_component_is_not_also_a_rename():
    # util's entities all land in core, and core also keeps its own -> merge.
    # util has exactly one outgoing flow, which would otherwise read as a rename.
    arch_a = _arch(core=["c.A", "c.B", "c.C"], util=["u.X", "u.Y", "u.Z"])
    arch_b = _arch(core=["c.A", "c.B", "c.C", "u.X", "u.Y", "u.Z"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.renamed == ()
    assert changes.stable == ()
    assert changes.removed == ()
    assert [m.target for m in changes.merged] == ["core"]


def test_precedence_split_product_is_not_also_an_addition_or_rename():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert "authz" not in changes.added
    assert changes.renamed == ()
    assert changes.split[0].targets == ("auth", "authz")


def test_split_and_merge_in_the_same_diff():
    arch_a = _arch(
        auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"],
        util=["u.1", "u.2", "u.3"],
        core=["c.1", "c.2", "c.3"],
    )
    arch_b = _arch(
        auth=["a.A", "a.B", "a.C"],
        authz=["z.X", "z.Y", "z.Z"],
        core=["c.1", "c.2", "c.3", "u.1", "u.2", "u.3"],
    )
    changes = classify_structural_changes(arch_a, arch_b)
    assert [s.source for s in changes.split] == ["auth"]
    assert [m.target for m in changes.merged] == ["core"]
    assert changes.added == ()
    assert changes.removed == ()


def test_sub_threshold_flow_is_not_a_split():
    # One entity leaves a large component: below min_entities=3 and below
    # 20% of min(9, 1)=1 ... share is 1/1 = 1.0, so raise min_share above it
    # by making the target large too.
    arch_a = _arch(
        big=["b.1", "b.2", "b.3", "b.4", "b.5", "b.6", "b.7", "b.8", "b.9"],
        other=["o.1", "o.2", "o.3", "o.4", "o.5"],
    )
    arch_b = _arch(
        big=["b.1", "b.2", "b.3", "b.4", "b.5", "b.6", "b.7", "b.8"],
        other=["o.1", "o.2", "o.3", "o.4", "o.5", "b.9"],
    )
    changes = classify_structural_changes(arch_a, arch_b, min_entities=3, min_share=0.5)
    assert changes.split == ()
    assert changes.stable == ("big", "other")


def test_component_with_no_significant_outflow_is_removed():
    arch_a = _arch(dead=["d.1", "d.2", "d.3"], keep=["k.1", "k.2", "k.3"])
    arch_b = _arch(keep=["k.1", "k.2", "k.3"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.removed == ("dead",)
    assert changes.stable == ("keep",)


def test_brand_new_component_is_added():
    arch_a = _arch(keep=["k.1", "k.2", "k.3"])
    arch_b = _arch(keep=["k.1", "k.2", "k.3"], fresh=["f.1", "f.2", "f.3"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.added == ("fresh",)


def test_both_sides_empty():
    changes = classify_structural_changes(Architecture(), Architecture())
    assert changes.added == ()
    assert changes.removed == ()
    assert changes.flows == ()


def test_invalid_min_share_raises():
    import pytest

    with pytest.raises(ValueError, match="min_share"):
        classify_structural_changes(Architecture(), Architecture(), min_share=0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_algorithms/test_provenance.py -v`
Expected: FAIL — `ImportError: cannot import name 'Split'`

- [ ] **Step 3: Write the implementation**

Append to `src/arcade_agent/algorithms/provenance.py`:

```python
@dataclass(frozen=True)
class Split:
    """One component of the earlier architecture scattered into several later ones.

    Attributes:
        source: Component name in the earlier architecture.
        targets: Sorted later component names that received its entities.
        entities: Target component name -> number of entities received.
    """

    source: str
    targets: tuple[str, ...]
    entities: dict[str, int]


@dataclass(frozen=True)
class Merge:
    """One component of the later architecture drawing from several earlier ones.

    Attributes:
        target: Component name in the later architecture.
        sources: Sorted earlier component names that contributed entities.
        entities: Source component name -> number of entities contributed.
    """

    target: str
    sources: tuple[str, ...]
    entities: dict[str, int]


@dataclass(frozen=True)
class StructuralChanges:
    """Disjoint classification of components across two architectures.

    Every component of the earlier architecture appears in exactly one of
    ``removed``, ``split``, a ``merged`` entry's ``sources``, ``renamed`` or
    ``stable``. Every component of the later architecture appears in exactly one
    of ``added``, ``merged``, a ``split`` entry's ``targets``, ``renamed`` or
    ``stable``.
    """

    added: tuple[str, ...]
    removed: tuple[str, ...]
    renamed: tuple[tuple[str, str], ...]
    split: tuple[Split, ...]
    merged: tuple[Merge, ...]
    stable: tuple[str, ...]
    flows: tuple[Flow, ...]
    rename_map: dict[str, str]


def classify_structural_changes(
    arch_a: Architecture,
    arch_b: Architecture,
    *,
    min_entities: int = 3,
    min_share: float = 0.20,
) -> StructuralChanges:
    """Classify components into disjoint structural buckets.

    A flow is significant when it carries at least *min_entities* entities, or
    at least *min_share* of the smaller of its two endpoint components measured
    at its own version. Splits and merges take precedence over renames so that
    no structural event is reported twice.

    Args:
        arch_a: The earlier architecture.
        arch_b: The later architecture.
        min_entities: Absolute entity count at which a flow becomes significant.
        min_share: Fractional threshold in (0, 1] as an alternative trigger.

    Returns:
        A StructuralChanges with every field sorted deterministically.

    Raises:
        ValueError: If *min_share* is outside (0, 1].
    """
    if not 0 < min_share <= 1:
        raise ValueError(f"min_share must be in (0, 1], got {min_share}")

    flows = entity_flows(arch_a, arch_b)
    size_a = {c.name: len(c.entities) for c in arch_a.components}
    size_b = {c.name: len(c.entities) for c in arch_b.components}

    def is_significant(flow: Flow) -> bool:
        count = len(flow.entities)
        if count >= min_entities:
            return True
        denominator = min(size_a.get(flow.source, 0), size_b.get(flow.target, 0))
        return denominator > 0 and count / denominator >= min_share

    outgoing: dict[str, list[Flow]] = {}
    incoming: dict[str, list[Flow]] = {}
    for flow in flows:
        if not is_significant(flow):
            continue
        outgoing.setdefault(flow.source, []).append(flow)
        incoming.setdefault(flow.target, []).append(flow)

    split_sources = {name for name, fs in outgoing.items() if len(fs) >= 2}
    merge_targets = {name for name, fs in incoming.items() if len(fs) >= 2}

    splits = tuple(
        Split(
            source=name,
            targets=tuple(sorted(f.target for f in outgoing[name])),
            entities={
                f.target: len(f.entities)
                for f in sorted(outgoing[name], key=lambda f: f.target)
            },
        )
        for name in sorted(split_sources)
    )
    merges = tuple(
        Merge(
            target=name,
            sources=tuple(sorted(f.source for f in incoming[name])),
            entities={
                f.source: len(f.entities)
                for f in sorted(incoming[name], key=lambda f: f.source)
            },
        )
        for name in sorted(merge_targets)
    )

    # Precedence: a lone flow into a merge target means the source was absorbed,
    # not renamed. It is reported inside the merge entry only.
    absorbed = {
        name
        for name, fs in outgoing.items()
        if name not in split_sources and fs[0].target in merge_targets
    }

    renamed: list[tuple[str, str]] = []
    stable: list[str] = []
    for name in sorted(outgoing):
        if name in split_sources or name in absorbed:
            continue
        target = outgoing[name][0].target
        # A lone flow out of a split source makes the target a split product,
        # already reported inside the split entry.
        if len(incoming.get(target, [])) != 1:
            continue
        if name == target:
            stable.append(name)
        else:
            renamed.append((name, target))

    removed = tuple(
        c.name for c in arch_a.components if not outgoing.get(c.name)
    )
    added = tuple(c.name for c in arch_b.components if not incoming.get(c.name))

    rename_map = {source: target for source, target in renamed}
    rename_map.update({name: name for name in stable})

    return StructuralChanges(
        added=tuple(sorted(added)),
        removed=tuple(sorted(removed)),
        renamed=tuple(renamed),
        split=splits,
        merged=merges,
        stable=tuple(stable),
        flows=flows,
        rename_map=rename_map,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_algorithms/test_provenance.py -v`
Expected: all passed (17 tests total including Task 1's)

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check src/ tests/ && mypy src/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/arcade_agent/algorithms/provenance.py tests/test_algorithms/test_provenance.py
git commit -m "feat(provenance): classify structural changes with split/merge precedence"
```

---

### Task 3: Correct `compare`'s split/merge classification

**Files:**
- Modify: `src/arcade_agent/tools/compare.py`
- Test: `tests/test_tools/test_compare.py` (create)

**Interfaces:**
- Consumes: `classify_structural_changes` from Task 2.
- Produces: `compare()` keeps `overall_similarity` and `matches` unchanged. `summary` loses `possible_splits` / `possible_merges` and gains `splits` / `merges` (both `int`). Task 7 depends on the new key names.

This is a deliberate behaviour change. The old keys were wrong: they labelled heavily-refactored renames as splits or merges depending on which way entity count moved, and reported genuine splits twice.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tools/test_compare.py`:

```python
"""Tests for the compare tool's structural classification."""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.tools.compare import compare


def _arch(**components: list[str]) -> Architecture:
    return Architecture(
        components=[
            Component(name=name, responsibility="", entities=list(entities))
            for name, entities in components.items()
        ],
        algorithm="test",
    )


def test_summary_uses_accurate_split_merge_keys():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    result = compare(arch_a, arch_b)
    assert result["summary"]["splits"] == 1
    assert result["summary"]["merges"] == 0
    assert "possible_splits" not in result["summary"]
    assert "possible_merges" not in result["summary"]


def test_split_is_not_double_counted_as_an_addition():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    result = compare(arch_a, arch_b)
    assert result["summary"]["components_added"] == 0


def test_refactored_rename_is_not_labelled_a_split():
    arch_a = _arch(util=["u.1", "u.2", "u.3", "u.4"])
    arch_b = _arch(common=["u.1", "u.2", "u.3", "u.4"])
    result = compare(arch_a, arch_b)
    assert result["summary"]["splits"] == 0
    assert result["summary"]["merges"] == 0


def test_similarity_and_matches_are_preserved():
    arch = _arch(auth=["a.A", "a.B"])
    result = compare(arch, arch)
    assert result["overall_similarity"] == 1.0
    assert isinstance(result["matches"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools/test_compare.py -v`
Expected: FAIL — `KeyError: 'splits'`

- [ ] **Step 3: Rewrite the classification**

Replace the whole body of `compare()` in `src/arcade_agent/tools/compare.py` below the docstring. Keep the `@tool` decorator and signature exactly as they are. New body:

```python
    matches = match_components(arch_a, arch_b)
    overall_similarity = compute_a2a_similarity(arch_a, arch_b)
    changes = classify_structural_changes(arch_a, arch_b)

    return {
        "overall_similarity": overall_similarity,
        "matches": matches,
        "summary": {
            "total_matches": len([m for m in matches if m["source"] and m["target"]]),
            "components_added": len(changes.added),
            "components_removed": len(changes.removed),
            "splits": len(changes.split),
            "merges": len(changes.merged),
            "arch_a_components": len(arch_a.components),
            "arch_b_components": len(arch_b.components),
        },
    }
```

Add the import at the top of the file:

```python
from arcade_agent.algorithms.provenance import classify_structural_changes
```

Update the `@tool` description string to: `"Compare two architectures (A2A analysis). Matches components using the Hungarian algorithm and classifies additions, removals, splits and merges by entity provenance."`

- [ ] **Step 4: Run the new tests**

Run: `pytest tests/test_tools/test_compare.py -v`
Expected: 4 passed

- [ ] **Step 5: Run the existing suite to find breakage**

Run: `pytest -v`
Expected: `tests/test_arch_diff.py` may FAIL on the removed `possible_splits` / `possible_merges` keys. That is expected — Task 7 fixes `arch_diff`. If `test_arch_diff.py` fails **only** with `KeyError: 'possible_splits'` or `KeyError: 'possible_merges'`, continue. Any other failure must be fixed now.

- [ ] **Step 6: Commit**

```bash
git add src/arcade_agent/tools/compare.py tests/test_tools/test_compare.py
git commit -m "fix(compare): classify splits and merges by entity provenance

match_components solves a 1:1 assignment problem and cannot represent a
split or merge. The previous similarity<0.5 heuristic mislabelled renames
and reported genuine splits twice. summary.possible_splits/possible_merges
are replaced by accurate splits/merges."
```

---

### Task 4: `ingest(ref=...)` — materialise a commit without touching the working tree

**Files:**
- Modify: `src/arcade_agent/tools/ingest.py`
- Test: `tests/test_tools/test_ingest_ref.py` (create)

**Interfaces:**
- Produces: `ingest(source, ..., ref: str | None = None)`. When `ref` is set, `IngestedRepo.version == ref` and `IngestedRepo.is_temp is True`. Task 8 depends on this.

Use `git archive` piped into `tar -x`, **not** `git checkout` and **not** `git worktree`. The caller's working tree must be untouched — this runs against repos people are actively working in.

- [ ] **Step 1: Write the failing test**

Create `tests/test_tools/test_ingest_ref.py`:

```python
"""Tests for ingesting a specific git ref."""

import subprocess
from pathlib import Path

import pytest

from arcade_agent.tools.ingest import ingest


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def two_tag_repo(tmp_path: Path) -> Path:
    """A git repo with v1 and v2 tags and different content at each."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("git", "init", "-q", cwd=repo)
    _run("git", "config", "user.email", "t@example.com", cwd=repo)
    _run("git", "config", "user.name", "Test", cwd=repo)

    (repo / "first.py").write_text("class First:\n    pass\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-q", "-m", "first", cwd=repo)
    _run("git", "tag", "v1", cwd=repo)

    (repo / "second.py").write_text("class Second:\n    pass\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-q", "-m", "second", cwd=repo)
    _run("git", "tag", "v2", cwd=repo)
    return repo


def test_ingest_at_ref_sees_only_that_refs_files(two_tag_repo: Path):
    repo = ingest(str(two_tag_repo), language="python", ref="v1")
    names = {p.name for p in repo.source_files}
    assert "first.py" in names
    assert "second.py" not in names
    repo.cleanup()


def test_ingest_at_ref_records_the_ref_as_version(two_tag_repo: Path):
    repo = ingest(str(two_tag_repo), language="python", ref="v1")
    assert repo.version == "v1"
    assert repo.is_temp is True
    repo.cleanup()


def test_ingest_at_ref_does_not_touch_the_working_tree(two_tag_repo: Path):
    before = (two_tag_repo / "second.py").read_text()
    repo = ingest(str(two_tag_repo), language="python", ref="v1")
    repo.cleanup()
    assert (two_tag_repo / "second.py").read_text() == before
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=two_tag_repo, capture_output=True, text=True, check=True,
    )
    assert status.stdout == ""


def test_unknown_ref_raises_with_available_tags(two_tag_repo: Path):
    with pytest.raises(ValueError, match="nope"):
        ingest(str(two_tag_repo), language="python", ref="nope")


def test_ref_on_non_git_directory_raises(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("x = 1\n")
    with pytest.raises(ValueError, match="not a git repository"):
        ingest(str(plain), language="python", ref="v1")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools/test_ingest_ref.py -v`
Expected: FAIL — `TypeError: ingest() got an unexpected keyword argument 'ref'`

- [ ] **Step 3: Add the helper**

Add to `src/arcade_agent/tools/ingest.py` (module level, after the existing private helpers):

```python
def _materialize_ref(repo_path: Path, ref: str) -> Path:
    """Extract a git ref into a fresh temp directory.

    Uses ``git archive`` so the caller's working tree, index and HEAD are
    untouched. The extracted tree has no ``.git`` directory, which is why the
    caller supplies the version rather than detecting it from tags.

    Args:
        repo_path: Path to a git repository.
        ref: A commit SHA, tag or branch name.

    Returns:
        Path to the extracted tree. Caller owns cleanup.

    Raises:
        ValueError: If *repo_path* is not a git repository, or *ref* is unknown.
    """
    import subprocess

    if not (repo_path / ".git").exists():
        raise ValueError(f"{repo_path} is not a git repository; cannot use ref={ref!r}")

    resolved = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--verify", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
    )
    if resolved.returncode != 0:
        tags = subprocess.run(
            ["git", "-C", str(repo_path), "tag", "--list"],
            capture_output=True,
            text=True,
        ).stdout.split()
        available = ", ".join(tags) if tags else "none"
        raise ValueError(f"Unknown ref {ref!r} in {repo_path}. Available tags: {available}")

    dest = Path(tempfile.mkdtemp(prefix="arcade_agent_ref_"))
    archive = subprocess.run(
        ["git", "-C", str(repo_path), "archive", ref],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["tar", "-x", "-C", str(dest)],
        input=archive.stdout,
        check=True,
        capture_output=True,
    )
    return dest
```

- [ ] **Step 4: Wire `ref` into `ingest`**

In `ingest()`, add `ref: str | None = None` as the final keyword parameter and document it in the docstring as:

```
        ref: Optional git commit, tag or branch to analyse instead of the
            working tree. Extracted to a temp directory; the caller's working
            tree is never modified.
```

At the very top of the function body, before the existing `source_path = Path(source)` line, insert:

```python
    if ref is not None:
        source_path = Path(source)
        if not source_path.is_dir():
            raise ValueError(f"ref={ref!r} requires a local repository path, got {source!r}")
        extracted = _materialize_ref(source_path, ref)
        repo = _ingest_local(
            extracted,
            language=language,
            languages=languages,
            exclude_tests=exclude_tests,
            source_root=Path(source_root) if source_root else None,
        )
        repo.version = ref
        repo.is_temp = True
        repo.path = extracted
        return repo
```

**Before writing this, read the existing local-ingest path in `ingest()` and use whatever the real internal function is called** — the file may name it differently from `_ingest_local`. Match the real signature; do not invent one. If the local path is inlined rather than factored into a helper, extract it into `_ingest_local` first as a behaviour-preserving refactor, run the full suite to confirm nothing broke, then use it here.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_tools/test_ingest_ref.py -v`
Expected: 5 passed

- [ ] **Step 6: Confirm nothing else broke**

Run: `pytest tests/test_tools/ -v && ruff check src/ tests/ && mypy src/`
Expected: no new failures beyond the known `test_arch_diff.py` keys from Task 3

- [ ] **Step 7: Commit**

```bash
git add src/arcade_agent/tools/ingest.py tests/test_tools/test_ingest_ref.py
git commit -m "feat(ingest): add ref parameter to analyse a commit or tag

Uses git archive into a temp dir so the caller's working tree, index and
HEAD are untouched."
```

---

### Task 5: The `changelog_architecture` tool

**Files:**
- Create: `src/arcade_agent/tools/changelog_architecture.py`
- Test: `tests/test_changelog_architecture.py`

**Interfaces:**
- Consumes: `classify_structural_changes`, `StructuralChanges` (Task 2); `detect_smells`, `compute_metrics`.
- Produces: `changelog_architecture(arch_a, graph_a, arch_b, graph_b, *, smells_a=None, smells_b=None, metrics_a=None, metrics_b=None, ref_a=None, ref_b=None, min_entities=3, min_share=0.20) -> dict`. Tasks 6, 7 and 8 consume the returned dict shape.

**Smell identity is the subtle part.** A smell is keyed by `(smell_type, sorted(affected_components))`. Component names from `arch_a` must be mapped through `changes.rename_map` before comparison — otherwise every renamed component manufactures a spurious resolved+new pair for each of its smells.

- [ ] **Step 1: Write the failing test**

Create `tests/test_changelog_architecture.py`:

```python
"""Tests for the changelog_architecture tool."""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.changelog_architecture import changelog_architecture


def _arch(**components: list[str]) -> Architecture:
    return Architecture(
        components=[
            Component(name=name, responsibility="", entities=list(entities))
            for name, entities in components.items()
        ],
        algorithm="test",
    )


def _empty_graph() -> DependencyGraph:
    return DependencyGraph()


def test_reports_structural_changes():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    result = changelog_architecture(
        arch_a, _empty_graph(), arch_b, _empty_graph(),
        smells_a=[], smells_b=[], metrics_a=[], metrics_b=[],
    )
    assert result["components"]["split"] == [
        {"from": "auth", "into": ["auth", "authz"],
         "entities": {"auth": 3, "authz": 3}}
    ]
    assert result["components"]["added"] == []


def test_reports_responsibility_shifts_at_entity_granularity():
    arch_a = _arch(auth=["a.A", "a.B", "a.C"], api=["p.1", "p.2", "p.3"])
    arch_b = _arch(auth=["a.A", "a.B"], api=["p.1", "p.2", "p.3", "a.C"])
    result = changelog_architecture(
        arch_a, _empty_graph(), arch_b, _empty_graph(),
        smells_a=[], smells_b=[], metrics_a=[], metrics_b=[],
    )
    assert {"entity": "a.C", "from": "auth", "to": "api"} in result["responsibility_shifts"]


def test_smell_survives_a_rename_without_spurious_churn():
    arch_a = _arch(util=["u.1", "u.2", "u.3"])
    arch_b = _arch(common=["u.1", "u.2", "u.3"])
    smell_a = SmellInstance(smell_type="BDC", severity="high", affected_components=["util"])
    smell_b = SmellInstance(smell_type="BDC", severity="high", affected_components=["common"])
    result = changelog_architecture(
        arch_a, _empty_graph(), arch_b, _empty_graph(),
        smells_a=[smell_a], smells_b=[smell_b], metrics_a=[], metrics_b=[],
    )
    assert result["smells"]["new"] == []
    assert result["smells"]["resolved"] == []
    assert len(result["smells"]["persisting"]) == 1


def test_new_and_resolved_smells_are_reported():
    arch = _arch(auth=["a.1", "a.2", "a.3"])
    gone = SmellInstance(smell_type="BCO", severity="low", affected_components=["auth"])
    fresh = SmellInstance(smell_type="BDC", severity="high", affected_components=["auth"])
    result = changelog_architecture(
        arch, _empty_graph(), arch, _empty_graph(),
        smells_a=[gone], smells_b=[fresh], metrics_a=[], metrics_b=[],
    )
    assert [s["smell_type"] for s in result["smells"]["new"]] == ["BDC"]
    assert [s["smell_type"] for s in result["smells"]["resolved"]] == ["BCO"]


def test_metric_deltas():
    arch = _arch(auth=["a.1", "a.2", "a.3"])
    result = changelog_architecture(
        arch, _empty_graph(), arch, _empty_graph(),
        smells_a=[], smells_b=[],
        metrics_a=[MetricResult(name="RCI", value=0.30)],
        metrics_b=[MetricResult(name="RCI", value=0.44)],
    )
    assert result["metrics"]["RCI"]["a"] == 0.30
    assert result["metrics"]["RCI"]["b"] == 0.44
    assert round(result["metrics"]["RCI"]["delta"], 4) == 0.14


def test_metric_present_on_only_one_side_has_null_delta():
    arch = _arch(auth=["a.1", "a.2", "a.3"])
    result = changelog_architecture(
        arch, _empty_graph(), arch, _empty_graph(),
        smells_a=[], smells_b=[],
        metrics_a=[], metrics_b=[MetricResult(name="TurboMQ", value=1.5)],
    )
    assert result["metrics"]["TurboMQ"]["a"] is None
    assert result["metrics"]["TurboMQ"]["delta"] is None


def test_refs_are_recorded_as_metadata():
    arch = _arch(auth=["a.1", "a.2", "a.3"])
    result = changelog_architecture(
        arch, _empty_graph(), arch, _empty_graph(),
        smells_a=[], smells_b=[], metrics_a=[], metrics_b=[],
        ref_a="v0.1.1", ref_b="v0.2.0",
    )
    assert result["refs"] == {"a": "v0.1.1", "b": "v0.2.0"}


def test_empty_architectures_do_not_raise():
    result = changelog_architecture(
        Architecture(), _empty_graph(), Architecture(), _empty_graph(),
        smells_a=[], smells_b=[], metrics_a=[], metrics_b=[],
    )
    assert result["summary"]["components_a"] == 0
    assert result["summary"]["components_b"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_changelog_architecture.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `src/arcade_agent/tools/changelog_architecture.py`:

```python
"""Tool: architectural changelog between two versions of a codebase."""

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.provenance import (
    StructuralChanges,
    classify_structural_changes,
)
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.registry import tool


def _smell_key(
    smell: SmellInstance, rename_map: dict[str, str] | None = None
) -> tuple[str, tuple[str, ...]]:
    """Identity of a smell, with component names optionally normalised."""
    components = smell.affected_components
    if rename_map:
        components = [rename_map.get(name, name) for name in components]
    return smell.smell_type, tuple(sorted(components))


def _smell_dict(smell: SmellInstance) -> dict:
    """Compact serialisable view of a smell."""
    return {
        "smell_type": smell.smell_type,
        "severity": smell.severity,
        "affected_components": sorted(smell.affected_components),
        "description": smell.description,
    }


def _languages(graph: DependencyGraph) -> list[str]:
    """Sorted distinct languages present in a dependency graph."""
    return sorted({e.language for e in graph.entities.values() if e.language})


def _structural_dict(changes: StructuralChanges) -> dict:
    """Serialise the structural buckets."""
    return {
        "added": list(changes.added),
        "removed": list(changes.removed),
        "renamed": [{"from": a, "to": b} for a, b in changes.renamed],
        "split": [
            {"from": s.source, "into": list(s.targets), "entities": dict(s.entities)}
            for s in changes.split
        ],
        "merged": [
            {"into": m.target, "from": list(m.sources), "entities": dict(m.entities)}
            for m in changes.merged
        ],
        "stable": list(changes.stable),
    }


@tool(
    name="changelog_architecture",
    description="Produce an architectural changelog between two versions: components "
    "added, removed, renamed, split or merged; entities that changed component; "
    "smells gained or resolved; and metric deltas.",
)
def changelog_architecture(
    arch_a: Architecture,
    graph_a: DependencyGraph,
    arch_b: Architecture,
    graph_b: DependencyGraph,
    *,
    smells_a: list[SmellInstance] | None = None,
    smells_b: list[SmellInstance] | None = None,
    metrics_a: list[MetricResult] | None = None,
    metrics_b: list[MetricResult] | None = None,
    ref_a: str | None = None,
    ref_b: str | None = None,
    min_entities: int = 3,
    min_share: float = 0.20,
) -> dict:
    """Build an architectural changelog between two recovered architectures.

    Args:
        arch_a: The earlier architecture.
        graph_a: Dependency graph for the earlier version.
        arch_b: The later architecture.
        graph_b: Dependency graph for the later version.
        smells_a: Smells for the earlier version. Computed if omitted.
        smells_b: Smells for the later version. Computed if omitted.
        metrics_a: Metrics for the earlier version. Computed if omitted.
        metrics_b: Metrics for the later version. Computed if omitted.
        ref_a: Optional label for the earlier version, recorded as metadata.
        ref_b: Optional label for the later version, recorded as metadata.
        min_entities: Absolute significance threshold for a flow.
        min_share: Fractional significance threshold in (0, 1].

    Returns:
        A dict with refs, components, responsibility_shifts, smells, metrics,
        languages and summary. Every collection is deterministically sorted.
    """
    changes = classify_structural_changes(
        arch_a, arch_b, min_entities=min_entities, min_share=min_share
    )

    if smells_a is None:
        smells_a = detect_smells(arch_a, graph_a)
    if smells_b is None:
        smells_b = detect_smells(arch_b, graph_b)
    if metrics_a is None:
        metrics_a = compute_metrics(arch_a, graph_a)
    if metrics_b is None:
        metrics_b = compute_metrics(arch_b, graph_b)

    shifts = [
        {"entity": fqn, "from": flow.source, "to": flow.target}
        for flow in changes.flows
        if flow.source != flow.target
        for fqn in flow.entities
    ]
    shifts.sort(key=lambda s: (s["entity"], s["from"], s["to"]))

    keys_a = {_smell_key(s, changes.rename_map): s for s in smells_a}
    keys_b = {_smell_key(s): s for s in smells_b}
    new_keys = sorted(set(keys_b) - set(keys_a))
    resolved_keys = sorted(set(keys_a) - set(keys_b))
    persisting_keys = sorted(set(keys_a) & set(keys_b))

    values_a = {m.name: m.value for m in metrics_a}
    values_b = {m.name: m.value for m in metrics_b}
    metrics: dict[str, dict] = {}
    for name in sorted(set(values_a) | set(values_b)):
        a_value = values_a.get(name)
        b_value = values_b.get(name)
        delta = (
            b_value - a_value
            if isinstance(a_value, (int, float)) and isinstance(b_value, (int, float))
            else None
        )
        metrics[name] = {"a": a_value, "b": b_value, "delta": delta}

    entities_a = set(arch_a.membership())
    entities_b = set(arch_b.membership())

    return {
        "refs": {"a": ref_a, "b": ref_b},
        "components": _structural_dict(changes),
        "responsibility_shifts": shifts,
        "smells": {
            "new": [_smell_dict(keys_b[k]) for k in new_keys],
            "resolved": [_smell_dict(keys_a[k]) for k in resolved_keys],
            "persisting": [_smell_dict(keys_b[k]) for k in persisting_keys],
        },
        "metrics": metrics,
        "languages": {"a": _languages(graph_a), "b": _languages(graph_b)},
        "summary": {
            "components_a": len(arch_a.components),
            "components_b": len(arch_b.components),
            "shifts": len(shifts),
            "entities_a": len(entities_a),
            "entities_b": len(entities_b),
            "entities_added": len(entities_b - entities_a),
            "entities_deleted": len(entities_a - entities_b),
            "smells_new": len(new_keys),
            "smells_resolved": len(resolved_keys),
        },
    }
```

**Before running:** confirm `DependencyGraph` exposes `.entities` as a dict of FQN → entity with a `.language` attribute. If the real attribute differs, fix `_languages` to match reality rather than changing the test.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_changelog_architecture.py -v`
Expected: 8 passed

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check src/ tests/ && mypy src/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/arcade_agent/tools/changelog_architecture.py tests/test_changelog_architecture.py
git commit -m "feat(changelog): architectural changelog tool (roadmap #10)"
```

---

### Task 6: Markdown exporter

**Files:**
- Create: `src/arcade_agent/exporters/changelog_md.py`
- Test: `tests/test_changelog_md.py`

**Interfaces:**
- Consumes: the dict returned by Task 5.
- Produces: `render_changelog_markdown(changelog: dict) -> str`. Task 7 depends on this name.

Empty sections are omitted entirely. A changelog with no changes renders a single "No architectural changes." line, not a wall of empty headings.

- [ ] **Step 1: Write the failing test**

Create `tests/test_changelog_md.py`:

```python
"""Tests for architectural changelog markdown rendering."""

from arcade_agent.exporters.changelog_md import render_changelog_markdown


def _changelog(**overrides) -> dict:
    base = {
        "refs": {"a": "v1", "b": "v2"},
        "components": {"added": [], "removed": [], "renamed": [],
                       "split": [], "merged": [], "stable": ["core"]},
        "responsibility_shifts": [],
        "smells": {"new": [], "resolved": [], "persisting": []},
        "metrics": {},
        "languages": {"a": ["python"], "b": ["python"]},
        "summary": {"components_a": 1, "components_b": 1, "shifts": 0,
                    "entities_a": 3, "entities_b": 3, "entities_added": 0,
                    "entities_deleted": 0, "smells_new": 0, "smells_resolved": 0},
    }
    base.update(overrides)
    return base


def test_no_changes_renders_a_single_line():
    out = render_changelog_markdown(_changelog())
    assert "No architectural changes" in out
    assert "### Split" not in out


def test_header_includes_refs():
    out = render_changelog_markdown(_changelog())
    assert "v1" in out and "v2" in out


def test_split_is_rendered():
    out = render_changelog_markdown(_changelog(components={
        "added": [], "removed": [], "renamed": [], "stable": [], "merged": [],
        "split": [{"from": "auth", "into": ["auth", "authz"],
                   "entities": {"auth": 3, "authz": 3}}],
    }))
    assert "auth" in out and "authz" in out
    assert "split" in out.lower()


def test_new_smell_is_rendered():
    out = render_changelog_markdown(_changelog(smells={
        "new": [{"smell_type": "BDC", "severity": "high",
                 "affected_components": ["core"], "description": "cycle"}],
        "resolved": [], "persisting": [],
    }))
    assert "BDC" in out


def test_metric_delta_is_rendered_with_sign():
    out = render_changelog_markdown(_changelog(
        metrics={"RCI": {"a": 0.30, "b": 0.44, "delta": 0.14}}
    ))
    assert "RCI" in out
    assert "+0.14" in out


def test_language_drift_is_surfaced():
    out = render_changelog_markdown(_changelog(
        languages={"a": ["python"], "b": ["python", "kotlin"]}
    ))
    assert "kotlin" in out


def test_output_is_deterministic():
    changelog = _changelog()
    assert render_changelog_markdown(changelog) == render_changelog_markdown(changelog)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_changelog_md.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

Create `src/arcade_agent/exporters/changelog_md.py`:

```python
"""Render an architectural changelog as markdown."""


def _fmt_delta(delta: float | None) -> str:
    """Format a metric delta with an explicit sign."""
    if delta is None:
        return "—"
    return f"{delta:+.2f}"


def render_changelog_markdown(changelog: dict) -> str:
    """Render a changelog_architecture result as markdown.

    Empty sections are omitted. A changelog with no structural changes, smell
    changes or metric movement renders a single explanatory line.

    Args:
        changelog: The dict returned by changelog_architecture.

    Returns:
        A markdown string suitable for a pull-request comment.
    """
    refs = changelog.get("refs") or {}
    ref_a = refs.get("a") or "baseline"
    ref_b = refs.get("b") or "current"

    lines = [f"## Architectural changes — `{ref_a}` → `{ref_b}`", ""]

    components = changelog["components"]
    smells = changelog["smells"]
    metrics = changelog["metrics"]
    shifts = changelog["responsibility_shifts"]

    body: list[str] = []

    if components["split"]:
        body.append("### Split")
        body.append("")
        for entry in components["split"]:
            targets = ", ".join(f"`{t}` ({entry['entities'][t]})" for t in entry["into"])
            body.append(f"- `{entry['from']}` split into {targets}")
        body.append("")

    if components["merged"]:
        body.append("### Merged")
        body.append("")
        for entry in components["merged"]:
            sources = ", ".join(f"`{s}` ({entry['entities'][s]})" for s in entry["from"])
            body.append(f"- `{entry['into']}` absorbed {sources}")
        body.append("")

    if components["added"] or components["removed"] or components["renamed"]:
        body.append("### Components")
        body.append("")
        for name in components["added"]:
            body.append(f"- added `{name}`")
        for name in components["removed"]:
            body.append(f"- removed `{name}`")
        for entry in components["renamed"]:
            body.append(f"- renamed `{entry['from']}` → `{entry['to']}`")
        body.append("")

    if shifts:
        body.append(f"### Responsibility shifts ({len(shifts)})")
        body.append("")
        for shift in shifts[:20]:
            body.append(
                f"- `{shift['entity']}`: `{shift['from']}` → `{shift['to']}`"
            )
        if len(shifts) > 20:
            body.append(f"- …and {len(shifts) - 20} more")
        body.append("")

    if smells["new"] or smells["resolved"]:
        body.append("### Smells")
        body.append("")
        for smell in smells["new"]:
            comps = ", ".join(f"`{c}`" for c in smell["affected_components"])
            body.append(f"- **new** {smell['smell_type']} ({smell['severity']}) — {comps}")
        for smell in smells["resolved"]:
            comps = ", ".join(f"`{c}`" for c in smell["affected_components"])
            body.append(f"- resolved {smell['smell_type']} — {comps}")
        body.append("")

    moved_metrics = {
        name: entry
        for name, entry in metrics.items()
        if entry.get("delta") not in (None, 0)
    }
    if moved_metrics:
        body.append("### Metrics")
        body.append("")
        body.append("| Metric | Before | After | Delta |")
        body.append("|--------|--------|-------|-------|")
        for name, entry in moved_metrics.items():
            before = "—" if entry["a"] is None else f"{entry['a']:.2f}"
            after = "—" if entry["b"] is None else f"{entry['b']:.2f}"
            body.append(f"| {name} | {before} | {after} | {_fmt_delta(entry['delta'])} |")
        body.append("")

    languages = changelog.get("languages") or {}
    if languages.get("a") != languages.get("b"):
        body.append(
            f"> **Language set changed** — `{ref_a}`: {languages.get('a')}, "
            f"`{ref_b}`: {languages.get('b')}. Comparisons across different "
            f"language sets are not like-for-like."
        )
        body.append("")

    if not body:
        body = ["No architectural changes.", ""]

    return "\n".join(lines + body).rstrip() + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_changelog_md.py -v`
Expected: 7 passed

- [ ] **Step 5: Lint and typecheck**

Run: `ruff check src/ tests/ && mypy src/`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/arcade_agent/exporters/changelog_md.py tests/test_changelog_md.py
git commit -m "feat(exporters): markdown renderer for the architectural changelog"
```

---

### Task 7: Rewire `ci/arch_diff.py`

**Files:**
- Modify: `src/arcade_agent/ci/arch_diff.py`
- Test: `tests/test_arch_diff.py` (update)

**Interfaces:**
- Consumes: `changelog_architecture` (Task 5), `render_changelog_markdown` (Task 6), corrected `compare` summary keys (Task 3).

**`arcade-arch-diff` must still never exit non-zero by default.** This is documented behaviour on the site (`docs/ci.md`) and in the positioning; this task adds no gating. If you find yourself writing `sys.exit(1)`, stop — that is out of scope.

- [ ] **Step 1: Find every use of the removed keys**

Run: `grep -n "possible_splits\|possible_merges" src/ tests/ -r`
Expected: hits in `src/arcade_agent/ci/arch_diff.py` and possibly `tests/test_arch_diff.py`. Every one must go.

- [ ] **Step 2: Update the failing test**

In `tests/test_arch_diff.py`, replace assertions referencing `possible_splits` / `possible_merges` with `splits` / `merges`. Then add:

```python
def test_report_includes_the_architectural_changelog(tmp_path):
    """The PR comment shows the changelog section when a baseline exists."""
    from arcade_agent.algorithms.architecture import Architecture, Component
    from arcade_agent.ci.arch_diff import build_report
    from arcade_agent.parsers.graph import DependencyGraph
    from arcade_agent.tools.compare import compare

    baseline = Architecture(
        components=[Component(name="auth", responsibility="",
                              entities=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])],
        algorithm="pkg",
    )
    current = Architecture(
        components=[
            Component(name="auth", responsibility="", entities=["a.A", "a.B", "a.C"]),
            Component(name="authz", responsibility="", entities=["z.X", "z.Y", "z.Z"]),
        ],
        algorithm="pkg",
    )
    graph = DependencyGraph()
    report = build_report(
        current, graph, metrics=[], smells=[],
        drift=compare(baseline, current), baseline=baseline,
    )
    assert "Architectural changes" in report
    assert "authz" in report


def test_arch_diff_exits_zero_even_when_drift_is_detected(tmp_path):
    """Documented behaviour: arch-diff is informational, not a gate.

    Exercises the real console script so the guarantee is tested by
    behaviour, not by grepping the source for a particular spelling of exit.
    """
    import subprocess

    repo = tmp_path / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "a.py").write_text("class A:\n    pass\n")
    (repo / "pkg" / "b.py").write_text("from pkg.a import A\n\n\nclass B(A):\n    pass\n")

    # First run stores a baseline; second run detects drift against it.
    first = subprocess.run(
        ["arcade-arch-diff", "--source", str(repo), "--language", "python",
         "--update-baseline"],
        capture_output=True,
    )
    assert first.returncode == 0, first.stderr.decode()

    (repo / "pkg" / "c.py").write_text("from pkg.b import B\n\n\nclass C(B):\n    pass\n")
    second = subprocess.run(
        ["arcade-arch-diff", "--source", str(repo), "--language", "python"],
        capture_output=True,
    )
    assert second.returncode == 0, second.stderr.decode()
```

**If `arcade-arch-diff`'s real flags differ from `--source` / `--language` /
`--update-baseline`, read the argparse setup at the bottom of
`src/arcade_agent/ci/arch_diff.py` and use the real ones.** Do not change the
assertion: the exit code must be 0 on both runs.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_arch_diff.py -v`
Expected: FAIL — `assert "Architectural changes" in report`

- [ ] **Step 4: Rewire `build_report`**

In `src/arcade_agent/ci/arch_diff.py`:

1. Add imports:

```python
from arcade_agent.exporters.changelog_md import render_changelog_markdown
from arcade_agent.tools.changelog_architecture import changelog_architecture
```

2. Keep the existing header and the "Drift from Baseline" metric table — they still carry the current-version summary.

3. **Delete the entire hand-rolled "### Changes" section** (the block that counts `components_added`, `components_removed`, entity movements, `possible_merges`, `possible_splits`). Replace it with:

```python
        changelog = changelog_architecture(
            baseline,
            graph,
            current,
            graph,
            smells_a=[],
            smells_b=smells,
            metrics_a=[],
            metrics_b=metrics,
            ref_a="baseline",
            ref_b="current",
        )
        lines.append(render_changelog_markdown(changelog))
        lines.append("")
```

**Note on the graph argument:** `arch_diff` only has the *current* dependency graph — the baseline is a stored `Architecture` with no graph. Passing `graph` for both sides is correct for the structural and metric sections (which take the pre-computed values we pass explicitly) but means `_languages` reports the current language set on both sides. Pass `smells_a=[]` and `metrics_a=[]` explicitly, as above, so no smell or metric detection runs against the mismatched graph. Every smell will therefore appear as "new" on the first run after a baseline is stored; that is honest given the baseline carries no smell record.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_arch_diff.py -v`
Expected: all passed

- [ ] **Step 6: Run the full suite**

Run: `pytest && ruff check src/ tests/ && mypy src/`
Expected: all green — no remaining failures from Task 3

- [ ] **Step 7: Commit**

```bash
git add src/arcade_agent/ci/arch_diff.py tests/test_arch_diff.py
git commit -m "feat(ci): emit the architectural changelog in the drift report

Replaces the hand-rolled changes summary with the changelog renderer.
arch-diff remains informational and still never exits non-zero."
```

---

### Task 8: MCP wrapper and end-to-end verification

**Files:**
- Modify: `src/arcade_agent/tools/adapters/mcp.py`
- Test: `tests/test_changelog_e2e.py` (create)
- Modify: `ROADMAP.md`

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the failing end-to-end test**

Create `tests/test_changelog_e2e.py`:

```python
"""End-to-end changelog over arcade-agent's own history."""

from pathlib import Path

import pytest

from arcade_agent.tools.changelog_architecture import changelog_architecture
from arcade_agent.tools.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover

REPO_ROOT = Path(__file__).resolve().parents[1]


def _has_tag(tag: str) -> bool:
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", f"{tag}^{{commit}}"],
        capture_output=True,
    )
    return result.returncode == 0


@pytest.mark.skipif(
    not (_has_tag("v0.1.1") and _has_tag("v0.2.0")),
    reason="requires the v0.1.1 and v0.2.0 tags",
)
def test_changelog_between_real_releases():
    repo_a = ingest(str(REPO_ROOT), language="python", ref="v0.1.1")
    repo_b = ingest(str(REPO_ROOT), language="python", ref="v0.2.0")
    try:
        graph_a = parse(str(repo_a.path), language="python")
        graph_b = parse(str(repo_b.path), language="python")
        arch_a = recover(graph_a, algorithm="pkg")
        arch_b = recover(graph_b, algorithm="pkg")

        result = changelog_architecture(
            arch_a, graph_a, arch_b, graph_b, ref_a="v0.1.1", ref_b="v0.2.0"
        )

        # Known figures for these two tags.
        assert result["summary"]["entities_a"] > 0
        assert result["summary"]["entities_b"] > result["summary"]["entities_a"]
        assert result["refs"] == {"a": "v0.1.1", "b": "v0.2.0"}

        # Every component appears in exactly one bucket per side.
        components = result["components"]
        b_side = (
            set(components["added"])
            | {m["into"] for m in components["merged"]}
            | {e["to"] for e in components["renamed"]}
            | set(components["stable"])
            | {t for s in components["split"] for t in s["into"]}
        )
        assert len(b_side) == len(arch_b.components)
    finally:
        repo_a.cleanup()
        repo_b.cleanup()
```

- [ ] **Step 2: Run it**

Run: `pytest tests/test_changelog_e2e.py -v`
Expected: PASS. If it fails on the bucket-partition assertion, **that is a real bug in Task 2's precedence rules** — fix `provenance.py`, not the test.

- [ ] **Step 3: Record the observed thresholds**

Run the e2e test with `-s` and print the split/merge counts. If `v0.1.1 → v0.2.0` produces splits or merges that are obviously just refactoring noise, note the observed numbers in a comment at the top of `test_changelog_e2e.py` and report them — the spec flags `min_entities=3` / `min_share=0.20` as provisional and this is the first real datapoint. **Do not silently change the defaults**; report and let Đức decide.

- [ ] **Step 4: Add the MCP wrapper**

In `src/arcade_agent/tools/adapters/mcp.py`, after the `dependency_cone` block and before `get_full_result`, add:

```python
    # -- changelog_architecture ------------------------------------------------

    @server.tool()
    def changelog_architecture(
        arch_a: str,
        graph_a: str,
        arch_b: str,
        graph_b: str,
        ref_a: str | None = None,
        ref_b: str | None = None,
        min_entities: int = 3,
        min_share: float = 0.20,
        max_tokens: int | None = None,
    ) -> str:
        """Architectural changelog between two analysed versions of a codebase.

        Args:
            arch_a: Session ID from a 'recover' call on the earlier version.
            graph_a: Session ID from a 'parse' call on the earlier version.
            arch_b: Session ID from a 'recover' call on the later version.
            graph_b: Session ID from a 'parse' call on the later version.
            ref_a: Optional label for the earlier version (e.g. a tag).
            ref_b: Optional label for the later version.
            min_entities: Absolute significance threshold for a component flow.
            min_share: Fractional significance threshold in (0, 1].
            max_tokens: Optional token budget for the response.
        """
        from arcade_agent.tools.changelog_architecture import (
            changelog_architecture as _changelog,
        )

        result = _changelog(
            _resolve(arch_a, "Architecture"),
            _resolve(graph_a, "DependencyGraph"),
            _resolve(arch_b, "Architecture"),
            _resolve(graph_b, "DependencyGraph"),
            ref_a=ref_a,
            ref_b=ref_b,
            min_entities=min_entities,
            min_share=min_share,
        )
        serialized = serialize_result(result)
        return json.dumps(_apply_budget(serialized, max_tokens), indent=2)
```

**Match the real `_resolve` signature** in that file — read the `dependency_cone` block above it and copy the pattern exactly.

- [ ] **Step 5: Verify the MCP tool registers**

Run: `pytest tests/test_mcp.py tests/test_mcp_e2e.py -v`
Expected: all passed. If the suite asserts a tool count, update it.

- [ ] **Step 6: Update ROADMAP.md**

Change item 10 from `- [ ]` to `- [x]` and update the priority table: move `10` out of **Now** into **Done**, and promote `11, 16b` into **Now**.

- [ ] **Step 7: Full green run**

Run: `pytest && ruff check src/ tests/ && mypy src/`
Expected: all green

- [ ] **Step 8: Commit**

```bash
git add src/arcade_agent/tools/adapters/mcp.py tests/test_changelog_e2e.py ROADMAP.md
git commit -m "feat(mcp): expose changelog_architecture; e2e over v0.1.1 -> v0.2.0"
```

---

## Done criteria

- `pytest` fully green; `ruff check src/ tests/` and `mypy src/` clean.
- `grep -rn "possible_splits\|possible_merges" src/ tests/` returns nothing.
- `arcade-arch-diff --source . --language python` prints an "Architectural changes" section and exits 0.
- The e2e test's observed split/merge counts for `v0.1.1 → v0.2.0` have been reported so the thresholds can be tuned.
