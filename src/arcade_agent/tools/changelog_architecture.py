"""Tool: architectural changelog between two versions of a codebase."""

from typing import Any

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.provenance import (
    classify_structural_changes,
    structural_dict,
)
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.display import display_value
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.registry import tool


def _smell_key(
    smell: SmellInstance, rename_map: dict[str, str] | None = None
) -> tuple[str, tuple[str, ...]]:
    """Identity of a smell, with component names optionally normalised."""
    components = smell.affected_components
    if rename_map:
        components = [rename_map.get(name, name) for name in components]
    return smell.smell_type, tuple(sorted(components))


def _smell_dict(smell: SmellInstance) -> dict[str, Any]:
    """Compact serialisable view of a smell."""
    return {
        "smell_type": display_value(smell.smell_type),
        "severity": smell.severity,
        "affected_components": sorted(smell.affected_components),
        "description": smell.description,
    }


def _languages(graph: DependencyGraph) -> list[str]:
    """Sorted distinct languages present in a dependency graph."""
    return sorted({e.language for e in graph.entities.values() if e.language})


@tool(
    name="changelog_architecture",
    description="Produce an architectural changelog between two versions: components "
    "added, removed, renamed, split or merged; entities that changed component; "
    "smells gained or resolved; and metric deltas.",
)
def changelog_architecture(
    arch_a: Architecture,
    graph_a: DependencyGraph,
    arch_b: Architecture,
    graph_b: DependencyGraph,
    *,
    smells_a: list[SmellInstance] | None = None,
    smells_b: list[SmellInstance] | None = None,
    metrics_a: list[MetricResult] | None = None,
    metrics_b: list[MetricResult] | None = None,
    ref_a: str | None = None,
    ref_b: str | None = None,
    min_entities: int = 8,
    min_share: float = 0.20,
) -> dict[str, Any]:
    """Build an architectural changelog between two recovered architectures.

    Args:
        arch_a: The earlier architecture.
        graph_a: Dependency graph for the earlier version.
        arch_b: The later architecture.
        graph_b: Dependency graph for the later version.
        smells_a: Smells for the earlier version. Computed if omitted.
        smells_b: Smells for the later version. Computed if omitted.
        metrics_a: Metrics for the earlier version. Computed if omitted.
        metrics_b: Metrics for the later version. Computed if omitted.
        ref_a: Optional label for the earlier version, recorded as metadata.
        ref_b: Optional label for the later version, recorded as metadata.
        min_entities: Absolute significance threshold for a flow. ``min_share``
            already catches proportionally-large moves in small components, so
            this exists only to catch large absolute moves in large ones; see
            ``classify_structural_changes`` for the measured datapoint behind
            the default.
        min_share: Fractional significance threshold in (0, 1].

    Returns:
        A dict with refs, components, responsibility_shifts, smells, metrics,
        languages and summary. Every collection is deterministically sorted.

    Raises:
        ValueError: If *min_share* is outside (0, 1].
    """
    changes = classify_structural_changes(
        arch_a, arch_b, min_entities=min_entities, min_share=min_share
    )

    if smells_a is None:
        smells_a = detect_smells(arch_a, graph_a)
    if smells_b is None:
        smells_b = detect_smells(arch_b, graph_b)
    if metrics_a is None:
        metrics_a = compute_metrics(arch_a, graph_a)
    if metrics_b is None:
        metrics_b = compute_metrics(arch_b, graph_b)

    shifts = [
        {"entity": fqn, "from": flow.source, "to": flow.target}
        for flow in changes.flows
        if flow.source != flow.target
        for fqn in flow.entities
    ]
    shifts.sort(key=lambda s: (s["entity"], s["from"], s["to"]))

    rename_map = dict(changes.rename_map)
    keys_a = {_smell_key(s, rename_map): s for s in smells_a}
    keys_b = {_smell_key(s): s for s in smells_b}
    new_keys = sorted(set(keys_b) - set(keys_a))
    resolved_keys = sorted(set(keys_a) - set(keys_b))
    persisting_keys = sorted(set(keys_a) & set(keys_b))

    values_a = {m.name: m.value for m in metrics_a}
    values_b = {m.name: m.value for m in metrics_b}
    metrics: dict[str, dict[str, Any]] = {}
    for name in sorted(set(values_a) | set(values_b)):
        a_value = values_a.get(name)
        b_value = values_b.get(name)
        delta = (
            b_value - a_value
            if isinstance(a_value, (int, float)) and isinstance(b_value, (int, float))
            else None
        )
        metrics[name] = {"a": a_value, "b": b_value, "delta": delta}

    entities_a = set(arch_a.membership())
    entities_b = set(arch_b.membership())

    return {
        "refs": {"a": ref_a, "b": ref_b},
        "components": structural_dict(changes),
        "responsibility_shifts": shifts,
        "smells": {
            "new": [_smell_dict(keys_b[k]) for k in new_keys],
            "resolved": [_smell_dict(keys_a[k]) for k in resolved_keys],
            "persisting": [_smell_dict(keys_b[k]) for k in persisting_keys],
        },
        "metrics": metrics,
        "languages": {"a": _languages(graph_a), "b": _languages(graph_b)},
        "summary": {
            "components_a": len(arch_a.components),
            "components_b": len(arch_b.components),
            "shifts": len(shifts),
            "entities_a": len(entities_a),
            "entities_b": len(entities_b),
            "entities_added": len(entities_b - entities_a),
            "entities_deleted": len(entities_a - entities_b),
            "smells_new": len(new_keys),
            "smells_resolved": len(resolved_keys),
        },
    }
