"""Coupling, cohesion, and modularization quality metrics.

Implements the 7 decay metrics from ARCADE Core:
- RCI (Ratio of Cohesive Interactions)
- TurboMQ (Modularization Quality)
- BasicMQ (Basic Modularization Quality)
- IntraConnectivity
- InterConnectivity
- TwoWayPairRatio
- ArchitecturalStability (requires two versions)
"""

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.parsers.graph import DependencyGraph


def _build_membership(architecture: Architecture) -> dict[str, str]:
    """Build entity -> component mapping."""
    membership: dict[str, str] = {}
    for comp in architecture.components:
        for fqn in comp.entities:
            membership[fqn] = comp.name
    return membership


def _count_edges(
    dep_graph: DependencyGraph,
    membership: dict[str, str],
) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    """Count intra-component and inter-component edges.

    Returns:
        Tuple of (intra_counts, inter_counts) where:
        - intra_counts: {component_name: count}
        - inter_counts: {(src_comp, tgt_comp): count}
    """
    intra: dict[str, int] = {}
    inter: dict[tuple[str, str], int] = {}

    for edge in dep_graph.edges:
        src_comp = membership.get(edge.source)
        tgt_comp = membership.get(edge.target)
        if not src_comp or not tgt_comp:
            continue

        if src_comp == tgt_comp:
            intra[src_comp] = intra.get(src_comp, 0) + 1
        else:
            key = (src_comp, tgt_comp)
            inter[key] = inter.get(key, 0) + 1

    return intra, inter


def compute_rci(architecture: Architecture, dep_graph: DependencyGraph) -> MetricResult:
    """Compute Ratio of Cohesive Interactions.

    RCI = intra_edges / total_edges
    Higher is better (more cohesive architecture).
    """
    membership = _build_membership(architecture)
    intra, inter = _count_edges(dep_graph, membership)

    total_intra = sum(intra.values())
    total_inter = sum(inter.values())
    total = total_intra + total_inter

    value = total_intra / total if total > 0 else 0.0

    return MetricResult(
        name="RCI",
        value=round(value, 4),
        details={
            "intra_edges": total_intra,
            "inter_edges": total_inter,
            "total_edges": total,
        },
    )


def compute_turbo_mq(architecture: Architecture, dep_graph: DependencyGraph) -> MetricResult:
    """Compute TurboMQ (Modularization Quality).

    TurboMQ = sum of cluster factors CF(i) for each component i.
    CF(i) = 2 * mu_i / (2 * mu_i + sum_j(epsilon_ij + epsilon_ji))
    where mu_i = intra-edges, epsilon_ij = inter-edges from i to j.

    Higher is better.
    """
    membership = _build_membership(architecture)
    intra, inter = _count_edges(dep_graph, membership)

    comp_names = [comp.name for comp in architecture.components]
    turbo_mq = 0.0
    cf_details: dict[str, float] = {}

    for comp_name in comp_names:
        mu = intra.get(comp_name, 0)

        # Sum of inter-edges involving this component
        epsilon_sum = 0
        for (src, tgt), count in inter.items():
            if src == comp_name or tgt == comp_name:
                epsilon_sum += count

        denominator = 2 * mu + epsilon_sum
        if denominator > 0:
            cf = (2 * mu) / denominator
        else:
            cf = 0.0

        cf_details[comp_name] = round(cf, 4)
        turbo_mq += cf

    num_components = len(comp_names)
    normalized = turbo_mq / num_components if num_components > 0 else 0.0

    return MetricResult(
        name="TurboMQ",
        value=round(normalized, 4),
        details={"cluster_factors": cf_details, "raw_sum": round(turbo_mq, 4)},
    )


