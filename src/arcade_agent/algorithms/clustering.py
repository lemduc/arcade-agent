"""Agglomerative clustering algorithms for architecture recovery.

Implements:
- WCA (Weighted Clustering Algorithm) — agglomerative hierarchical clustering
  using similarity measures between entities based on their dependency structure.
"""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.similarity import compute_similarity_matrix
from arcade_agent.parsers.graph import DependencyGraph


def wca(
    dep_graph: DependencyGraph,
    similarity_measure: str = "uem",
    num_clusters: int | None = None,
    stop_threshold: float = 0.0,
) -> Architecture:
    """Weighted Clustering Algorithm for architecture recovery.

    Agglomerative hierarchical clustering that merges the two most similar
    clusters at each step, using entity dependency similarity.

    Args:
        dep_graph: The dependency graph to cluster.
        similarity_measure: Similarity measure to use ('js', 'uem', 'scm').
        num_clusters: Target number of clusters (stopping criterion).
            If None, uses stop_threshold.
        stop_threshold: Minimum similarity to continue merging (default: 0.0).
            Ignored if num_clusters is set.

    Returns:
        Architecture with recovered components.
    """
    entities = list(dep_graph.entities.keys())
    if not entities:
        return Architecture(algorithm="wca")

    adjacency = dep_graph.to_adjacency()

    # Initialize: each entity is its own cluster
    clusters: dict[str, list[str]] = {fqn: [fqn] for fqn in entities}

    # Compute initial pairwise similarity
    sim_matrix = compute_similarity_matrix(entities, adjacency, similarity_measure)

    while len(clusters) > 1:
        # Check stopping criteria
        if num_clusters is not None and len(clusters) <= num_clusters:
            break

        # Find the most similar pair of clusters
        best_sim = -1.0
        best_pair: tuple[str, str] | None = None

        cluster_keys = list(clusters.keys())
        for i, key_a in enumerate(cluster_keys):
            for j, key_b in enumerate(cluster_keys):
                if i >= j:
                    continue
                # Average-link similarity between clusters
                sim = _cluster_similarity(
                    clusters[key_a], clusters[key_b], sim_matrix
                )
                if sim > best_sim:
                    best_sim = sim
                    best_pair = (key_a, key_b)

        if best_pair is None or (num_clusters is None and best_sim <= stop_threshold):
            break

        # Merge the two most similar clusters
        key_a, key_b = best_pair
        merged = clusters[key_a] + clusters[key_b]
        del clusters[key_a]
        del clusters[key_b]
        clusters[key_a] = merged

    # Build architecture from clusters
    components = []
    for key, members in sorted(clusters.items()):
        # Name from common package prefix
        name = _cluster_name(members, dep_graph)
        components.append(
            Component(
                name=name,
                responsibility=f"Cluster of {len(members)} entities",
                entities=sorted(members),
            )
        )

    return Architecture(
        components=components,
        rationale=f"WCA clustering with {similarity_measure} similarity",
        algorithm="wca",
        metadata={"similarity_measure": similarity_measure, "num_clusters": len(components)},
    )


def _cluster_similarity(
    cluster_a: list[str],
    cluster_b: list[str],
    sim_matrix: dict[tuple[str, str], float],
) -> float:
    """Compute average-link similarity between two clusters."""
    total = 0.0
    count = 0
    for a in cluster_a:
        for b in cluster_b:
            total += sim_matrix.get((a, b), 0.0)
            count += 1
    return total / count if count > 0 else 0.0


def _cluster_name(members: list[str], dep_graph: DependencyGraph) -> str:
    """Generate a meaningful name for a cluster from its members."""
    packages = set()
    for fqn in members:
        entity = dep_graph.entities.get(fqn)
        if entity:
            packages.add(entity.package)

    if len(packages) == 1:
        pkg = packages.pop()
        parts = pkg.split(".")
        return parts[-1].title() if parts[-1] else "Default"

    # Find common prefix
    pkg_list = sorted(packages)
    if pkg_list:
        parts_list = [p.split(".") for p in pkg_list]
        common = []
        for segments in zip(*parts_list):
            if len(set(segments)) == 1:
                common.append(segments[0])
            else:
                break
        if common:
            return common[-1].title()

    # Fallback: use first member's short name
    entity = dep_graph.entities.get(members[0])
    if entity:
        return entity.package.split(".")[-1].title() if entity.package else entity.name
    return "Cluster"
