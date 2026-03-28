"""Mermaid.js diagram generation."""

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph


def _node_id(name: str) -> str:
    """Sanitize a component name for Mermaid node IDs."""
    nid = name.replace(" ", "_").replace("-", "_").replace(".", "_")
    # Remove any chars that aren't alphanumeric or underscore
    nid = "".join(c for c in nid if c.isalnum() or c == "_")
    return nid or "unnamed"


def build_mermaid_diagram(
    architecture: Architecture,
    dep_graph: DependencyGraph,
) -> str:
    """Build a Mermaid.js flowchart of the architecture.

    Args:
        architecture: The recovered architecture.
        dep_graph: The dependency graph.

    Returns:
        Mermaid diagram source string.
    """
    lines = ["graph TD"]

    for comp in architecture.components:
        nid = _node_id(comp.name)
        label = f"{comp.name}\\n({len(comp.entities)} entities)"
        lines.append(f"    {nid}[\"{label}\"]")

    comp_deps = architecture.component_dependencies(dep_graph)
    seen_edges: set[tuple[str, str]] = set()
    for src, tgt in comp_deps:
        edge_key = (_node_id(src), _node_id(tgt))
        if edge_key not in seen_edges:
            lines.append(f"    {edge_key[0]} --> {edge_key[1]}")
            seen_edges.add(edge_key)

    return "\n".join(lines)