def compute_basic_mq(architecture: Architecture, dep_graph: DependencyGraph) -> MetricResult:
    """Compute BasicMQ.

    BasicMQ = (1/k) * sum_i(intra_i / (intra_i + 0.5*inter_i))
    where k = number of components, inter_i = inter-edges touching component i.

    Higher is better.
    """
    membership = _build_membership(architecture)
    intra, inter = _count_edges(dep_graph, membership)

    comp_names = [comp.name for comp in architecture.components]
    total = 0.0

    for comp_name in comp_names:
        intra_count = intra.get(comp_name, 0)
        inter_count = 0
        for (src, tgt), count in inter.items():
            if src == comp_name or tgt == comp_name:
                inter_count += count

        denominator = intra_count + 0.5 * inter_count
        if denominator > 0:
            total += intra_count / denominator

    k = len(comp_names)
    value = total / k if k > 0 else 0.0

    return MetricResult(name="BasicMQ", value=round(value, 4), details={})


def compute_intra_connectivity(
    architecture: Architecture, dep_graph: DependencyGraph
) -> MetricResult:
    """Compute average intra-connectivity across components.

    IntraConnectivity(i) = intra_edges(i) / (N_i * (N_i - 1))
    where N_i = number of entities in component i.

    Higher is better (denser internal connections).
    """
    membership = _build_membership(architecture)
    intra, _ = _count_edges(dep_graph, membership)

    comp_values: dict[str, float] = {}
    total = 0.0
    count = 0

    for comp in architecture.components:
        n = len(comp.entities)
        max_edges = n * (n - 1)
        if max_edges > 0:
            val = intra.get(comp.name, 0) / max_edges
        else:
            val = 0.0
        comp_values[comp.name] = round(val, 4)
        total += val
        count += 1

    avg = total / count if count > 0 else 0.0

    return MetricResult(
        name="IntraConnectivity",
        value=round(avg, 4),
        details={"per_component": comp_values},
    )


def compute_inter_connectivity(
    architecture: Architecture, dep_graph: DependencyGraph
) -> MetricResult:
    """Compute average inter-connectivity between component pairs.

    InterConnectivity(i,j) = inter_edges(i,j) / (N_i * N_j)

    Lower is better (less coupling between components).
    """
    membership = _build_membership(architecture)
    _, inter = _count_edges(dep_graph, membership)

    comp_sizes = {comp.name: len(comp.entities) for comp in architecture.components}

    total = 0.0
    pair_count = 0

    for (src, tgt), edge_count in inter.items():
        n_src = comp_sizes.get(src, 0)
        n_tgt = comp_sizes.get(tgt, 0)
        max_edges = n_src * n_tgt
        if max_edges > 0:
            total += edge_count / max_edges
        pair_count += 1

    avg = total / pair_count if pair_count > 0 else 0.0

    return MetricResult(
        name="InterConnectivity",
        value=round(avg, 4),
        details={"num_connected_pairs": pair_count},
    )


def compute_two_way_pair_ratio(
    architecture: Architecture, dep_graph: DependencyGraph
) -> MetricResult:
    """Compute ratio of bidirectional component dependencies.

    TwoWayPairRatio = bidirectional_pairs / total_connected_pairs

    Lower is better (fewer mutual dependencies suggest cleaner layering).
    """
    comp_deps = architecture.component_dependencies(dep_graph)
    edge_set = set(comp_deps)

    total_pairs: set[frozenset[str]] = set()
    bidirectional = 0

    for src, tgt in comp_deps:
        pair = frozenset([src, tgt])
        if pair not in total_pairs:
            total_pairs.add(pair)
            if (tgt, src) in edge_set:
                bidirectional += 1

    total = len(total_pairs)
    value = bidirectional / total if total > 0 else 0.0

    return MetricResult(
        name="TwoWayPairRatio",
        value=round(value, 4),
        details={
            "bidirectional_pairs": bidirectional,
            "total_pairs": total,
        },
    )


def compute_all_metrics(
    architecture: Architecture, dep_graph: DependencyGraph
) -> list[MetricResult]:
    """Compute all single-version architecture quality metrics."""
    return [
        compute_rci(architecture, dep_graph),
        compute_turbo_mq(architecture, dep_graph),
        compute_basic_mq(architecture, dep_graph),
        compute_intra_connectivity(architecture, dep_graph),
        compute_inter_connectivity(architecture, dep_graph),
        compute_two_way_pair_ratio(architecture, dep_graph),
    ]
