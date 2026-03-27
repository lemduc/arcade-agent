"""Similarity measure implementations for clustering algorithms.

Implements measures used in Weighted Clustering Algorithm (WCA):
- Jaccard Similarity (JS)
- Unbiased Ellenberg Measure (UEM)
- Structure-based Coupling Measure (SCM)
"""

from arcade_agent.models.graph import DependencyGraph


def _get_neighbors(fqn: str, adjacency: dict[str, list[str]]) -> set[str]:
    """Get all neighbors (successors) of an entity."""
    return set(adjacency.get(fqn, []))


def _get_predecessors(fqn: str, reverse_adj: dict[str, list[str]]) -> set[str]:
    """Get all predecessors of an entity."""
    return set(reverse_adj.get(fqn, []))


def _build_reverse_adjacency(adjacency: dict[str, list[str]]) -> dict[str, list[str]]:
    """Build reverse adjacency list."""
    reverse: dict[str, list[str]] = {}
    for src, targets in adjacency.items():
        for tgt in targets:
            reverse.setdefault(tgt, []).append(src)
    return reverse


def jaccard_similarity(
    fqn_a: str,
    fqn_b: str,
    adjacency: dict[str, list[str]],
) -> float:
    """Compute Jaccard similarity between two entities based on their dependencies.

    JS(a,b) = |deps(a) ∩ deps(b)| / |deps(a) ∪ deps(b)|
    """
    deps_a = _get_neighbors(fqn_a, adjacency)
    deps_b = _get_neighbors(fqn_b, adjacency)

    intersection = deps_a & deps_b
    union = deps_a | deps_b

    if not union:
        return 0.0
    return len(intersection) / len(union)


def unbiased_ellenberg(
    fqn_a: str,
    fqn_b: str,
    adjacency: dict[str, list[str]],
) -> float:
    """Compute Unbiased Ellenberg Measure between two entities.

    UEM(a,b) = 2 * |deps(a) ∩ deps(b)| / (|deps(a)| + |deps(b)|)
    """
    deps_a = _get_neighbors(fqn_a, adjacency)
    deps_b = _get_neighbors(fqn_b, adjacency)

    intersection = deps_a & deps_b
    total = len(deps_a) + len(deps_b)

    if total == 0:
        return 0.0
    return 2 * len(intersection) / total


def structure_coupling_measure(
    fqn_a: str,
    fqn_b: str,
    adjacency: dict[str, list[str]],
    reverse_adj: dict[str, list[str]] | None = None,
) -> float:
    """Compute Structure-based Coupling Measure.

    SCM considers both forward and backward dependencies.
    SCM(a,b) = (JS_forward(a,b) + JS_backward(a,b)) / 2
    """
    if reverse_adj is None:
        reverse_adj = _build_reverse_adjacency(adjacency)

    # Forward Jaccard (based on outgoing deps)
    fwd = jaccard_similarity(fqn_a, fqn_b, adjacency)

    # Backward Jaccard (based on incoming deps)
    back_a = _get_predecessors(fqn_a, reverse_adj)
    back_b = _get_predecessors(fqn_b, reverse_adj)
    back_intersection = back_a & back_b
    back_union = back_a | back_b
    bwd = len(back_intersection) / len(back_union) if back_union else 0.0

    return (fwd + bwd) / 2


def compute_similarity_matrix(
    entities: list[str],
    adjacency: dict[str, list[str]],
    measure: str = "uem",
) -> dict[tuple[str, str], float]:
    """Compute pairwise similarity matrix for a set of entities.

    Args:
        entities: List of entity FQNs.
        adjacency: Adjacency list.
        measure: Similarity measure to use ('js', 'uem', 'scm').

    Returns:
        Dict mapping (fqn_a, fqn_b) to similarity score.
    """
    reverse_adj = _build_reverse_adjacency(adjacency)

    sim_fn = {
        "js": lambda a, b: jaccard_similarity(a, b, adjacency),
        "uem": lambda a, b: unbiased_ellenberg(a, b, adjacency),
        "scm": lambda a, b: structure_coupling_measure(a, b, adjacency, reverse_adj),
    }

    fn = sim_fn.get(measure)
    if fn is None:
        raise ValueError(f"Unknown similarity measure: {measure}. Use: js, uem, scm")

    matrix: dict[tuple[str, str], float] = {}
    for i, a in enumerate(entities):
        for j, b in enumerate(entities):
            if i < j:
                score = fn(a, b)
                matrix[(a, b)] = score
                matrix[(b, a)] = score
            elif i == j:
                matrix[(a, b)] = 1.0

    return matrix
