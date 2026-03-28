"""JSON export for architecture analysis results."""

import json
from dataclasses import asdict

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph


def export_json(
    dep_graph: DependencyGraph,
    architecture: Architecture,
    smells: list[SmellInstance] | None = None,
    metrics: list[MetricResult] | None = None,
) -> str:
    """Export analysis results as JSON.

    Args:
        dep_graph: The dependency graph.
        architecture: The recovered architecture.
        smells: Detected architectural smells.
        metrics: Computed quality metrics.

    Returns:
        JSON string.
    """
    data = {
        "graph": {
            "num_entities": dep_graph.num_entities,
            "num_edges": dep_graph.num_edges,
            "entities": {
                fqn: {
                    "name": e.name,
                    "package": e.package,
                    "kind": e.kind,
                    "language": e.language,
                    "file_path": e.file_path,
                }
                for fqn, e in dep_graph.entities.items()
            },
            "edges": [
                {"source": e.source, "target": e.target, "relation": e.relation}
                for e in dep_graph.edges
            ],
            "packages": dep_graph.packages,
        },
        "architecture": {
            "algorithm": architecture.algorithm,
            "rationale": architecture.rationale,
            "components": [
                {
                    "name": c.name,
                    "responsibility": c.responsibility,
                    "entities": c.entities,
                }
                for c in architecture.components
            ],
        },
    }

    if smells:
        data["smells"] = [asdict(s) for s in smells]

    if metrics:
        data["metrics"] = [asdict(m) for m in metrics]

    return json.dumps(data, indent=2)
