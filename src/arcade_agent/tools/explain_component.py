"""Tool: Explain a recovered architecture component in detail."""

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool


@tool(
    name="explain_component",
    description="Explain a component from a recovered architecture. Shows responsibility, "
    "entities, public API surface, dependencies, and cohesion metrics.",
)
def explain_component(
    architecture: Architecture,
    dep_graph: DependencyGraph,
    component: str,
) -> dict:
    """Explain a single architecture component in detail.

    Args:
        architecture: Recovered architecture containing the component.
        dep_graph: Dependency graph for the codebase.
        component: Name of the component to explain.

    Returns:
        Dict with component details: entities, API surface, dependencies, cohesion.
    """
    # Find the component
    target = None
    for comp in architecture.components:
        if comp.name == component:
            target = comp
            break

    if target is None:
        available = [c.name for c in architecture.components]
        return {"error": f"Component '{component}' not found", "available": available}

    comp_entities = set(target.entities)

    # Classify entities by kind
    entities = []
    for fqn in sorted(comp_entities):
        entity = dep_graph.entities.get(fqn)
        if entity:
            entities.append({
                "fqn": fqn,
                "name": entity.name,
                "kind": entity.kind,
                "file_path": entity.file_path,
            })

    # Compute edge classification
    internal_edges = 0
    incoming_edges: list[dict] = []
    outgoing_edges: list[dict] = []
    depended_on_fqns: set[str] = set()  # our entities that outsiders depend on

    for edge in dep_graph.edges:
        src_in = edge.source in comp_entities
        tgt_in = edge.target in comp_entities
        if src_in and tgt_in:
            internal_edges += 1
        elif src_in and not tgt_in:
            outgoing_edges.append({
                "source": edge.source, "target": edge.target, "relation": edge.relation,
            })
        elif tgt_in and not src_in:
            incoming_edges.append({
                "source": edge.source, "target": edge.target, "relation": edge.relation,
            })
            depended_on_fqns.add(edge.target)

    # API surface = entities that other components depend on
    api_surface = sorted(depended_on_fqns)
    internal_only = sorted(comp_entities - depended_on_fqns)

    # Component-level dependencies
    depends_on: set[str] = set()
    depended_on_by: set[str] = set()
    for edge in dep_graph.edges:
        src_in = edge.source in comp_entities
        tgt_in = edge.target in comp_entities
        if src_in and not tgt_in:
            target_comp = architecture.component_of(edge.target)
            if target_comp:
                depends_on.add(target_comp)
        elif tgt_in and not src_in:
            source_comp = architecture.component_of(edge.source)
            if source_comp:
                depended_on_by.add(source_comp)

    # Cohesion: ratio of internal edges to total edges involving this component
    total_edges = internal_edges + len(incoming_edges) + len(outgoing_edges)
    cohesion = round(internal_edges / total_edges, 3) if total_edges > 0 else 1.0

    return {
        "name": target.name,
        "responsibility": target.responsibility,
        "num_entities": len(comp_entities),
        "entities": entities,
        "api_surface": api_surface,
        "internal_only": internal_only,
        "depends_on": sorted(depends_on),
        "depended_on_by": sorted(depended_on_by),
        "internal_edges": internal_edges,
        "incoming_edges": len(incoming_edges),
        "outgoing_edges": len(outgoing_edges),
        "cohesion": cohesion,
    }
