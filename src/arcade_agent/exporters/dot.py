"""GraphViz DOT format export."""

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph


def _escape_dot(s: str) -> str:
    """Escape a string for DOT labels."""
    return s.replace('"', '\\"').replace("\n", "\\n")


def export_dot(
    architecture: Architecture,
    dep_graph: DependencyGraph,
) -> str:
    """Export architecture as a GraphViz DOT diagram.

    Args:
        architecture: The recovered architecture.
        dep_graph: The dependency graph.

    Returns:
        DOT format string.
    """
    lines = [
        "digraph architecture {",
        "    rankdir=TB;",
        '    node [shape=box, style=filled, fillcolor="#e8f0fe", fontname="Helvetica"];',
        '    edge [color="#666666"];',
        "",
    ]

    for comp in architecture.components:
        node_id = comp.name.replace(" ", "_").replace("-", "_")
        label = _escape_dot(f"{comp.name}\\n({len(comp.entities)} entities)")
        lines.append(f'    {node_id} [label="{label}"];')

    lines.append("")

    comp_deps = architecture.component_dependencies(dep_graph)
    for src, tgt in comp_deps:
        src_id = src.replace(" ", "_").replace("-", "_")
        tgt_id = tgt.replace(" ", "_").replace("-", "_")
        lines.append(f"    {src_id} -> {tgt_id};")

    lines.append("}")
    return "\n".join(lines)
