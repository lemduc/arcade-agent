"""Concern overload and scattered functionality detection."""

from arcade_agent.models.architecture import Architecture
from arcade_agent.models.graph import DependencyGraph


def detect_concern_overload(
    architecture: Architecture,
    threshold: int = 20,
    high_threshold: int = 40,
) -> list[dict]:
    """Detect components with too many responsibilities.

    A component is flagged if it contains more entities than the threshold,
    suggesting it handles multiple concerns.

    Args:
        architecture: The recovered architecture.
        threshold: Minimum entity count to flag (default: 20).
        high_threshold: Entity count for high severity (default: 40).

    Returns:
        List of dicts with component name, entity count, and severity.
    """
    results = []
    for comp in architecture.components:
        count = len(comp.entities)
        if count > threshold:
            severity = "high" if count > high_threshold else "medium"
            results.append({
                "component": comp.name,
                "entity_count": count,
                "severity": severity,
            })
    return results


def detect_scattered_functionality(
    architecture: Architecture,
    dep_graph: DependencyGraph,
    min_components: int = 3,
) -> list[dict]:
    """Detect functionality scattered across too many components.

    Looks for naming patterns (suffixes like Service, Controller, Repository)
    that appear in multiple components, suggesting a concern is scattered.

    Args:
        architecture: The recovered architecture.
        dep_graph: The dependency graph.
        min_components: Minimum number of components a pattern must appear in.

    Returns:
        List of dicts with pattern, components, and count.
    """
    common_suffixes = [
        "Service", "Controller", "Repository", "Manager", "Handler",
        "Factory", "Listener", "Provider", "Adapter", "Helper",
        "Util", "Utils", "Config", "Configuration", "Exception",
        "Test", "Spec",
    ]

    # Track which components contain each suffix pattern
    suffix_components: dict[str, set[str]] = {}

    for comp in architecture.components:
        for fqn in comp.entities:
            entity = dep_graph.entities.get(fqn)
            if not entity:
                continue
            for suffix in common_suffixes:
                if entity.name.endswith(suffix):
                    suffix_components.setdefault(suffix, set()).add(comp.name)
                    break

    results = []
    for suffix, components in sorted(suffix_components.items()):
        if len(components) >= min_components:
            results.append({
                "pattern": suffix,
                "components": sorted(components),
                "count": len(components),
                "severity": "high" if len(components) >= 5 else "medium",
            })

    return results


def detect_link_overload(
    architecture: Architecture,
    dep_graph: DependencyGraph,
    threshold_ratio: float = 0.5,
) -> list[dict]:
    """Detect components that are depended upon by too many other components.

    A component has link overload if more than threshold_ratio of all other
    components depend on it.

    Args:
        architecture: The recovered architecture.
        dep_graph: The dependency graph.
        threshold_ratio: Fraction of components that must depend on a component (default: 0.5).

    Returns:
        List of dicts with component name, dependents count, and severity.
    """
    if len(architecture.components) <= 2:
        return []

    # Count incoming dependencies per component
    incoming: dict[str, set[str]] = {comp.name: set() for comp in architecture.components}
    for src, tgt in architecture.component_dependencies(dep_graph):
        incoming[tgt].add(src)

    total_other = len(architecture.components) - 1
    results = []
    for comp_name, dependents in incoming.items():
        ratio = len(dependents) / total_other if total_other > 0 else 0
        if ratio >= threshold_ratio and len(dependents) >= 3:
            severity = "high" if ratio >= 0.75 else "medium"
            results.append({
                "component": comp_name,
                "dependents": sorted(dependents),
                "dependent_count": len(dependents),
                "ratio": round(ratio, 2),
                "severity": severity,
            })

    return results
