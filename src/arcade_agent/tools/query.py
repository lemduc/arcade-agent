"""Tool: Query and explore the recovered architecture."""

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool


@tool(
    name="query",
    description="Query and explore a recovered architecture. Find which component an entity "
    "belongs to, list dependencies, find the most coupled components, etc.",
)
def query(
    architecture: Architecture,
    dep_graph: DependencyGraph,
    question: str,
    entity: str | None = None,
    component: str | None = None,
) -> dict:
    """Query the recovered architecture.

    Args:
        architecture: The recovered architecture.
        dep_graph: The dependency graph.
        question: Type of query to run:
            - 'component_of': Which component does an entity belong to?
            - 'dependencies': What are the dependencies of a component?
            - 'dependents': What depends on this component?
            - 'entities': List all entities in a component.
            - 'most_coupled': Show the most coupled component pairs.
            - 'summary': Overall architecture summary.
            - 'largest': Largest components by entity count.
        entity: Entity FQN (for entity-specific queries).
        component: Component name (for component-specific queries).

    Returns:
        Dict with query results.
    """
    if question == "component_of":
        if not entity:
            return {"error": "entity parameter required for 'component_of' query"}
        comp = architecture.component_of(entity)
        return {"entity": entity, "component": comp}

    elif question == "dependencies":
        if not component:
            return {"error": "component parameter required for 'dependencies' query"}
        comp_deps = architecture.component_dependencies(dep_graph)
        deps = sorted({tgt for src, tgt in comp_deps if src == component})
        return {"component": component, "dependencies": deps}

    elif question == "dependents":
        if not component:
            return {"error": "component parameter required for 'dependents' query"}
        comp_deps = architecture.component_dependencies(dep_graph)
        deps = sorted({src for src, tgt in comp_deps if tgt == component})
        return {"component": component, "dependents": deps}

    elif question == "entities":
        if not component:
            return {"error": "component parameter required for 'entities' query"}
        for comp in architecture.components:
            if comp.name == component:
                return {"component": component, "entities": sorted(comp.entities)}
        return {"error": f"Component '{component}' not found"}

    elif question == "most_coupled":
        comp_deps = architecture.component_dependencies(dep_graph)
        # Count edges per pair
        pair_counts: dict[tuple[str, str], int] = {}
        for edge in dep_graph.edges:
            src_comp = architecture.component_of(edge.source)
            tgt_comp = architecture.component_of(edge.target)
            if src_comp and tgt_comp and src_comp != tgt_comp:
                key = (src_comp, tgt_comp)
                pair_counts[key] = pair_counts.get(key, 0) + 1

        ranked = sorted(pair_counts.items(), key=lambda x: -x[1])[:10]
        return {
            "most_coupled_pairs": [
                {"source": src, "target": tgt, "edge_count": count}
                for (src, tgt), count in ranked
            ]
        }

    elif question == "summary":
        comp_deps = architecture.component_dependencies(dep_graph)
        return {
            "num_components": len(architecture.components),
            "num_entities": dep_graph.num_entities,
            "num_edges": dep_graph.num_edges,
            "num_component_dependencies": len(comp_deps),
            "algorithm": architecture.algorithm,
            "rationale": architecture.rationale,
            "components": [
                {
                    "name": c.name,
                    "responsibility": c.responsibility,
                    "entity_count": len(c.entities),
                }
                for c in architecture.components
            ],
        }

    elif question == "largest":
        ranked = sorted(architecture.components, key=lambda c: -len(c.entities))[:10]
        return {
            "largest_components": [
                {
                    "name": c.name, "entity_count": len(c.entities),
                    "responsibility": c.responsibility,
                }
                for c in ranked
            ]
        }

    else:
        return {
            "error": f"Unknown query: {question}",
            "available_queries": [
                "component_of", "dependencies", "dependents", "entities",
                "most_coupled", "summary", "largest",
            ],
        }
