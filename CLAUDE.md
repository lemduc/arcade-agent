# CLAUDE.md

## What This Is

arcade-agent is a framework-agnostic tool library for software architecture analysis. It provides composable tools for parsing source code, recovering architecture, detecting smells, computing metrics, and comparing versions. Tools work standalone or plug into MCP/LangChain/Claude SDK.

## Quick Reference

```bash
# Setup
cd arcade-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Example usage
python examples/basic_analysis.py /path/to/java/project
```

## Architecture

Tool library with registry pattern — no pipeline, no CLI orchestrator. Each tool is independently callable.

```
registry.py          # @tool decorator, discovery
parsers/             # Language-agnostic parsing (tree-sitter)
models/              # Shared dataclasses (DependencyGraph, Architecture, etc.)
tools/               # 8 composable tools (ingest, parse, recover, detect_smells, ...)
algorithms/          # Pure algorithm implementations (clustering, SCC, metrics)
exporters/           # Output format adapters (HTML, DOT, JSON, RSF, Mermaid)
adapters/            # Framework integration (MCP stub for v2)
```

## Key Domain Objects

All `@dataclass` in `models/`:

- `Entity` — FQN, kind, package, file path, language, imports, inheritance
- `Edge` — source FQN, target FQN, relation type
- `DependencyGraph` — entities dict, edges list, packages dict
- `Component` — name, responsibility, entity FQNs
- `Architecture` — components list, rationale, algorithm used, metadata
- `SmellInstance` — smell type, severity, affected components, description, explanation, suggestion
- `MetricResult` — metric name, value, details dict

## Tool Registry

```python
from arcade_agent import list_tools, get_tool

# Discover all tools
for t in list_tools():
    print(t.name, t.description)

# Call a tool directly
from arcade_agent.tools.parse import parse
graph = parse("/path/to/project", language="java")
```

## Dependencies

- `tree-sitter` + language grammars for parsing
- `networkx` for graph algorithms (SCC, clustering)
- `scipy` for Hungarian algorithm (cluster matching)
- `numpy` for numerical metric computations
- `jinja2` for HTML report templating
- `gitpython` for repo ingestion

## Coding Conventions

- **Python 3.12+** — PEP 585: `list[str]`, `str | None`
- **Type hints** on all functions and return types
- **@dataclass** for domain objects
- **Naming**: `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE_CASE` constants, `_underscore` private
- **Docstrings**: Google style with Args/Returns
- **Imports**: stdlib → third-party → local (`from arcade_agent.models.graph import ...`)
- **Linting**: ruff, mypy strict mode
- **Testing**: pytest, fixtures in `tests/fixtures/`
