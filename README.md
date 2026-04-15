# arcade-agent

[![CI](https://github.com/lemduc/arcade-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/lemduc/arcade-agent/actions/workflows/ci.yml)

Framework-agnostic tool library for software architecture analysis.

Provides composable tools for parsing source code, recovering architecture, detecting architectural smells, computing quality metrics, and comparing versions. Works standalone or plugs into MCP, LangChain, or Claude SDK.

## Install

```bash
pip install -e ".[dev]"

# With MCP server support (for AI agent integration)
pip install -e ".[mcp,dev]"
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

## MCP Server (AI Agent Integration)

arcade-agent exposes all tools via the [Model Context Protocol](https://modelcontextprotocol.io/) so AI agents (Claude Code, Cursor, etc.) can analyze codebases with minimal token usage.

### Start the server

```bash
arcade-mcp
```

### Configure in Claude Code

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "arcade-agent": {
      "command": "arcade-mcp"
    }
  }
}
```

### How it works

1. **Session store** — Tools like `parse` and `recover` return compact summaries with a `session_id`. Pass session IDs to downstream tools instead of full data objects.
2. **Token budget** — Every tool accepts an optional `max_tokens` parameter. Outputs are progressively truncated (entity details → edge summaries → component counts) to fit.
3. **Parse caching** — Parsed dependency graphs are cached to `.arcade-cache/` keyed by file modification times. Repeated analysis of the same codebase skips re-parsing.
4. **On-demand detail** — Call `get_full_result(session_id)` to retrieve complete data when the summary isn't enough.

### Example agent workflow

```
Agent: call parse(source_path="/path/to/project")
       → {session_id: "a1b2c3", num_entities: 170, num_edges: 470, ...}

Agent: call recover(dep_graph="a1b2c3", algorithm="pkg")
       → {session_id: "d4e5f6", num_components: 13, components: [...], ...}

Agent: call detect_smells(architecture="d4e5f6", dep_graph="a1b2c3")
       → {num_smells: 7, smells: [...]}

Agent: call get_full_result(session_id="a1b2c3", max_tokens=2000)
       → full graph data, truncated to fit token budget
```

## LLM-Powered Analysis

Pass `--use-llm` to enable Claude-powered concern detection. Requires the `claude` CLI installed and authenticated.

```bash
python examples/basic_analysis.py arcade_core --language java --use-llm
```

This replaces heuristic smell detection (entity count thresholds, suffix matching) with semantic analysis that identifies *what* concerns each component handles and *why* they are problematic. Set `ARCADE_MOCK=1` to skip LLM calls, or `ARCADE_MODEL=haiku` to use a faster model.

## CI/CD Integration

arcade-agent ships with a GitHub Action that detects architecture drift on every PR — like SonarQube for architecture.

### How It Works

1. On **pull request**: parses the codebase, recovers architecture (PKG), compares against a stored baseline, and posts a PR comment with a drift report.
2. On **push to main**: updates the baseline (`.arcade/baseline.json`) so future PRs compare against the latest merged state.

### Setup

Copy `.github/workflows/arch-drift.yml` into your repository. The workflow auto-detects the language, or you can set it explicitly via the `language` workflow input.

```yaml
# .github/workflows/arch-drift.yml is included in the repo — just enable Actions.
```

The baseline is stored in `.arcade/baseline.json` and committed to the repo automatically when changes are pushed to `main`.

### Local Usage

Run the drift detection script locally:

```bash
# Analyze without a baseline (first run)
python scripts/arch_diff.py --source /path/to/project --language java

# Update the baseline
python scripts/arch_diff.py --source /path/to/project --language java --update-baseline

# Compare against existing baseline
python scripts/arch_diff.py --source /path/to/project --language java
```

### PR Comment Format

The action posts a comment with:
- **Drift table** — component count, similarity score, RCI, TurboMQ deltas
- **Changes** — added/removed components, entity movements, splits/merges
- **Smells** — dependency cycles, concern overload, scattered functionality

The comment is updated on each push to the PR (not duplicated).

## Roadmap

arcade-agent ports and extends the capabilities of the original [ARCADE](https://github.com/usc-softarch/arcade_core) Java workbench, and is evolving into a token-efficient codebase understanding layer for AI agents. See [ROADMAP.md](ROADMAP.md) for the full AI agent integration roadmap.

| Feature | Status | Details |
|---------|--------|---------|
| 5 recovery algorithms (PKG, WCA, ACDC, ARC, LIMBO) | Done | Package-based, weighted clustering, pattern-based, LLM concern-based, information-theoretic |
| 4 smell types (BDC, BCO, SPF, BUO) | Done | Heuristic + LLM-powered detection |
| 6 quality metrics | Done | RCI, TurboMQ, BasicMQ, IntraConnectivity, InterConnectivity, TwoWayPairRatio |
| A2A architecture comparison | Done | Hungarian algorithm on Jaccard similarity |
| Multi-language parsing | Done | Java, Python, C/C++ (full), TypeScript (stub) |
| 5 export formats | Done | HTML, DOT, JSON, RSF, Mermaid |
| LLM concern extraction | Done | Claude CLI for semantic BCO/SPF detection |
| MCP server | Done | Expose tools to AI agents via Model Context Protocol with session store |
| Token-budget truncation | Done | Progressive output reduction to fit agent context windows |
| Parse result caching | Done | Mtime-based cache avoids re-parsing unchanged codebases |
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
