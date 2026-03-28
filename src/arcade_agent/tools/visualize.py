"""Tool: Generate reports and diagrams."""

from pathlib import Path

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.exporters.dot import export_dot
from arcade_agent.exporters.html import export_html
from arcade_agent.exporters.json import export_json
from arcade_agent.exporters.mermaid import build_mermaid_diagram
from arcade_agent.exporters.rsf import export_rsf
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool


@tool(
    name="visualize",
    description=(
        "Generate architecture reports and diagrams "
        "in HTML, DOT, JSON, RSF, or Mermaid format."
    ),
)
def visualize(
    repo_name: str,
    version: str,
    dep_graph: DependencyGraph,
    architecture: Architecture,
    smells: list[SmellInstance] | None = None,
    metrics: list[MetricResult] | None = None,
    output: str = "report.html",
    format: str | None = None,
    concerns: dict[str, list[str]] | None = None,
) -> str:
    """Generate a visualization of the architecture analysis.

    Args:
        repo_name: Repository name.
        version: Version string.
        dep_graph: The dependency graph.
        architecture: The recovered architecture.
        smells: Detected architectural smells.
        metrics: Computed quality metrics.
        output: Output file path.
        format: Output format (html, dot, json, rsf, mermaid). Auto-detected from extension.
        concerns: Optional dict mapping component name to concern labels (LLM-extracted).

    Returns:
        Path to the generated output file (or content string for mermaid).
    """
    if smells is None:
        smells = []
    if metrics is None:
        metrics = []

    output_path = Path(output)

    # Auto-detect format from extension
    if format is None:
        ext_map = {".html": "html", ".dot": "dot", ".json": "json", ".rsf": "rsf", ".md": "mermaid"}
        format = ext_map.get(output_path.suffix, "html")

    if format == "html":
        export_html(
            repo_name, version, dep_graph, architecture,
            smells, metrics, output_path, concerns=concerns,
        )
    elif format == "dot":
        content = export_dot(architecture, dep_graph)
        output_path.write_text(content)
    elif format == "json":
        content = export_json(dep_graph, architecture, smells, metrics)
        output_path.write_text(content)
    elif format == "rsf":
        content = export_rsf(architecture)
        output_path.write_text(content)
    elif format == "mermaid":
        content = build_mermaid_diagram(architecture, dep_graph)
        output_path.write_text(content)
    else:
        raise ValueError(f"Unknown format: {format}. Use: html, dot, json, rsf, mermaid")

    return str(output_path)
