# Kotlin import attribution and cohesion reproduction

This standalone fixture reproduces a **detector coverage/calibration defect**:
structural Kotlin dependencies can produce an unqualified HIGH concern-overload
finding for a single computation whose internal calls are not collected.
It does not establish a Kotlin parser contract violation. The repository README
advertises Kotlin as structural support (import + inheritance graph).

Run from the repository root after installing `.[languages,dev]`:

```sh
PYTHONPATH=src .venv/bin/python examples/kotlin_dependency_coverage/reproduce.py
.venv/bin/pytest -q tests/test_tools/test_kotlin_dependency_coverage.py
```

The example uses the same `analyze` pipeline as MCP, with `language=kotlin`,
`algorithm=pkg`, `exclude_tests=true`, `use_cache=false`, and `use_llm=false`.
It prints edge counts, raw graph metadata, detector evidence, smells, and metrics.
To reproduce through MCP, analyze this directory's `src` subdirectory, then use
`get_full_result` for graph, architecture, smells, and metrics in that session.

Observed at arcade-agent source commit `0db7fabb75708272340fa9248b210298aced1204`
(package version 0.3.0):

| Observation | Result |
| --- | --- |
| Entities / edges | 51 / 12 |
| Relations collected in this fixture | 12 import edges; no call edges |
| Renderer imports | 3 file/target pairs expanded into 9 entity edges |
| Ui component | 42 entities, 0 recorded internal edges, HIGH concern overload |
| Explicit calls in MainActivity source | 40, all absent from the graph |
| Counterfactual with those 40 calls added | Concern overload disappears |
| Independent source-import cycle | Data → Export → View → Data |
| Graph metadata | Empty; no dependency coverage qualification |

`TimelineFrameRenderer.close()` is empty but receives the same three import edges
as the class and `render()`. `Bitmap` and `Paint` are intentionally unused imports.
These edges represent file import attribution, not independent resolved usages.

`MainActivity` is a synthetic single-computation chain (not an Android Activity).
Its 41 methods plus the class cross the default HIGH threshold of 40 entities.
The controlled test adds only calls explicitly present in source: density rises
from 0 to 40/42, exceeding the detector's 0.4 guard. This isolates missing coverage
as the trigger without implementing or pretending to implement call resolution.

Metrics count the expanded graph edges. Package recovery may merge the small
renderer component with Canvas, so the example reports RCI 0.75 (9 internal edges
out of 12), even while Ui's internal connectivity is zero. These numbers describe
the recorded graph; they are not evidence that Ui's methods are unrelated.

Three passing characterization tests cover import attribution, missing-call
sensitivity, and the independent cycle. The fourth test deliberately FAILS:
`test_structural_only_graph_should_not_emit_unqualified_high_cohesion_finding`.
It expresses the desired detector guard, without an xfail marker or suppression.
This draft PR is a reproduction, not a production fix; its test CI is expected
to be red until the guard is implemented. A follow-up should
expose relation coverage and qualify or suppress unsupported cohesion findings;
adding compiler-equivalent Kotlin call resolution is a separate design choice.

The original MultiplayerArt Android scope was also rechecked from a temporary
`git archive` of commit `31327fc159374b947822bff85d314626ba0d4d28`, using
the same pipeline and flags. It reproduced the reported totals exactly:
1,793 entities / 27,909 edges (27,842 import, 65 implements, 2 extends),
and Mainactivity HIGH with 194 entities / 0 internal edges. The working checkout
was not modified. These real-project counts are separate from the fixture.
Neither result proves that MainActivity in the real application has only one concern,
or invalidate the independently evidenced package cycle. Listener and Domain hub
findings are outside its scope.
