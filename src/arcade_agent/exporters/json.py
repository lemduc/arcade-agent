"""JSON export for architecture analysis results."""

import json
from collections import Counter
from dataclasses import asdict
from typing import Iterable

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph, Entity


def summarize_entity_kinds(entities: Iterable[Entity]) -> dict[str, int]:
    """Count entities by kind and expose common rollups."""
    kind_counts = Counter(entity.kind for entity in entities)
    summary = dict(sorted(kind_counts.items()))
    summary["class_count"] = kind_counts.get("class", 0)
    summary["function_count"] = kind_counts.get("function", 0)
    summary["method_count"] = kind_counts.get("method", 0)
    return summary


def build_component_summary(
    component: Component,
    dep_graph: DependencyGraph,
    stats_graph: DependencyGraph | None = None,
) -> dict:
    """Build a JSON-friendly component summary with derived counts."""
    if stats_graph is None:
        stats_graph = dep_graph

    component_entity_keys = set(component.entities)
    component_entities = []
    for fqn, entity in stats_graph.entities.items():
        owner = entity.properties.get("owner")
        if fqn in component_entity_keys or owner in component_entity_keys:
            component_entities.append(entity)

    kind_summary = summarize_entity_kinds(component_entities)
    return {
        "name": component.name,
        "responsibility": component.responsibility,
        "num_entities": len(component.entities),
        "class_count": kind_summary["class_count"],
        "function_count": kind_summary["function_count"],
        "method_count": kind_summary["method_count"],
        "entity_kind_counts": {
            key: value
            for key, value in kind_summary.items()
            if key not in {"class_count", "function_count", "method_count"}
        },
        "entities": component.entities,
    }


def build_graph_summary(dep_graph: DependencyGraph) -> dict:
    """Build a JSON-friendly dependency graph summary with derived counts."""
    kind_summary = summarize_entity_kinds(dep_graph.entities.values())
    return {
        "num_entities": dep_graph.num_entities,
        "num_edges": dep_graph.num_edges,
        "class_count": kind_summary["class_count"],
        "function_count": kind_summary["function_count"],
        "method_count": kind_summary["method_count"],
        "entity_kind_counts": {
            key: value
            for key, value in kind_summary.items()
            if key not in {"class_count", "function_count", "method_count"}
        },
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
    }


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
    graph_summary = build_graph_summary(dep_graph)
    data = {
        "graph": graph_summary,
        "architecture": {
            "algorithm": architecture.algorithm,
            "rationale": architecture.rationale,
            "component_dependencies": [
                {"source": source, "target": target}
                for source, target in architecture.component_dependencies(dep_graph)
            ],
            "components": [
                build_component_summary(c, dep_graph)
                for c in architecture.components
            ],
        },
    }

    if smells:
        data["smells"] = [asdict(s) for s in smells]

    if metrics:
        data["metrics"] = [asdict(m) for m in metrics]

    return json.dumps(data, indent=2)
