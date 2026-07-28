# Real-World Case Catalog

This catalog records how arcade-agent is exercised across repositories,
languages, and delivery surfaces. It is both a map of current evidence and an
acceptance contract for adding new cases.

Last reviewed: **2026-07-28**.

The catalog deliberately separates:

- **expected invariants**: behavior that must remain true;
- **observed output**: a measured result for one pinned run; and
- **golden output**: exact values that may be asserted only when every input is
  immutable.

Architecture metrics are discovery signals, not universal pass/fail thresholds.
An entity count or score changing in an evolving repository is not automatically
a regression.

## Evidence levels

| Level | Meaning |
|---|---|
| **Automated** | Runs in the arcade-agent test suite or CI and has executable assertions. |
| **Live external** | Runs in another repository through a released arcade-agent integration. |
| **Historical verified** | A real run was completed and recorded, but is not continuously rerun. |
| **Regression fixture** | A real defect was reduced to a small, deterministic fixture. |
| **In flight** | Executable evidence exists on an unmerged branch or pull request. |
| **Proposed** | The case and acceptance criteria are defined, but no evidence run exists yet. |

## Coverage matrix

| ID | Repository or corpus | Languages | Surface | Evidence level | Primary purpose |
|---|---|---|---|---|---|
| RW-01 | `lemduc/arcade-agent` | Python | Source install, GitHub Actions, PR comment | Automated | Self-dogfood the full architecture-analysis workflow |
| RW-02 | `usc-softarch/arcade_core` `v1.2.0` | Java | Local CLI/example report | Historical verified | Analyze a real architecture-recovery workbench |
| RW-03 | `tuannx/spring-boot-multi-region-ha` | Java | Released composite GitHub Action | Live external | Prove package distribution, baseline storage, and PR reporting |
| RW-04 | `embabel/embabel-agent` | Java + Kotlin | CLI/MCP analysis plus reduced fixtures | Historical verified + regression fixture | Validate a large JVM polyglot graph |
| RW-05 | `tests/fixtures/java_kotlin_mixed` and `maven_java_kotlin` | Java + Kotlin | Direct pipeline and MCP adapter | Automated | Pin JVM relinking and ingest-session behavior |
| RW-06 | `tests/fixtures/python_java_mixed` | Python + Java | Direct multi-language parse | Automated | Prove unsupported language families stay disconnected |
| RW-07 | `NousResearch/hermes-agent` MCP catalog integration | Python package + MCP | Fresh Python 3.12 install | Historical verified | Prove clean installation and MCP tool discovery |
| RW-08 | arcade-agent release history | Python | Git-ref ingest and architectural changelog | In flight | Compare immutable releases and tune structural-change thresholds |

## RW-01 — arcade-agent self-dogfooding

**Purpose:** prove that the source under review can install and analyze its own
repository, compare with the latest default-branch baseline, upload artifacts,
and update one idempotent PR comment.

**Pinned observed run**

| Input | Value |
|---|---|
| Repository | `lemduc/arcade-agent` |
| Commit | `24ab271d12f1db13250df95102a5722ae7f71f39` |
| Python | `3.12` for analysis; tests also run on `3.13` |
| Tool source | Checked-out source via `arcade-agent-version: "source"` |
| Source path | Repository root |
| Primary algorithm | `pkg` |
| Secondary algorithms | `acdc`, `wca` |
| Analysis profile | Self-dogfood helper filtering enabled |

Equivalent local input:

```bash
arcade-self-analysis \
  --source . \
  --algorithm pkg \
  --filter-non-architectural-helpers \
  --output-json arcade_analysis_results.json \
  --output-html arcade_analysis_report.html
```

**Expected invariants**

- the checked-out source, rather than a lagging PyPI release, performs analysis;
- primary and secondary analyses complete;
- JSON, HTML, comparison, and PR-comment artifacts are generated;
- a compatible default-branch baseline is used when available;
- PR comment updates are idempotent;
- the workflow does not turn architecture scores into a merge gate.

**Observed output**

| Output | Value |
|---|---:|
| Components | 10 |
| Entities | 125 |
| Edges | 127 |
| Balanced Architecture Score | 0.6283 |
| Principle Alignment Score | 0.8659 |
| Smells | 1 medium concern-overload finding |

