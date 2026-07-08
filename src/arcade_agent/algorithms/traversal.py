"""Cycle-safe dependency-graph traversal helpers.

Pure functions shared by ``diff_impact`` and ``dependency_cone``. They operate
on a plain adjacency mapping so they carry no dependency on the tool registry.
"""

from collections import deque
from collections.abc import Iterable

from arcade_agent.parsers.graph import DependencyGraph


def adjacency_with_relations(
    graph: DependencyGraph, *, reverse: bool = False
) -> dict[str, list[tuple[str, str]]]:
    """Build an adjacency map that preserves edge relations.

    Args:
        graph: Dependency graph to read edges from.
        reverse: When False, map ``source -> [(target, relation)]`` (forward
            dependencies). When True, map ``target -> [(source, relation)]``
            (reverse dependencies — who depends on a node).

    Returns:
        Mapping of node FQN to a list of ``(neighbor_fqn, relation)`` pairs.
    """
    adjacency: dict[str, list[tuple[str, str]]] = {}
    for edge in graph.edges:
        if reverse:
            adjacency.setdefault(edge.target, []).append((edge.source, edge.relation))
        else:
            adjacency.setdefault(edge.source, []).append((edge.target, edge.relation))
    return adjacency


def walk_cone(
    adjacency: dict[str, list[tuple[str, str]]],
    seeds: Iterable[str],
    max_depth: int,
    max_nodes: int | None = None,
    valid_nodes: set[str] | None = None,
) -> tuple[list[dict], bool]:
    """Breadth-first walk of a cone from ``seeds`` over ``adjacency``.

    A ``visited`` set pre-seeded with ``seeds`` both excludes the seeds from the
    result and makes the walk cycle-safe. Each reached node records the number
    of hops from the nearest seed (``distance``, 1 = direct) and the relation of
    the *first* hop taken to reach it (``via_relation``).

    Args:
        adjacency: Node FQN -> list of ``(neighbor_fqn, relation)`` pairs.
        seeds: Starting node FQNs (distance 0, never reported).
        max_depth: Maximum hops to walk (1 = direct neighbors only).
        max_nodes: Optional cap; the closest nodes are kept and ``truncated`` is
            set when any are dropped.
        valid_nodes: When given, only neighbors in this set are recorded, though
            the walk still traverses through non-recorded neighbors.

    Returns:
        ``(nodes, truncated)`` where ``nodes`` is a list of
        ``{"fqn", "distance", "via_relation"}`` sorted by ``(distance, fqn)``.
    """
    seed_list = list(seeds)
    visited: set[str] = set(seed_list)
    reached: dict[str, dict] = {}
    queue: deque[tuple[str, int, str | None]] = deque(
        (s, 0, None) for s in seed_list
    )

    while queue:
        node, dist, first_rel = queue.popleft()
        if dist >= max_depth:
            continue
        for neighbor, relation in adjacency.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            hop_rel = relation if first_rel is None else first_rel
            if valid_nodes is None or neighbor in valid_nodes:
                reached[neighbor] = {
                    "fqn": neighbor,
                    "distance": dist + 1,
                    "via_relation": hop_rel,
                }
            queue.append((neighbor, dist + 1, hop_rel))

    nodes = sorted(reached.values(), key=lambda d: (d["distance"], d["fqn"]))
    truncated = False
    if max_nodes is not None and len(nodes) > max_nodes:
        nodes = nodes[:max_nodes]
        truncated = True
    return nodes, truncated
