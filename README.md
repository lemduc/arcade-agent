# arcade-agent

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
| `recover` | Recover architecture (package-based, WCA, ACDC) |
| `detect_smells` | Find dependency cycles, concern overload, scattered functionality, link overload |
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

See [`examples/arcade_core_report.html`](examples/arcade_core_report.html) for the full interactive report.
