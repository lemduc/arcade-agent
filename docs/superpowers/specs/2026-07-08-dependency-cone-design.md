# Design: `dependency_cone` tool (roadmap #13)

## Purpose

Given an entity or file, return its **dependency cone** — the set of nodes
reachable by following dependencies upstream (what the seed depends on) and/or
downstream (what depends on the seed), with depth control. Answers two agent
questions from one entry point:

- **downstream** — "if I change this, what is the blast radius?"
- **upstream** — "what must I read/understand to change this?"

It completes the agent-context tool cluster (`find_relevant`, `context_for_task`,
`diff_impact`, `api_surface`) and is built on top of the `#12` branch so it can
reuse `diff_impact`'s cycle-safe traversal.

## Scope

In scope: a single new `@tool`, a shared traversal helper, an MCP wrapper, tests,
and a behavior-preserving refactor of `diff_impact` onto the shared helper.

Out of scope: rendering the cone as a diagram, cross-language edges, ranking by
relevance (that is `context_for_task`'s job).

## Module layout

- `src/arcade_agent/algorithms/traversal.py` — pure, graph-only helpers:
  - `adjacency_with_relations(graph, *, reverse) -> dict[str, list[tuple[str, str]]]`
    Builds `node -> [(neighbor, relation), ...]`. Forward (`reverse=False`):
    `source -> [(target, rel)]`. Reverse (`reverse=True`): `target -> [(source, rel)]`.
  - `walk_cone(adjacency, seeds, max_depth, max_nodes=None) -> tuple[list[dict], bool]`
    Breadth-first walk from `seeds` over `adjacency`. Returns
    `(nodes, truncated)` where each node is `{"fqn", "distance", "via_relation"}`.
    `visited` is pre-seeded with `seeds` so seeds are excluded from the result and
    cycles cannot loop. `distance` is hops from the nearest seed (1 = direct);
    `via_relation` is the relation of the **first** hop taken to reach the node.
    Results are sorted by `(distance, fqn)`. When `max_nodes` is set, the walk
    keeps the closest-first nodes and returns `truncated=True` if any were dropped.
- `src/arcade_agent/tools/dependency_cone.py` — the `@tool`, seed resolution, and
  output assembly.
- `src/arcade_agent/tools/diff_impact.py` — refactored to obtain its downstream
  dependents via `adjacency_with_relations(graph, reverse=True)` + `walk_cone(...)`
  instead of its current inline reverse-BFS. Behavior is unchanged; its existing
  tests are the regression guard.

## Tool signature

```python
def dependency_cone(
    dep_graph: DependencyGraph,
    target: str,                    # entity FQN or file path
    direction: str = "both",        # "upstream" | "downstream" | "both"
    max_depth: int = 3,
    max_nodes: int | None = None,   # per-direction cap
) -> dict
```

## Direction semantics

Stated explicitly because it is easy to invert:

- **downstream** = entities that depend **on** the seed (blast radius). An edge
  `X -> seed` means `X` depends on the seed, so downstream is found by walking
  **reverse** edges (`reverse=True`).
- **upstream** = entities the seed depends **on** (prerequisites). An edge
  `seed -> Y` means the seed depends on `Y`, so upstream is found by walking
  **forward** edges (`reverse=False`, i.e. `to_adjacency` with relations).

## Behavior

1. **Resolve `target` to seed FQNs.**
   - If `target` is a key in `dep_graph.entities`, `matched_by = "entity"` and
     `seed_entities = [target]`.
   - Otherwise treat `target` as a file path and match entities by
     `entity.file_path` using `diff_impact`'s tolerant `_paths_match` (exact /
     suffix-on-`/`-boundary / basename). `matched_by = "file"`,
     `seed_entities = [all matching fqns]`.
   - If neither resolves any entity, return a clean empty result with a `note`
     (no exception).
2. **Run the requested direction(s).** For each of upstream/downstream requested
   by `direction`, build the appropriate adjacency and call `walk_cone`.
3. **Assemble output** (below). `files` is the deduped, sorted list of
   `file_path` values of the reached entities.

Validation: an unknown `direction` value returns a clear error dict listing the
valid values; `max_depth < 1` yields empty cones (no traversal).

## Output shape

```jsonc
{
  "target": "com.example.util.MathHelper",
  "matched_by": "entity",              // or "file"
  "seed_entities": ["com.example.util.MathHelper"],
  "direction": "both",                 // echoes the request
  "max_depth": 3,
  "upstream":   {                      // present iff direction in (upstream, both)
    "num_nodes": 0,
    "truncated": false,
    "nodes": [],                       // [{ "fqn", "distance", "via_relation" }], sorted by (distance, fqn)
    "files": []
  },
  "downstream": {                      // present iff direction in (downstream, both)
    "num_nodes": 2,
    "truncated": false,
    "nodes": [
      { "fqn": "com.example.calc.Calculator",        "distance": 1, "via_relation": "import" },
      { "fqn": "com.example.calc.AdvancedCalculator", "distance": 1, "via_relation": "import" }
    ],
    "files": ["AdvancedCalculator.java", "Calculator.java"]
  }
}
```

Empty/unresolved result:

```jsonc
{
  "target": "does/not/exist.py",
  "matched_by": null,
  "seed_entities": [],
  "direction": "both",
  "max_depth": 3,
  "note": "No entity or file matched 'does/not/exist.py'."
}
```

Only the direction block(s) requested appear. `truncated: true` whenever
`max_nodes` drops closest-first nodes — no silent capping.

## Token efficiency

Output is entity-FQN + integer distance + short relation string per node, plus a
deduped file rollup — the same compact shape as `diff_impact.downstream_dependents`.
`max_depth` (default 3) bounds reach; `max_nodes` caps per direction. The MCP
wrapper additionally passes results through `serialize_result` + `_apply_budget`
like every other tool.

## Testing

`tests/test_dependency_cone.py` (pytest, `sample_graph` / `sample_architecture`):

- downstream from an entity seed returns dependents with correct distance / relation
- upstream from an entity seed returns dependencies (e.g. seed `Calculator`
  upstream includes `MathHelper` at distance 1)
- `direction="both"` returns both blocks; `"upstream"`/`"downstream"` return only one
- file-path seed resolves to all entities in that file
- `max_depth=1` bounds the walk to direct neighbors
- the fixture cycle (`AdvancedCalculator -> Calculator`, both -> `MathHelper`) does
  not hang and yields finite results
- `max_nodes` smaller than the reachable set sets `truncated=true` and keeps the
  closest nodes
- unresolved `target` returns the clean empty result with a `note`
- invalid `direction` returns an error dict

`tests/test_traversal.py`: unit tests for `adjacency_with_relations` (forward vs
reverse) and `walk_cone` (distance, first-hop relation, cycle safety, `max_nodes`
truncation).

Regression guard: `tests/test_diff_impact.py` must stay green after the refactor.

## Review

Independent adversarial reviewer (model fidelity against the real Entity/Edge
model, correctness edge cases — especially direction inversion and cycle safety —
scope, and a re-run of the tests), matching the process used for the previous
three tools.
