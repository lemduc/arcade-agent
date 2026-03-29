"""Tool: Recover software architecture from dependency graph."""

from arcade_agent.algorithms.acdc import acdc
from arcade_agent.algorithms.arc import arc
from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.clustering import wca
from arcade_agent.algorithms.limbo import limbo
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool


def _package_based_recovery(
    dep_graph: DependencyGraph,
    depth: int | None = None,
) -> Architecture:
    """Group entities by meaningful package segments.

    Uses adaptive depth: finds the common prefix, then groups by enough
    remaining segments to produce meaningful components (target: 5-20).

    Entities whose package equals the common prefix (e.g. __init__ modules)
    are assigned using their FQN so they join the correct sub-package group.

    Args:
        dep_graph: Dependency graph to cluster.
        depth: Number of package segments to use after common prefix.
            If None, auto-selects depth to target 5-20 components.
    """
    all_pkgs = [e.package for e in dep_graph.entities.values() if e.package]
    common = _common_prefix_segments(all_pkgs) if all_pkgs else []

    if depth is None:
        depth = _auto_depth(all_pkgs, common)

    groups: dict[str, list[str]] = {}
    for fqn, entity in dep_graph.entities.items():
        if not entity.package:
            groups.setdefault("(default)", []).append(fqn)
            continue
        parts = entity.package.split(".")
        remainder = parts[len(common):]
        if remainder:
            key = ".".join(remainder[:depth])
        else:
            # Package equals common prefix — use FQN to find the right group.
            # e.g. FQN "arcade_agent.algorithms" -> key "algorithms"
            fqn_parts = fqn.split(".")
            fqn_remainder = fqn_parts[len(common):]
            if fqn_remainder:
                key = ".".join(fqn_remainder[:depth])
            else:
                key = parts[-1] if parts[0] else "(default)"
        groups.setdefault(key, []).append(fqn)

    components = []
    seen_names: set[str] = set()
    for key in sorted(groups.keys()):
        name = _component_name_from_key(key)
        # Ensure unique names
        base_name = name
        counter = 1
        while name in seen_names:
            counter += 1
            name = f"{base_name}{counter}"
        seen_names.add(name)

        components.append(
            Component(
                name=name,
                responsibility=f"Entities in {key}",
                entities=sorted(groups[key]),
            )
        )

    return Architecture(
        components=components,
        rationale=(
            f"Package-based grouping (depth={depth} "
            f"after common prefix '{'.'.join(common)}')."
        ),
        algorithm="pkg",
    )


def _auto_depth(all_pkgs: list[str], common: list[str]) -> int:
    """Auto-select grouping depth to target 5-20 components.

    Uses unique package segments after the common prefix to estimate
    how many components each depth level would produce.
    """
    if not all_pkgs:
        return 2

    for depth in range(1, 6):
        keys: set[str] = set()
        for pkg in all_pkgs:
            parts = pkg.split(".")
            remainder = parts[len(common):]
            if remainder:
                keys.add(".".join(remainder[:depth]))
            else:
                keys.add(parts[-1] if parts[0] else "(default)")
        num_groups = len(keys)
        if num_groups >= 5 or depth >= 4:
            return depth

    return 2


def _component_name_from_key(key: str) -> str:
    """Generate a readable component name from a package key."""
    if key == "(default)":
        return "Default"
    # Use last segment, title-cased
    name = key.split(".")[-1] if "." in key else key
    name = name.replace("_", " ").title().replace(" ", "")
    return name if name else "Default"


def _common_prefix_segments(packages: list[str]) -> list[str]:
    """Find the longest common package prefix across all packages."""
    if not packages:
        return []
    split_pkgs = [p.split(".") for p in packages]
    prefix = []
    for segments in zip(*split_pkgs):
        if len(set(segments)) == 1:
            prefix.append(segments[0])
        else:
            break
    return prefix


@tool(
    name="recover",
    description="Recover software architecture from a dependency graph. "
    "Supports multiple algorithms: pkg (package-based), wca (weighted clustering), "
    "acdc (pattern-based), arc (concern-based via LLM), limbo (information-theoretic).",
)
def recover(
    dep_graph: DependencyGraph,
    algorithm: str = "pkg",
    num_clusters: int | None = None,
    similarity_measure: str = "uem",
    pkg_depth: int | None = None,
    hybrid_weight: float = 0.5,
) -> Architecture:
    """Recover software architecture using the specified algorithm.

    Args:
        dep_graph: Dependency graph to analyze.
        algorithm: Recovery algorithm to use:
            - 'pkg': Package-based grouping (fast, deterministic)
            - 'wca': Weighted Clustering Algorithm (agglomerative)
            - 'acdc': ACDC pattern-based clustering
            - 'arc': Architecture Recovery using Concerns (LLM-powered)
            - 'limbo': Information-theoretic clustering (LLM-powered)
        num_clusters: Target number of clusters (for WCA/ARC/LIMBO). Auto if None.
        similarity_measure: Similarity measure for WCA ('js', 'uem', 'scm').
        pkg_depth: Package depth for 'pkg' algorithm. Auto if None.
        hybrid_weight: ARC semantic/structural blend (0-1). 1.0 = pure semantic,
            0.0 = pure structural, 0.5 = equal blend (default).

    Returns:
        Architecture with recovered components.
    """
    if algorithm == "pkg":
        return _package_based_recovery(dep_graph, depth=pkg_depth)
    elif algorithm == "wca":
        return wca(
            dep_graph,
            similarity_measure=similarity_measure,
            num_clusters=num_clusters,
        )
    elif algorithm == "acdc":
        return acdc(dep_graph)
    elif algorithm == "arc":
        return arc(
            dep_graph,
            num_clusters=num_clusters,
            hybrid_weight=hybrid_weight,
        )
    elif algorithm == "limbo":
        return limbo(
            dep_graph,
            num_clusters=num_clusters,
            hybrid_weight=hybrid_weight,
        )
    else:
        raise ValueError(f"Unknown algorithm: {algorithm}. Use: pkg, wca, acdc, arc, limbo")
