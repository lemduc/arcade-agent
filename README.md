# arcade-agent

[![CI](https://github.com/lemduc/arcade-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/lemduc/arcade-agent/actions/workflows/ci.yml)

Framework-agnostic tool library for software architecture analysis.

Provides composable tools for parsing source code, recovering architecture, detecting architectural smells, computing quality metrics, and comparing versions. Works standalone or plugs into MCP, LangChain, or Claude SDK.

## Install

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from arcade_agent.tools.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.visualize import visualize

# 1. Ingest a project
repo = ingest("/path/to/java/project")

# 2. Parse dependencies
graph = parse(repo.path, language="java")

# 3. Recover architecture
arch = recover(graph, algorithm="pkg")

# 4. Detect smells
smells = detect_smells(arch, graph)

# 5. Compute metrics
metrics = compute_metrics(arch, graph)

# 6. Generate report
visualize(repo.name, repo.version, graph, arch, smells, output="report.html")
```

## Tools

| Tool | Description |
|------|-------------|
| `ingest` | Clone/load source code, detect versions, discover files |
| `parse` | Parse source → DependencyGraph via tree-sitter |
| `recover` | Recover architecture (PKG, WCA, ACDC, ARC, LIMBO) |
| `detect_smells` | Find dependency cycles, concern overload, scattered functionality, link overload (heuristic or LLM-powered) |
| `compute_metrics` | Calculate RCI, TurboMQ, connectivity metrics |
| `compare` | A2A architecture comparison across versions |
| `visualize` | Generate HTML reports, DOT, Mermaid, JSON, RSF |
| `query` | Explore recovered architecture interactively |

## Supported Languages

- Java (full support)
- Python (full support)
- C/C++ (full support)
- TypeScript/JavaScript (stub — contributions welcome)

## Example: ARCADE Core

[ARCADE Core](https://github.com/usc-softarch/arcade_core) is a Java-based architecture recovery workbench from USC's Software Architecture Research Group. Running arcade-agent against it:

```bash
git clone https://github.com/usc-softarch/arcade_core.git
python examples/basic_analysis.py arcade_core --language java
```

Results (v1.2.0): 170 entities, 470 edges, 13 components recovered, 7 architectural smells detected (including a 7-component dependency cycle and concern overload in the Clustering module).

See [`examples/arcade_core_report.html`](https://lemduc.github.io/arcade-agent/examples/arcade_core_report.html) for the full interactive report.

### Algorithm Comparison

Compare PKG, ACDC, ARC, and LIMBO recovery algorithms side-by-side on the same project:

```bash
python examples/compare_algorithms.py arcade_core --language java --use-llm
```

See [`examples/comparison_report.html`](https://lemduc.github.io/arcade-agent/examples/comparison_report.html) for the full comparison report.

## LLM-Powered Analysis

Pass `--use-llm` to enable Claude-powered concern detection. Requires the `claude` CLI installed and authenticated.

```bash
python examples/basic_analysis.py arcade_core --language java --use-llm
```

This replaces heuristic smell detection (entity count thresholds, suffix matching) with semantic analysis that identifies *what* concerns each component handles and *why* they are problematic. Set `ARCADE_MOCK=1` to skip LLM calls, or `ARCADE_MODEL=haiku` to use a faster model.

## Reusable GitHub Workflow

This repository exposes a reusable GitHub Actions workflow at `.github/workflows/architecture-analysis-reusable.yml` so other repositories can integrate architecture evaluation with one job.

Current implementation uses **PA1 (dual checkout)**:

- Checkout target repository source code for analysis.
- Checkout the tooling repository (this repo by default) to access `scripts/run_self_analysis.py`, `scripts/compare_baseline.py`, and related helpers.

Minimal caller workflow:

```yaml
name: Architecture Analysis

on:
  pull_request:
  push:
    branches: [main]

jobs:
  architecture:
    uses: lemduc/arcade-agent/.github/workflows/architecture-analysis-reusable.yml@<release-tag-or-commit-sha>
    with:
      source-path: .
      primary-algorithm: pkg
      baseline-workflow-id: ci.yml
      tooling-repository: lemduc/arcade-agent
      tooling-ref: <release-tag-or-commit-sha>
    secrets: inherit
```

Notes:

- `baseline-workflow-id` should match the caller workflow filename where baseline artifacts are produced.
- Prefer pinning to a release tag or commit SHA instead of `@main`.
- The reusable workflow already handles PR comment updates, artifact upload, and baseline refresh on `main` pushes.

## Roadmap

arcade-agent ports and extends the capabilities of the original [ARCADE](https://github.com/usc-softarch/arcade_core) Java workbench. Below is what has been implemented and what remains.

| Feature | Status | Details |
|---------|--------|---------|
| 5 recovery algorithms (PKG, WCA, ACDC, ARC, LIMBO) | Done | Package-based, weighted clustering, pattern-based, LLM concern-based, information-theoretic |
| 4 smell types (BDC, BCO, SPF, BUO) | Done | Heuristic + LLM-powered detection |
| 6 quality metrics | Done | RCI, TurboMQ, BasicMQ, IntraConnectivity, InterConnectivity, TwoWayPairRatio |
| A2A architecture comparison | Done | Hungarian algorithm on Jaccard similarity |
| Multi-language parsing | Done | Java, Python, C/C++ (full), TypeScript (stub) |
| 5 export formats | Done | HTML, DOT, JSON, RSF, Mermaid |
| LLM concern extraction | Done | Claude CLI for semantic BCO/SPF detection |
| Multi-version evolution pipeline | Planned | Batch version history analysis, A2A cost trends, CVG over time |
| Flexible stopping criteria | Planned | `no_orphans`, `size_fraction` strategies for WCA/ARC/LIMBO |
| Additional similarity measures | Planned | UEMNM (normalized UEM) and InfoLoss |
| Architectural Stability metric | Planned | Fan-in/fan-out ratio |
| MCFP-based comparison | Planned | Minimum Cost Flow for accurate entity movement cost |
| Design decision recovery (RecovAr) | Planned | Link issue trackers to architectural changes |

## Comparison with ARCADE Core

arcade-agent is a Python successor to the original [ARCADE Core](https://github.com/usc-softarch/arcade_core) Java workbench. The table below compares capabilities across both projects.

### High Value

| Feature | ARCADE Core (Java) | arcade-agent (Python) | Notes |
|---------|--------------------|-----------------------|-------|
| LIMBO algorithm | Full | Done (LLM-powered) | Uses Claude CLI concern vectors + size-weighted JS divergence |
| ARC algorithm | Full (concern-based) | Done (LLM-powered) | Uses Claude CLI concern vectors + JS divergence instead of MALLET topics |
| Topic modeling (MALLET) | Full (50 topics, 250 iterations) | LLM-based | arcade-agent uses Claude CLI instead of MALLET for semantic concern analysis |
| Evolution metrics (A2A cost, CVG) | MCFP-based movement cost, coverage | Basic Jaccard comparison | Core computes actual entity movement costs and bidirectional coverage |
| Multi-version batch analysis | VersionMap, VersionTree, batch processing | Single-pair compare | Core can process entire version histories and track trends |
| Stopping/serialization criteria | 3 stopping + 4 serialization strategies | Hardcoded target cluster count | Flexible termination (no-orphans, size-fraction) would improve clustering |
| Similarity measures | 11 (UEMNM, InfoLoss, WeightedJS, ARC variants) | 3 (JS, UEM, SCM) | More measures = better tuning per project type |

### Medium Value

| Feature | ARCADE Core (Java) | arcade-agent (Python) | Notes |
|---------|--------------------|-----------------------|-------|
| Architectural Stability metric | Fan-in/fan-out ratio | Missing | Simple addition to existing 6 metrics |
| Concern-based smell detection | Topic distributions for BCO and SPF | LLM-powered (Claude CLI) | Heuristic fallback also available |
| Cluster matching (MCFP) | Minimum Cost Flow for movement cost | Hungarian algorithm on Jaccard | MCFP gives more accurate evolution cost |
| ODEM input format | XML-based dependency parsing | Missing | Academic interchange format, limited real-world use |
| SmellToIssuesCorrelation | Correlates smells with issue tracker data | Missing | Requires issue tracker integration |

### Lower Priority

| Feature | ARCADE Core (Java) | arcade-agent (Python) | Notes |
|---------|--------------------|-----------------------|-------|
| RecovAr (Design Decision Recovery) | Full engine (GitLab issues/commits) | Missing | Large scope research feature |
| Issue tracker integration | JIRA + GitLab REST clients | Missing | Needed for RecovAr or SmellToIssues |
| Swing GUI | Full desktop visualization | HTML reports + CLI | HTML/Mermaid is more modern |
| Classycle bytecode analysis | Java bytecode dependency extraction | tree-sitter source parsing | tree-sitter is arguably better (no compilation needed) |
| Make dependency / Understand CSV | C-specific input formats | Missing | Niche; tree-sitter C parser covers the core need |
