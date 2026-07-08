"""Tool: Map a set of changed files to their architectural impact."""

from collections import deque

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool


def _basename(path: str) -> str:
    """Return the final path segment of a slash- or backslash-separated path."""
    normalized = path.replace("\\", "/")
    return normalized.rsplit("/", 1)[-1]


def _paths_match(entity_path: str, changed_file: str) -> bool:
    """Test whether a graph entity path refers to a changed file.

    Matching is deliberately tolerant because file paths in the graph may be
    relative, absolute, or bare simple names while a git diff yields
    repo-relative paths. A match is reported when the two are equal, when one
    is a path-suffix of the other, or when their basenames are equal.

    Args:
        entity_path: The ``file_path`` recorded on a graph entity.
        changed_file: A changed file path (e.g. from a git diff).

    Returns:
        True if the entity path plausibly refers to the changed file.
    """
    ep = entity_path.replace("\\", "/")
    cf = changed_file.replace("\\", "/")
    if ep == cf:
        return True
    if ep.endswith("/" + cf) or cf.endswith("/" + ep):
        return True
    return _basename(ep) == _basename(cf)


@tool(
    name="diff_impact",
    description="Map changed files to affected entities, components, downstream "
    "dependents, and potentially broken public contracts — a blast-radius "
    "analysis for a code change without reading the diff.",
)
def diff_impact(
    dep_graph: DependencyGraph,
    changed_files: list[str],
    architecture: Architecture | None = None,
    max_depth: int = 3,
) -> dict:
    """Assess the architectural blast radius of a set of changed files.

    Changed files are mapped to entities, then to their enclosing components,
    their transitive reverse-dependency closure (who depends on them), and the
    subset of changed entities that form a public contract for external callers.

    "Public" is derived structurally (never read from a field): an entity is a
    public contract if it has incoming edges from entities outside the changed
    files — the same signal ``explain_component`` uses for its API surface.

    Args:
        dep_graph: Dependency graph to analyze against.
        changed_files: Changed file paths (e.g. from ``git diff --name-only``).
        architecture: Optional recovered architecture for component mapping.
        max_depth: Maximum reverse-dependency hops to walk (1 = direct callers).

    Returns:
        Dict describing matched/unmatched files, changed entities, affected
        components, downstream dependents (with distance and first-hop relation),
        and potentially broken contracts with their external dependents.
    """
    # -- 1. Match changed files to entities -----------------------------------
    matched_files: list[str] = []
    unmatched_files: list[str] = []
    changed_fqns: set[str] = set()

    for cf in changed_files:
        hits = [
            fqn
            for fqn, entity in dep_graph.entities.items()
            if _paths_match(entity.file_path, cf)
        ]
        if hits:
            matched_files.append(cf)
            changed_fqns.update(hits)
        else:
            unmatched_files.append(cf)

    changed_entities = []
    for fqn in sorted(changed_fqns):
        entity = dep_graph.entities.get(fqn)
        if entity:
            changed_entities.append({
                "fqn": fqn,
                "name": entity.name,
                "kind": entity.kind,
                "file_path": entity.file_path,
            })

    # -- 2. Affected components ------------------------------------------------
    affected_components: list[str] = []
    if architecture is not None:
        comp_names: set[str] = set()
        for fqn in changed_fqns:
            comp = architecture.component_of(fqn)
            if comp:
                comp_names.add(comp)
        affected_components = sorted(comp_names)

    # -- 3. Downstream dependents (reverse-dependency closure) ----------------
    # Reverse adjacency: target -> list of (source, relation) that depend on it.
    reverse_adj: dict[str, list[tuple[str, str]]] = {}
    for edge in dep_graph.edges:
        reverse_adj.setdefault(edge.target, []).append((edge.source, edge.relation))

    # Multi-source BFS seeded at all changed entities (distance 0). A visited
    # set pre-loaded with the changed set both prevents cycles from looping and
    # excludes changed entities from the results.
    visited: set[str] = set(changed_fqns)
    downstream: dict[str, dict] = {}
    queue: deque[tuple[str, int, str | None]] = deque(
        (fqn, 0, None) for fqn in changed_fqns
    )
    while queue:
        node, dist, first_rel = queue.popleft()
        if dist >= max_depth:
            continue
        for src, rel in reverse_adj.get(node, []):
            if src in visited:
                continue
            visited.add(src)
            hop_rel = rel if first_rel is None else first_rel
            if src in dep_graph.entities:
                downstream[src] = {
                    "fqn": src,
                    "distance": dist + 1,
                    "via_relation": hop_rel,
                }
            queue.append((src, dist + 1, hop_rel))

    downstream_dependents = sorted(
        downstream.values(), key=lambda d: (d["distance"], d["fqn"])
    )

    # -- 4. Broken contracts ---------------------------------------------------
    # Changed entities that external (non-changed) entities depend on.
    external_deps: dict[str, list[str]] = {}
    for edge in dep_graph.edges:
        if (
            edge.target in changed_fqns
            and edge.source not in changed_fqns
            and edge.source in dep_graph.entities
        ):
            external_deps.setdefault(edge.target, [])
            if edge.source not in external_deps[edge.target]:
                external_deps[edge.target].append(edge.source)

    broken_contracts = []
    for fqn in sorted(external_deps):
        deps = sorted(external_deps[fqn])
        broken_contracts.append({
            "fqn": fqn,
            "dependents": deps[:20],
            "num_dependents": len(deps),
        })

    return {
        "changed_files": list(changed_files),
        "matched_files": matched_files,
        "unmatched_files": unmatched_files,
        "num_changed_entities": len(changed_entities),
        "changed_entities": changed_entities,
        "affected_components": affected_components,
        "downstream_dependents": downstream_dependents,
        "num_downstream": len(downstream_dependents),
        "broken_contracts": broken_contracts,
    }