These values describe the pinned run; they are not golden values for future
commits. Evidence:
[GitHub Actions run 30241970759](https://github.com/lemduc/arcade-agent/actions/runs/30241970759).

## RW-02 — ARCADE Core Java analysis

**Purpose:** exercise Java parsing and architecture recovery against the
upstream ARCADE Core workbench rather than a repository-shaped test fixture.

| Input | Value |
|---|---|
| Repository | `https://github.com/usc-softarch/arcade_core` |
| Ref | `v1.2.0` |
| Language | `java` |
| Surface | `examples/basic_analysis.py` |

```bash
git clone --branch v1.2.0 https://github.com/usc-softarch/arcade_core.git
python examples/basic_analysis.py arcade_core --language java
```

**Expected invariants**

- analysis completes without parser failure;
- the output contains non-empty entities, dependency edges, components, and
  smell findings;
- an HTML report is generated.

**Observed output**

| Output | Value |
|---|---:|
| Entities | 170 |
| Edges | 470 |
| Components | 13 |
| Architectural smells | 7 |

The committed example report is
[`examples/arcade_core_report.html`](../examples/arcade_core_report.html).
Because the repository ref is pinned, these values can be promoted to golden
assertions once this case is automated in CI.

## RW-03 — Spring Boot Multi-Region HA external action

**Purpose:** prove the consumer-facing composite action from outside the
arcade-agent repository, including PyPI installation, source scoping, baseline
artifact lookup, report upload, and PR-comment update.

**Pinned observed run**

| Input | Value |
|---|---|
| Repository | `tuannx/spring-boot-multi-region-ha` |
| Commit | `99d9d8efed40487136d387c85ae8dbbd3bdef16f` |
| arcade-agent package | `0.1.1` |
| Action ref | `3d7f6130b22050979d2d18084a63bc6a932b9789` |
| Source path | `app/src/main/java` |
| Language | `java` |
| Primary algorithm | `pkg` |
| Secondary algorithms | `acdc`, `wca` |

Consumer input:

```yaml
- name: Run arcade-agent
  uses: lemduc/arcade-agent/actions/analyze@3d7f6130b22050979d2d18084a63bc6a932b9789
  with:
    arcade-agent-version: "0.1.1"
    source-path: app/src/main/java
    language: java
    repo-name: spring-boot-multi-region-ha
    primary-algorithm: pkg
    run-secondary-analyses: "true"
```

**Expected invariants**

- the released package installs without checking out arcade-agent source;
- analysis produces non-empty Java entities, edges, and components;
- a main-branch run stores a baseline artifact;
- a pull-request run finds a compatible baseline and posts or updates one
  architecture comment;
- a non-architecture infrastructure-only change produces no fabricated source
  drift.

**Observed output**

| Output | Value |
|---|---:|
| Components | 19 |
| Entities | 239 |
| Edges | 510 |
| Classes | 31 |
| Methods | 189 |
| A2A similarity vs baseline | 1.0000 |

Evidence:
[consumer workflow](https://github.com/tuannx/spring-boot-multi-region-ha/blob/main/.github/workflows/arcade-agent-analysis.yml),
[GitHub Actions run 30187566024](https://github.com/tuannx/spring-boot-multi-region-ha/actions/runs/30187566024).

**Known gap:** this is valid independent-consumer evidence for `0.1.1`, not for
the current `0.2.0` release or the Java + Kotlin path.

## RW-04 — Embabel Java + Kotlin analysis

**Purpose:** validate large-repository JVM polyglot parsing and turn real parser
failures into durable regression cases.

Historical input shape:

```bash
arcade-self-analysis \
  --source /path/to/embabel-agent \
  --languages java,kotlin \
  --algorithm pkg \
  --output-json embabel-analysis.json \
  --output-html embabel-analysis.html
```

**Expected invariants**

- both Java and Kotlin entities are present;
- supported Java ↔ Kotlin import, extends, and implements edges are relinked;
- qualified external names never resolve to an unrelated local leaf name;
- annotation classes, backtick methods, property accessors, extension-only
  files, top-level values, and annotation-only files do not crash parsing;
- unsupported language-family relationships are not fabricated;
- unknown languages fail fast.

**Historical observed output**

| Output | Value |
|---|---:|
| Entities | 5,543 |
| Cross-language edges | 1,270 |
| Cross-language import edges | 1,265 |
| Cross-language implements edges | 5 |

These numbers are historical observations, not golden assertions: the original
Embabel commit was not recorded with the run. The durable evidence is the
reduced corpus under
[`tests/fixtures/kotlin_embabel_patterns`](../tests/fixtures/kotlin_embabel_patterns)
and its assertions in
[`tests/test_parsers/test_kotlin.py`](../tests/test_parsers/test_kotlin.py).

**Required follow-up:** pin an Embabel commit, rerun from a clean cache, and
record the JSON artifact before treating any count as a reproducible baseline.

## RW-05 — controlled Java + Kotlin E2E

**Purpose:** keep the core JVM multi-language contract deterministic and fast
enough for every pull request.

Inputs:

```python
repo = ingest(fixture_root, languages=["java", "kotlin"])
graph = parse(
    str(repo.path),
    languages=repo.languages,
    files=[str(path) for path in repo.source_files],
    use_cache=False,
)
architecture = recover(graph, algorithm="pkg")
```

The MCP variant passes the actual ingest session ID to `parse`; repeating the
fixture path is not accepted as proof of session chaining.

**Golden expectations**

- both language sets are present;
- `com.example.mixed.JavaBaseService` and
  `com.example.mixed.KotlinService` are present;
- the Maven fixture contains `com.example.JavaGreeter` and
  `com.example.KotlinGreeter`;
- `KotlinGreeter -> JavaGreeter` is an `extends` edge;
- recovery produces at least one non-empty component;
- invalid non-ingest session IDs fail with `ToolError`;
- default test-source exclusions and explicit overrides survive the
  `ingest -> parse` boundary.

Automated evidence:
[`tests/test_tools/test_pipeline_multilang_e2e.py`](../tests/test_tools/test_pipeline_multilang_e2e.py)
and
[`tests/test_mcp_multilang_e2e.py`](../tests/test_mcp_multilang_e2e.py).

## RW-06 — Python + Java family isolation

**Purpose:** prove that parsing multiple languages does not imply that every
language pair may be relinked.

Input:

```python
graph = parse(
    "tests/fixtures/python_java_mixed",
    languages=["python", "java"],
    use_cache=False,
)
```

**Golden expectations**

- Python and Java entities are both retained;
- no Python ↔ Java edge is fabricated from matching simple names;
- reversing language order produces the same serialized graph;
- single-language output remains compatible with the direct parser output.

Automated evidence:
[`tests/test_parsers/test_multilang_family_scoping.py`](../tests/test_parsers/test_multilang_family_scoping.py).

## RW-07 — Hermes clean-install MCP integration

**Purpose:** prove that an agent platform can install arcade-agent into a fresh
environment and discover its MCP tools.

| Input | Value |
|---|---|
| Consumer | `NousResearch/hermes-agent` MCP catalog |
| Consumer PR | `#63373` |
| Arcade ref | `d6956936fdb985116b101f51bfbd84d6fe221c07` |
| Python | `3.12` |
| Installation | Fresh clone, venv, `ensurepip`, then `pip install '.[mcp]'` |

**Expected invariants**

- prerequisites are checked before clone/install side effects;
- a fresh Python 3.12 venv can bootstrap `pip`;
- the MCP server starts and lists tools;
- all default tools are present:
  `compute_metrics`, `detect_smells`, `get_full_result`, `parse`, `recover`,
  and `summarize`.

**Historical observed output**

```text
tools=13
defaults_supported=[
  compute_metrics,
  detect_smells,
  get_full_result,
  parse,
  recover,
  summarize
]
missing=[]
```

Evidence:
[NousResearch/hermes-agent PR #63373](https://github.com/NousResearch/hermes-agent/pull/63373).

**Known gap:** the integration remains an open consumer PR and is not a
continuously running arcade-agent release canary.

## RW-08 — release-to-release architectural changelog

**Status:** in flight on
[arcade-agent PR #33](https://github.com/lemduc/arcade-agent/pull/33); it is not a
main-branch acceptance case yet.

**Purpose:** exercise git-ref ingestion, parse, recovery, provenance, and
changelog classification against immutable releases of arcade-agent itself.

Pinned inputs:

- `v0.1.1 -> v0.2.0` at default structural thresholds;
- `v0.1.0 -> v0.1.1` at both the historical low threshold and the proposed
  default threshold.

**Proposed golden expectations for `v0.1.1 -> v0.2.0`**

| Output | Value |
|---|---:|
| Components before | 9 |
| Components after | 9 |
| Entities before | 305 |
| Entities after | 331 |
| Responsibility shifts | 1 |
| Added/removed/renamed/split/merged components | none |

The low-threshold case intentionally reproduces an Algorithms/Tools
split-and-merge false positive; the default-threshold case must classify both
components as stable while preserving six entity-level shifts.

## Missing real-repository coverage

These cases should be added without implying support that has not been
demonstrated:

| ID | Proposed corpus | Languages | Minimum acceptance |
|---|---|---|---|
| RW-P01 | Pinned active TypeScript monorepo | TypeScript/JavaScript | Non-empty graph, workspace discovery, stable import edges, no generated/vendor leakage |
| RW-P02 | Pinned active Go modules repository | Go | Multi-module discovery, package/import edges, deterministic output |
| RW-P03 | Pinned C/C++ repository | C/C++ | Header/source discovery, include edges, no build/vendor leakage |
| RW-P04 | Pinned Rust workspace | Rust | Blocked until Rust parser support is merged and released |
| RW-P05 | Pinned three-language monorepo | Java + Kotlin + TypeScript or Go | JVM relinking only; unsupported pairs remain disconnected and are reported |
| RW-P06 | Released-package MCP canary | Python package + stdio MCP | Build wheel, fresh install, spawn `arcade-mcp`, call `ingest -> parse -> get_full_result` |
| RW-P07 | Current external action canary | Java + Kotlin | Use the current released action/package and verify push baseline plus PR delta/comment |

## Complex large open-source cases

The following cases turn the generic gaps above into concrete, immutable
large-repository inputs. Repository structure and commit SHAs were verified
from the upstream GitHub repositories on 2026-07-28.

They are **proposed acceptance cases**, not claims that arcade-agent has already
processed these revisions successfully. The first successful run must record
elapsed time, peak memory, discovered source-file counts, per-language entity
counts, edge counts by relation and language pair, cache behavior, and artifact
URLs.

### Large-case execution protocol

Every large case should use the same protocol:

1. Clone or create a worktree at the exact SHA with no uncommitted changes.
2. Remove `.arcade-cache/` and run a cold analysis.
3. Run the identical command again against the warm cache.
4. Serialize the full graph and compare deterministic fields between runs.
5. Record supported-language coverage and explicitly list ignored languages.
6. Inspect a sample of at least 20 resolved edges per supported relation and
   every cross-language edge.
7. Reduce every real defect to a small fixture before fixing production code.
8. Keep the large corpus in nightly/release CI unless measured runtime proves it
   is suitable for every pull request.

The initial run establishes a performance baseline; it must not invent a timeout
or memory threshold before measurement. Later runs may enforce a budget derived
from that pinned baseline with explicit headroom.

### RW-L01 — Apache Beam multi-SDK monorepo

| Input | Value |
|---|---|
| Repository | [`apache/beam`](https://github.com/apache/beam) |
| Commit | [`cae3e1749f28611055b9d952fb2ef2d6b3ecf605`](https://github.com/apache/beam/commit/cae3e1749f28611055b9d952fb2ef2d6b3ecf605) |
| Scope | `sdks/` |
| Supported languages under test | Java, Python, Go, TypeScript |
| Package shape | Dedicated `sdks/java`, `sdks/python`, `sdks/go`, and `sdks/typescript` trees |
| Cadence | Nightly and release candidate |

```bash
arcade-self-analysis \
  --source sdks \
  --languages java,python,go,typescript \
  --algorithm pkg \
  --output-json beam-analysis.json \
  --output-html beam-analysis.html
```

**Expected invariants**

- every requested language contributes non-zero entities;
- the Java, Python, Go, and TypeScript graphs are all retained in the union;
- Java simple names never resolve to same-named Python, Go, or TypeScript
  entities;
- reversing the requested language order does not change serialized graph
  content;
- `vendor`, generated output, build output, and test-only sources do not
  dominate the production graph;
- cold and warm runs produce the same architecture result;
- package recovery includes representative SDK packages from all four trees.

**Failure cases to pin**

- a same-named SDK abstraction in multiple languages creates a fabricated edge;
- a nested Gradle, Go module, or TypeScript workspace root is silently skipped;
- one language overwrites another language's entity with the same FQN;
- source discovery crosses into Beam's vendored dependencies.

### RW-L02 — Grafana frontend/backend monorepo

| Input | Value |
|---|---|
| Repository | [`grafana/grafana`](https://github.com/grafana/grafana) |
| Commit | [`7b868bedf0b54db6521f6d21aa381230a2fe92df`](https://github.com/grafana/grafana/commit/7b868bedf0b54db6521f6d21aa381230a2fe92df) |
| Scope | Repository root |
| Supported languages under test | Go, TypeScript/JavaScript |
| Package shape | 21 `apps/` entries, 19 `packages/` entries, 36 backend `pkg/` entries, and 17 `public/app/` entries |
| Cadence | Nightly |

```bash
arcade-self-analysis \
  --source . \
  --languages go,typescript \
  --exclude-dirs e2e-playwright \
  --algorithm pkg \
  --output-json grafana-analysis.json \
  --output-html grafana-analysis.html
```

**Expected invariants**

- both backend Go and frontend TypeScript/JavaScript entities are present;
- Go package imports and TypeScript module imports remain internally valid;
- no Go ↔ TypeScript edge is inferred from matching names alone;
- `apps`, `packages`, `pkg`, and `public/app` all contribute production
  entities;
- Yarn/Nx metadata, generated bundles, and Playwright fixtures do not appear as
  production architecture;
- repeated analysis at the same SHA is deterministic.

**Failure cases to pin**

- a frontend `Service` is linked to a Go `Service` by leaf name;
- JavaScript and TypeScript declarations collide during graph merge;
- generated frontend output overwhelms source entity counts;
- Go workspace packages outside the root `go.mod` are missed.

### RW-L03 — TensorFlow cross-runtime repository

| Input | Value |
|---|---|
| Repository | [`tensorflow/tensorflow`](https://github.com/tensorflow/tensorflow) |
| Commit | [`d146c6e3f0b04f3d771ff8adca5480736fc7527e`](https://github.com/tensorflow/tensorflow/commit/d146c6e3f0b04f3d771ff8adca5480736fc7527e) |
| Scope | `tensorflow/` |
| Supported languages under test | C/C++, Python, Go, Java |
| Package shape | 40 top-level TensorFlow entries including `c`, `cc`, `core`, `compiler`, `go`, `java`, `lite`, and `python` |
| Cadence | Scheduled scale test; not per-PR until measured |

```bash
arcade-self-analysis \
  --source tensorflow \
  --languages c,python,go,java \
  --algorithm pkg \
  --output-json tensorflow-analysis.json \
  --output-html tensorflow-analysis.html
```

**Expected invariants**

- all four requested language parsers complete without silently truncating the
  corpus;
- representative entities come from `core`/`cc`, `python`, `go`, and `java`;
- unsupported MLIR, Starlark, Objective-C, and Swift sources are explicitly
  outside this result rather than misclassified;
- unrelated same-named runtime APIs do not create cross-language edges;
- oversized source files are processed or reported explicitly, never silently
  skipped;
- the report remains serializable and bounded enough to upload as a CI
  artifact.

**Failure cases to pin**

- generated TensorFlow API surfaces are mistaken for independent production
  ownership;
- C/C++ header resolution creates excessive unresolved or self edges;
- Python wrapper names fabricate links to C++ implementation names;
- graph serialization or HTML generation fails at large entity counts.

### RW-L04 — Backstage package/plugin monorepo

| Input | Value |
|---|---|
| Repository | [`backstage/backstage`](https://github.com/backstage/backstage) |
| Commit | [`09c52f417ad77a96ce69720be48591669796cb32`](https://github.com/backstage/backstage/commit/09c52f417ad77a96ce69720be48591669796cb32) |
| Scope | Repository root |
| Supported language under test | TypeScript/JavaScript |
| Package shape | 71 package directories and 158 plugin directories |
| Cadence | Nightly and TypeScript parser release candidate |

```bash
arcade-self-analysis \
  --source . \
  --language typescript \
  --exclude-dirs docs,microsite \
  --algorithm pkg \
  --output-json backstage-analysis.json \
  --output-html backstage-analysis.html
```

**Expected invariants**

- both core packages and plugins contribute entities;
- workspace package boundaries survive recovery rather than collapsing into
  one generic component;
- TypeScript path aliases and package imports do not resolve to arbitrary leaf
  names;
- JavaScript compatibility files are included without duplicating equivalent
  TypeScript declarations;
- `node_modules`, generated docs, Storybook output, and build artifacts remain
  excluded;
- deterministic output is preserved across more than 200 package/plugin roots.

**Failure cases to pin**

- plugin packages with repeated `index.ts` or `types.ts` names collide;
- scoped package imports remain unresolved despite an in-repository target;
- barrel exports create duplicate or cyclic edges;
- one very large plugin component hides workspace boundaries.

### RW-L05 — Kubernetes staged Go modules

| Input | Value |
|---|---|
| Repository | [`kubernetes/kubernetes`](https://github.com/kubernetes/kubernetes) |
| Commit | [`8f19f1ec9349f516eb72e677a8ac2fa3fa930035`](https://github.com/kubernetes/kubernetes/commit/8f19f1ec9349f516eb72e677a8ac2fa3fa930035) |
| Scope | Repository root |
| Supported language under test | Go |
| Package shape | Main `cmd`, `pkg`, and `plugin` trees plus 33 staged `k8s.io` modules |
| Cadence | Nightly and Go parser release candidate |

```bash
arcade-self-analysis \
  --source . \
  --language go \
  --exclude-dirs vendor,test,third_party \
  --algorithm pkg \
  --output-json kubernetes-analysis.json \
  --output-html kubernetes-analysis.html
```

**Expected invariants**

- entities are discovered from `cmd`, `pkg`, `plugin`, and
  `staging/src/k8s.io`;
- staged modules are not treated as unrelated external packages;
- vendored copies do not duplicate first-party entities;
- generated files and test-only packages do not dominate the graph;
- internal package visibility and Go import paths remain deterministic;
- cache invalidation includes changes to module/workspace manifests.

**Failure cases to pin**

- `staging/src/k8s.io/client-go` resolves as external while its source is
  present;
- vendor and first-party packages share an FQN and overwrite one another;
- generated clients create a misleading architecture explosion;
- `go.work` or nested module changes leave a stale cached graph.

### RW-L06 — OpenTelemetry Collector Contrib component forest

| Input | Value |
|---|---|
| Repository | [`open-telemetry/opentelemetry-collector-contrib`](https://github.com/open-telemetry/opentelemetry-collector-contrib) |
| Commit | [`3148f0181c89d22ab16367e213a415957634029d`](https://github.com/open-telemetry/opentelemetry-collector-contrib/commit/3148f0181c89d22ab16367e213a415957634029d) |
| Scope | Repository root |
| Supported language under test | Go |
| Package shape | 113 receivers, 47 exporters, 35 processors, 14 connectors, and 31 extensions |
| Cadence | Nightly |

```bash
arcade-self-analysis \
  --source . \
  --language go \
  --algorithm pkg \
  --output-json otel-contrib-analysis.json \
  --output-html otel-contrib-analysis.html
```

**Expected invariants**

- every top-level component family contributes entities;
- repeated component conventions do not collapse distinct receivers,
  exporters, processors, connectors, or extensions;
- shared `internal` and `pkg` dependencies are linked without becoming
  fabricated ownership parents;
- generated configuration code and testbed fixtures are distinguishable from
  production component architecture;
- component counts and graph output remain deterministic at this package
  cardinality.

**Failure cases to pin**

- hundreds of repeated `factory`, `config`, and `client` names collide;
- common internal helpers become a false architecture super-component;
- a component directory is silently omitted because of nested module layout;
- HTML or Mermaid rendering generates duplicate node identifiers.

### RW-L07 — Elasticsearch modular server

| Input | Value |
|---|---|
| Repository | [`elastic/elasticsearch`](https://github.com/elastic/elasticsearch) |
| Commit | [`f758b3b4b6f99f19425757cf2563ae55d19035c0`](https://github.com/elastic/elasticsearch/commit/f758b3b4b6f99f19425757cf2563ae55d19035c0) |
| Scope | Repository root |
| Supported languages under test | Java primary; TypeScript and C/C++ inventory |
| Package shape | 35 `modules/` entries, 17 `plugins/` entries, 34 `libs/` entries, plus `server`, `client`, and `x-pack` |
| Cadence | Nightly |

Primary Java run:

```bash
arcade-self-analysis \
  --source . \
  --language java \
  --algorithm pkg \
  --output-json elasticsearch-java-analysis.json \
  --output-html elasticsearch-java-analysis.html
```

Polyglot inventory run:

```bash
arcade-self-analysis \
  --source . \
  --languages java,typescript,c \
  --algorithm pkg \
  --output-json elasticsearch-polyglot-analysis.json \
  --output-html elasticsearch-polyglot-analysis.html
```

**Expected invariants**

- the primary graph contains representative server, module, plugin, library,
  client, and x-pack entities;
- Gradle source-set and generated/test exclusions are applied consistently;
- the polyglot run retains Java, TypeScript, and C/C++ without inventing
  cross-family edges;
- Groovy and Rust are explicitly out of scope for the current released parser
  set;
- qualified Java parents never resolve through an unrelated simple-name local
  fallback.

**Failure cases to pin**

- repeated plugin implementation names collide across modules;
- test fixtures leak into the production architecture;
- x-pack and server packages with similar names are merged incorrectly;
- unsupported Rust files are silently reported as analyzed.

### RW-L08 — Visual Studio Code extension monorepo

| Input | Value |
|---|---|
| Repository | [`microsoft/vscode`](https://github.com/microsoft/vscode) |
| Commit | [`fc78dbeee6a6321383d67526c67dd13decaef78f`](https://github.com/microsoft/vscode/commit/fc78dbeee6a6321383d67526c67dd13decaef78f) |
| Scope | Repository root |
| Supported language under test | TypeScript/JavaScript |
| Package shape | 96 built-in extension directories plus `src/vs`, `remote`, and `cli` |
| Cadence | Nightly and TypeScript parser release candidate |

```bash
arcade-self-analysis \
  --source . \
  --language typescript \
  --exclude-dirs test,build \
  --algorithm pkg \
  --output-json vscode-analysis.json \
  --output-html vscode-analysis.html
```

**Expected invariants**

- core workbench code and built-in extensions both contribute entities;
- repeated extension entry-point and activation names remain package-scoped;
- JavaScript and TypeScript sources coexist without duplicate entity loss;
- tests, fixtures, vendored grammars, generated files, and packaged output do
  not dominate the graph;
- unsupported Rust/C++ native pieces are listed as excluded from this case;
- large Mermaid/HTML output uses stable, collision-free node identifiers.

**Failure cases to pin**

- 100+ extensions collapse into a single component;
- repeated `extension.ts`, `main.ts`, or `index.ts` files overwrite entities;
- tree-sitter grammar fixtures are mistaken for product source;
- path aliases or barrel exports create large false dependency cycles.

### RW-L09 — Apache Arrow C++/Python boundary

| Input | Value |
|---|---|
| Repository | [`apache/arrow`](https://github.com/apache/arrow) |
| Commit | [`2ae036fdb61149a969fc11c220ef1766cdf2a858`](https://github.com/apache/arrow/commit/2ae036fdb61149a969fc11c220ef1766cdf2a858) |
| Scope | Repository root |
| Supported languages under test | C/C++, Python |
| Package shape | Large `cpp/` and `python/` implementations plus C GLib, R, Ruby, and MATLAB bindings |
| Cadence | Nightly |

```bash
arcade-self-analysis \
  --source . \
  --languages c,python \
  --exclude-dirs docs,testing \
  --algorithm pkg \
  --output-json arrow-analysis.json \
  --output-html arrow-analysis.html
```

**Expected invariants**

- both C/C++ and Python contribute non-zero entities;
- `cpp` and `python` retain separate language graphs;
- matching Arrow API names do not create implicit Python ↔ C++ edges;
- Cython, R, Ruby, MATLAB, Vala, and build-language inputs are explicitly
  outside the supported result;
- generated bindings and third-party sources remain distinguishable from
  first-party architecture;
- header/include resolution is stable across the large C++ tree.

**Failure cases to pin**

- Python wrappers fabricate links to same-named C++ classes;
- generated Cython output is parsed as first-party C/C++ ownership;
- local and third-party Arrow headers collide;
- unresolved includes or graph size make report generation fail.

## Large-case result record

The first execution of each `RW-Lxx` case must append a result block without
rewriting the expected contract:

```yaml
case: RW-L01
input_commit: cae3e1749f28611055b9d952fb2ef2d6b3ecf605
arcade_version: source SHA or released version
verified_at: YYYY-MM-DD
environment:
  os: ubuntu-24.04
  python: "3.12"
  cpu: description
  memory_gb: number
discovery:
  files_by_language: {}
result:
  entities_by_language: {}
  edges_by_relation: {}
  cross_language_edges: {}
  components: 0
  smells_by_type: {}
performance:
  cold_seconds: 0
  warm_seconds: 0
  peak_memory_mb: 0
artifacts:
  json: URL
  html: URL
  log: URL
invariants:
  passed: []
  failed: []
notes: []
```

### Executable manifest and CI runner

The pinned inputs above are machine-readable in
[`docs/real-world-cases.json`](real-world-cases.json). The runner is
[`scripts/run_real_world_case.py`](../scripts/run_real_world_case.py), and the
GitHub Actions entry point is
[`real-world-analysis.yml`](../.github/workflows/real-world-analysis.yml).

Validate and list cases locally:

```bash
python scripts/run_real_world_case.py list
```

Preview the bounded GitHub Actions matrix:

```bash
# One deterministic case from the weekly rotation
python scripts/run_real_world_case.py matrix --selection scheduled

# A specific case or every pinned case
python scripts/run_real_world_case.py matrix --selection RW-L02
python scripts/run_real_world_case.py matrix --selection all
```

Run one case immediately:

```bash
python scripts/run_real_world_case.py run \
  --case RW-L02 \
  --output-dir real-world-results/RW-L02
```

The runner performs a partial sparse checkout at the exact SHA, removes the
case-local cache, runs cold and warm analyses, checks deterministic stable
fields, captures GNU `time` peak RSS on Linux, and writes `result.json` even
when checkout or analysis fails.

The workflow is intentionally absent from `pull_request`. Manual
`workflow_dispatch` runs are immediate and may select one case or all cases;
the schedule rotates one case per week. The matrix uses `fail-fast: false`,
`max-parallel: 2`, per-case timeouts, and unconditional artifact upload so a
large-repository failure remains diagnosable without creating unbounded CI
load.

After the workflow exists on the default branch, trigger a live case with:

```bash
gh workflow run real-world-analysis.yml \
  --ref main \
  -f case=RW-L02 \
  -f skip-warm=false \
  -f campaign-title="Grafana architecture evidence" \
  -f upstream-pr-url="https://github.com/grafana/grafana/pull/NNNN"
```

Use `skip-warm=true` only for a quick infrastructure smoke. A completed
acceptance run requires cold/warm determinism evidence.

### Public evidence and upstream PR workflow

Each matrix job publishes a full Markdown report directly to the GitHub Actions
run summary. The public CI page includes:

- the upstream repository and immutable commit links;
- the exact `arcade-agent` source commit used by the workflow;
- exact source scope, languages, algorithm, and reproduction command;
- graph size, recovered components, architecture quality signals, and score
  drivers;
- prioritized architectural review leads with suggested directions;
- the largest recovered components;
- cold/warm duration, peak RSS, and deterministic-output evidence;
- a link to the related upstream PR when `upstream-pr-url` is supplied;
- an explicit independent-analysis and non-endorsement disclosure.

The uploaded artifact retains `report.md`, `share-comment.md`, raw JSON,
interactive HTML, checkout and analysis logs, and timing data for 90 days
(subject to the repository's Actions retention policy).
`share-comment.md` is deliberately short and can be pasted into the focused
upstream PR so reviewers can follow the link back to the public, reproducible
CI evidence.

The workflow does **not** post automatically to external repositories.
Cross-repository commenting would require a separately managed token with write
access and would create an avoidable trust and spam risk. The default flow keeps
the evidence public and independently reproducible while leaving the PR author
in control of when the contextual note is appropriate. Automatic posting can be
added later only as an explicit opt-in integration for repositories that have
granted access.

An Actions run is evidence, not permanent hosting. Promote selected reports to
versioned documentation or a case-study site before the repository's workflow
retention window expires; keep the original run URL in that page for
provenance.

## Contract for adding a case

Every new case must record this data:

```yaml
id: RW-XX
status: automated | live-external | historical-verified | regression-fixture | proposed
purpose: What product or correctness claim this case proves
input:
  repository: owner/name or fixture path
  ref: immutable tag or commit SHA
  arcade_version: released version, source SHA, or source-under-review
  language: java
  languages: []
  source_path: .
  exclusions: []
  algorithm: pkg
  surface: direct-api | cli | mcp-stdio | github-action
command_or_workflow: Exact reproducible invocation
expected:
  invariants: []
  exact_values: {} # only for immutable inputs
  failure_behavior: []
observed:
  verified_at: YYYY-MM-DD
  output_summary: {}
  artifact_url: URL or committed artifact path
limitations: []
```

### Assertion policy

Use **exact values** only for immutable fixtures, tags, or commit SHAs. For an
evolving default branch, assert:

- successful completion and required artifact creation;
- deterministic output for identical inputs;
- presence of required languages and known representative entities;
- presence or absence of supported/unsupported cross-language relationships;
- explicit errors for invalid input;
- bounded performance or output size when a measured budget exists.

Do not assert that an absolute smell count or Balanced Architecture Score is
universally “good.” Compare a pull request with a compatible pinned baseline and
surface the reasons for change.

## Source-of-truth order

When evidence disagrees, use this order:

1. a currently green automated test on a pinned input;
2. a successful external workflow with downloadable artifacts;
3. a committed generated artifact tied to a tag or SHA;
4. a historical run note;
5. documentation without executable evidence.

Historical observations must never be silently promoted to current claims.
