# Design: `changelog_architecture` tool (roadmap #10)

## Purpose

Given two versions of a codebase, produce an **architectural changelog**: which
components were added, removed, renamed, split or merged; which entities changed
component ("shifted responsibilities"); which smells appeared or were resolved; and
how the metrics moved.

This is the artifact that answers *"what did the last N pull requests do to our
architecture"* — a question no diff-scoped code-review tool can answer, because
cumulative structural drift is invisible in any single diff. It is the primary
deliverable behind the project's positioning as a structural regression test for
agent-authored code.

## Scope

In scope: a new pure `algorithms/provenance.py`; a **correctness rewrite** of
`tools/compare.py`'s split/merge classification; a `ref` parameter on
`tools/ingest.py`; the new `changelog_architecture` tool; a markdown exporter; and
rewiring `ci/arch_diff.py` to emit the changelog in its PR comment.

Out of scope: LLM narrative summaries; threshold **gating** / non-zero exit codes;
`blame_component` (#11); any change to cross-language relinking.

## Why `compare` must change first

`algorithms/matching.py::match_components` solves a **1:1 assignment problem**
(Hungarian). It structurally cannot represent a split (one source → two targets) or a
merge (two sources → one target).

`tools/compare.py` nevertheless reports `possible_splits` / `possible_merges`, derived
from:

```python
if m["similarity"] < 0.5 and len(m["entities_added"]) > len(m["entities_removed"]):
    merges.append(m)
elif m["similarity"] < 0.5 and len(m["entities_removed"]) > len(m["entities_added"]):
    splits.append(m)
```

Two defects follow:

1. **Mislabelling.** A heavily refactored *renamed* component is labelled "split" or
   "merge" purely by which way its entity count moved.
2. **Double counting.** A genuine split (`auth` → `auth` + `authz`) appears both as a
   low-similarity 1:1 match *and* as an added component. The same event is reported
   twice under two names.

A changelog whose headline is "component `auth` split" cannot be built on this.
Because the current labels are wrong rather than merely imprecise, `compare` is
corrected in place rather than left alongside a second, disagreeing implementation.
The repo is pre-1.0 and `compare`'s only in-tree consumer is `ci/arch_diff.py`.

## Module layout

- `src/arcade_agent/algorithms/provenance.py` — **new, pure, no I/O.**

  ```python
  @dataclass(frozen=True)
  class Flow:
      source: str                    # component name in arch_a
      target: str                    # component name in arch_b
      entities: tuple[str, ...]      # sorted FQNs present in both, that moved

  def entity_flows(arch_a, arch_b) -> tuple[Flow, ...]
  ```

  Attributes every entity present in **both** architectures to the
  `(source component, target component)` pair it travelled between. An entity present
  in only one architecture produces no flow: newly added entities and deleted entities
  are not individually reported, but they do change component sizes and therefore
  affect the `min_share` test below. Their totals appear in `summary`.
  Output sorted by `(source, target)`; `Flow.entities` sorted.

  ```python
  def classify_structural_changes(
      arch_a, arch_b, *, min_entities: int = 3, min_share: float = 0.20
  ) -> StructuralChanges
  ```

  A flow is **significant** when it carries `>= min_entities` entities **or** at least
  `min_share` of `min(|source component in arch_a|, |target component in arch_b|)`,
  each measured in entity count at its own version. Classification:

  | Bucket | Rule |
  |---|---|
  | `split` | a component of `arch_a` with **≥2** significant outgoing flows |
  | `merged` | a component of `arch_b` with **≥2** significant incoming flows |
  | `removed` | a component of `arch_a` with **0** significant outgoing flows |
  | `added` | a component of `arch_b` with **0** significant incoming flows |
  | `renamed` | exactly one significant flow each way, names differ |
  | `stable` | exactly one significant flow each way, names equal |

  **Precedence — split and merge outrank rename and stable.** The rules above are not
  sufficient on their own: a component of `arch_a` with exactly one significant
  outgoing flow *into a merge target* satisfies `renamed`, which would report the same
  event twice — once as `util → core` and again inside `core`'s merge entry. Two
  precedence rules resolve this:

  - A component of `arch_a` whose single significant outgoing flow lands on a **merge
    target** is *absorbed*. It is reported only inside that merge entry, never as
    `renamed`, `stable` or `removed`.
  - A component of `arch_b` whose single significant incoming flow originates from a
    **split source** is a *product of that split*. It is reported only inside that
    split entry, never as `renamed`, `stable` or `added`.

  With those rules **the six top-level buckets partition the components**: each
  component of `arch_a` is classified into exactly one of
  `{removed, split, renamed, stable}` or is absorbed into a merge, and each component
  of `arch_b` into exactly one of `{added, merged, renamed, stable}` or is a split
  product. Split and rename are mutually exclusive by construction (≥2 outgoing flows
  vs exactly 1).

  **`Split.targets` and `Merge.sources` are descriptive provenance, not
  classification**, and may name a component that is classified elsewhere. This is
  intentional. Consider `S` splitting into `S` and `T`, where `T` independently also
  absorbs an unrelated `X`:

  ```
  split:  S -> (S, T)
  merged: T <- (S, X)
  ```

  `S` is named twice, and both statements are true — `S` did split, and `T` did draw
  from both `S` and `X`. Suppressing `S` from `T`'s sources to force a stricter
  partition would misreport where half of `T`'s entities came from, which is a worse
  error than the double-naming. The classification is disjoint; the provenance detail
  is not, and does not claim to be.

- `src/arcade_agent/tools/compare.py` — classification replaced by
  `classify_structural_changes`. Return shape keeps `overall_similarity` and
  `matches` (still Hungarian-derived, still used for the similarity score and rename
  detection). `summary.possible_splits` / `possible_merges` are replaced by accurate
  `splits` / `merges`. **This is a deliberate behaviour change.**

- `src/arcade_agent/tools/ingest.py` — new `ref: str | None = None` parameter.

- `src/arcade_agent/tools/changelog_architecture.py` — the new `@tool`. Pure: no git,
  no filesystem.

  ```python
  def changelog_architecture(
      arch_a, graph_a, arch_b, graph_b,
      *,
      smells_a=None, smells_b=None,      # computed if not supplied
      metrics_a=None, metrics_b=None,    # computed if not supplied
      ref_a: str | None = None,          # recorded as metadata only
      ref_b: str | None = None,
      min_entities: int = 3,
      min_share: float = 0.20,
  ) -> dict
  ```

  No `max_tokens` on the tool itself: the house pattern applies the budget at the
  MCP adapter layer via `_apply_budget`, exactly as `dependency_cone` does.

  Smells and metrics are optional so a caller that already computed them (as
  `arch_diff` does) does not pay twice.

- `src/arcade_agent/exporters/changelog_md.py` — `render_changelog_markdown(dict) -> str`.

- `src/arcade_agent/ci/arch_diff.py` — emits the changelog section when a baseline
  exists. Retains the documented **"informational, never exits nonzero by default"**
  behaviour; this change adds no gating.

## Data flow

```
ingest(".", ref="v0.1.1") → parse → recover ─┐
                                              ├→ changelog_architecture → dict → changelog_md
ingest(".", ref="v0.2.0") → parse → recover ─┘
```

Three independently-callable stages. The tool itself never touches git, preserving the
repo's "no CLI orchestrator; each tool independently callable" rule.

## Output shape

```jsonc
{
  "refs": {"a": "v0.1.1", "b": "v0.2.0"},          // null when not supplied
  "components": {
    "added":    ["parsers.kotlin"],
    "removed":  [],
    "renamed":  [{"from": "util", "to": "common"}],
    "split":    [{"from": "auth", "into": ["auth", "authz"],
                  "entities": {"auth": 14, "authz": 9}}],
    "merged":   [{"into": "core", "from": ["core", "util"],
                  "entities": {"core": 31, "util": 6}}],
    "stable":   ["exporters"]
  },
  "responsibility_shifts": [
    {"entity": "arcade_agent.tools.query.Query", "from": "tools", "to": "core"}
  ],
  "smells":  {"new": [...], "resolved": [...], "persisting": [...]},
  "metrics": {"coupling": {"a": 0.31, "b": 0.44, "delta": 0.13}},
  "languages": {"a": ["python"], "b": ["python", "kotlin"]},
  "summary": {"components_a": 9, "components_b": 10, "shifts": 12,
              "entities_a": 325, "entities_b": 331,
              "entities_added": 9, "entities_deleted": 3,
              "smells_new": 2, "smells_resolved": 1}
}
```

In `split.entities` the keys are **target** component names (where `auth`'s entities
landed); in `merged.entities` the keys are **source** component names (where `core`'s
entities came from). Values are entity counts along that flow.

`responsibility_shifts` reports **every** cross-component entity move at entity
granularity, including moves along flows too small to be structurally significant.
That is the point: sub-threshold drift is exactly what accumulates unnoticed.

Follows the house MCP pattern — the adapter serialises the result and applies
progressive truncation via the existing `budget.py` when the caller passes
`max_tokens`.

### Smell identity across versions

A smell is identified by `(smell_type, sorted(affected_components))`. Component names
on the `arch_a` side are **normalised through the rename map** from
`classify_structural_changes` before comparison. Without this, every renamed component
manufactures a spurious `resolved` + `new` pair for each smell attached to it.

Smells attached to split or merged components cannot be normalised unambiguously and
are reported as `resolved` on the old name and `new` on the new name(s), with the
structural event alongside as the explanation.

### Metric deltas

`delta = b - a` for numeric `MetricResult.value`. Non-numeric metrics are carried with
`"delta": null` rather than dropped.

## `ingest(ref=...)`

Materialises a commit or tag **without mutating the caller's working tree** — no
`git checkout`, no branch switching, no stash. Implementation:

1. Resolve and validate with `git -C <repo> rev-parse --verify <ref>^{commit}`.
2. `git -C <repo> archive <ref>` piped into `tar -x` in a fresh temp directory.
3. `IngestedRepo.version = ref`; `is_temp = True`.

`git archive` is preferred over `git worktree add` because it needs no lock files, no
worktree registration, and no cleanup beyond removing the temp directory. Its cost is
that the extracted tree has no `.git`, so tag-based version detection cannot run —
irrelevant here, since the caller has already named the ref.

Applies to local repos and to cloned URLs (archive is taken from the clone).

## Error handling

| Condition | Behaviour |
|---|---|
| Unknown `ref` | `ValueError` naming the ref, listing the repo's available tags |
| `ref` given, source is not a git repo | `ValueError` stating the source is not a git repository |
| Either architecture has no components | Well-formed changelog — all components on the other side reported as added/removed. Never raises. |
| Both architectures empty | Empty changelog with zeroed summary. Never raises. |
| Language sets differ between refs | Recorded in `languages`; **not** an error. Comparing a Python-only recovery against a polyglot one silently produces nonsense, so the difference must be visible in the output. |
| `min_share` outside `(0, 1]` | `ValueError` |

## Testing

Pure unit tests over hand-built `Architecture` fixtures (no git, no parsing):

- identity — everything `stable`, no shifts
- pure rename — one `renamed`, zero `added`/`removed`
- clean split — one `split`, and the new component does **not** also appear in `added`
- clean merge — one `merged`, and the absorbed component does **not** also appear in `removed`
- split and merge in the same diff
- **precedence: absorbed component** — `util`'s entities all flow into a `core` that
  also absorbs from elsewhere; `util` appears only inside `core`'s merge entry, and
  **not** as `renamed`, `stable` or `removed`
- **precedence: split product** — the component produced by a split appears only
  inside the split entry, and **not** as `added` or `renamed`
- sub-threshold flow — appears in `responsibility_shifts`, not in `split`
- empty side, both sides empty
- smell normalisation across a rename — no spurious new/resolved pair

Regression: existing `tests/test_arch_diff.py` must stay green; add coverage for
`compare`'s corrected `splits`/`merges` keys.

`ingest(ref=...)`: a temporary git fixture repo with two tagged commits — asserts the
working tree is untouched and the extracted tree matches the ref.

Golden-file test for `render_changelog_markdown`.

End-to-end: arcade-agent itself between `v0.1.1` and `v0.2.0` — a real fixture whose
figures are already known (64 → 65 source files, 325 → 331 entities, 176 → 179 edges,
9 components both sides).

## Open tunables

`min_entities = 3` and `min_share = 0.20` are the defaults, exposed as parameters.
They decide signal-to-noise: too low and every refactor reads as a split, too high and
real ones vanish. Expect to revise them after running against real repositories; the
e2e fixture above is the first datapoint.
