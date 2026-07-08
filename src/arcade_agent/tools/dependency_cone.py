"""Tool: Compute the upstream/downstream dependency cone of an entity or file."""

from arcade_agent.algorithms.traversal import adjacency_with_relations, walk_cone
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.diff_impact import _paths_match
from arcade_agent.tools.registry import tool

_VALID_DIRECTIONS = ("upstream", "downstream", "both")


def _resolve_seeds(
    dep_graph: DependencyGraph, target: str
) -> tuple[set[str], str | None]:
    """Resolve a target (entity FQN or file path) to seed entity FQNs.

    Args:
        dep_graph: Dependency graph to resolve against.
        target: An entity FQN or a file path.

    Returns:
        ``(seeds, matched_by)`` where ``matched_by`` is ``"entity"``, ``"file"``,
        or ``None`` when nothing matched.
    """
    if target in dep_graph.entities:
        return {target}, "entity"
    seeds = {
        fqn
        for fqn, entity in dep_graph.entities.items()
        if _paths_match(entity.file_path, target)
    }
    if seeds:
        return seeds, "file"
    return set(), None


def _cone_block(
    dep_graph: DependencyGraph,
    adjacency: dict[str, list[tuple[str, str]]],
    seeds: set[str],
    max_depth: int,
    max_nodes: int | None,
) -> dict:
    """Walk one direction and roll reached entities up into a summary block.

    Args:
        dep_graph: Dependency graph (for the file rollup).
        adjacency: Forward or reverse adjacency to walk.
        seeds: Seed FQNs.
        max_depth: Maximum hops.
        max_nodes: Optional per-direction cap.

    Returns:
        Dict with ``num_nodes``, ``truncated``, ``nodes``, and ``files``.
    """
    nodes, truncated = walk_cone(
        adjacency,
        seeds,
        max_depth,
        max_nodes=max_nodes,
        valid_nodes=set(dep_graph.entities),
    )
    files = sorted(
        {dep_graph.entities[n["fqn"]].file_path for n in nodes}
    )
    return {
        "num_nodes": len(nodes),
        "truncated": truncated,
        "nodes": nodes,
        "files": files,
    }


@tool(
    name="dependency_cone",
    description="Return the upstream (what it depends on) and/or downstream "
    "(what depends on it) dependency cone of an entity or file, with depth "
    "control — the reachability view behind impact and comprehension questions.",
)
def dependency_cone(
    dep_graph: DependencyGraph,
    target: str,
    direction: str = "both",
    max_depth: int = 3,
    max_nodes: int | None = None,
) -> dict:
    """Compute the dependency cone of an entity or file.

    Args:
        dep_graph: Dependency graph to traverse.
        target: An entity FQN or a file path to seed the cone from.
        direction: ``"upstream"`` (what the seed depends on), ``"downstream"``
            (what depends on the seed), or ``"both"``.
        max_depth: Maximum hops to walk from the seed (1 = direct neighbors).
        max_nodes: Optional per-direction cap on returned nodes (closest kept).

    Returns:
        Dict with the resolved seeds and an ``upstream``/``downstream`` block for
        each requested direction; a clean empty result if nothing resolves, or an
        error dict for an invalid ``direction``.
    """
    if direction not in _VALID_DIRECTIONS:
        return {
            "target": target,
            "error": f"Invalid direction '{direction}'.",
            "valid_directions": list(_VALID_DIRECTIONS),
        }

    seeds, matched_by = _resolve_seeds(dep_graph, target)
    if not seeds:
        return {
            "target": target,
            "matched_by": None,
            "seed_entities": [],
            "direction": direction,
            "max_depth": max_depth,
            "note": f"No entity or file matched '{target}'.",
        }

    result: dict = {
        "target": target,
        "matched_by": matched_by,
        "seed_entities": sorted(seeds),
        "direction": direction,
        "max_depth": max_depth,
    }

    if direction in ("upstream", "both"):
        forward = adjacency_with_relations(dep_graph, reverse=False)
        result["upstream"] = _cone_block(
            dep_graph, forward, seeds, max_depth, max_nodes
        )

    if direction in ("downstream", "both"):
        reverse = adjacency_with_relations(dep_graph, reverse=True)
        result["downstream"] = _cone_block(
            dep_graph, reverse, seeds, max_depth, max_nodes
        )

    return result
