"""Tool: Summarize a codebase for AI agent consumption."""

from collections import Counter
from pathlib import Path

from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.parse import parse
from arcade_agent.tools.registry import tool

# Heuristic patterns for identifying entry points
_ENTRY_POINT_PATTERNS = {
    "Main", "App", "Application", "Server", "CLI",
    "main", "app", "server", "cli", "run", "start",
    "Controller", "Handler", "Router", "Gateway",
}


def _build_package_tree(graph: DependencyGraph) -> list[dict]:
    """Build a package tree with entity counts and kinds."""
    tree: list[dict] = []
    for pkg, fqns in sorted(graph.packages.items()):
        kinds: dict[str, int] = Counter()
        for fqn in fqns:
            entity = graph.entities.get(fqn)
            if entity:
                kinds[entity.kind] = kinds.get(entity.kind, 0) + 1
        tree.append({
            "package": pkg,
            "num_entities": len(fqns),
            "kinds": dict(sorted(kinds.items())),
        })
    return tree


def _find_hotspots(graph: DependencyGraph, top_k: int = 10) -> list[dict]:
    """Find the most-connected entities (dependency hotspots)."""
    in_degree: dict[str, int] = Counter()
    out_degree: dict[str, int] = Counter()
    for edge in graph.edges:
        out_degree[edge.source] += 1
        in_degree[edge.target] += 1

    # Score by total connections
    scores: dict[str, int] = {}
    for fqn in graph.entities:
        scores[fqn] = in_degree.get(fqn, 0) + out_degree.get(fqn, 0)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    results = []
    for fqn, total in ranked:
        entity = graph.entities[fqn]
        results.append({
            "fqn": fqn,
            "name": entity.name,
            "kind": entity.kind,
            "package": entity.package,
            "in_degree": in_degree.get(fqn, 0),
            "out_degree": out_degree.get(fqn, 0),
            "total_connections": total,
        })
    return results


def _find_entry_points(graph: DependencyGraph) -> list[dict]:
    """Heuristically identify entry points based on naming patterns."""
    entries = []
    for fqn, entity in graph.entities.items():
        if entity.name in _ENTRY_POINT_PATTERNS:
            entries.append({
                "fqn": fqn,
                "name": entity.name,
                "kind": entity.kind,
                "file_path": entity.file_path,
            })
    return entries


def _drill_down_package(graph: DependencyGraph, package: str) -> dict:
    """Get detailed info for a specific package."""
    # Find entities in this package (exact or prefix match)
    matching_fqns = set()
    for fqn, entity in graph.entities.items():
        if entity.package == package or entity.package.startswith(package + "."):
            matching_fqns.add(fqn)

    if not matching_fqns:
        return {"error": f"No entities found for package '{package}'"}

    entities = []
    for fqn in sorted(matching_fqns):
        entity = graph.entities[fqn]
        entities.append({
            "fqn": fqn,
            "name": entity.name,
            "kind": entity.kind,
            "file_path": entity.file_path,
        })

    # Dependencies in and out
    deps_in: list[dict] = []
    deps_out: list[dict] = []
    for edge in graph.edges:
        src_in = edge.source in matching_fqns
        tgt_in = edge.target in matching_fqns
        if src_in and not tgt_in:
            deps_out.append({
                "source": edge.source, "target": edge.target, "relation": edge.relation,
            })
        elif tgt_in and not src_in:
            deps_in.append({
                "source": edge.source, "target": edge.target, "relation": edge.relation,
            })

    # Key files
    files = sorted({graph.entities[fqn].file_path for fqn in matching_fqns})

    return {
        "package": package,
        "num_entities": len(entities),
        "entities": entities,
        "dependencies_in": deps_in,
        "dependencies_out": deps_out,
        "num_deps_in": len(deps_in),
        "num_deps_out": len(deps_out),
        "files": files,
    }


@tool(
    name="summarize",
    description="Summarize a codebase for quick understanding. Returns package structure, "
    "dependency hotspots, and entry points. Use focus parameter to drill into a "
    "specific package or area.",
)
def summarize(
    source_path: str,
    language: str | None = None,
    focus: str | None = None,
    use_cache: bool = True,
) -> dict:
    """Summarize a codebase or drill into a specific area.

    Args:
        source_path: Root directory of the project.
        language: Language to parse (auto-detected if None).
        focus: Package name to drill into (e.g. "com.example.auth").
            If None, returns a top-level overview.
        use_cache: Use cached parse results when available.

    Returns:
        Dict with codebase summary or focused drill-down.
    """
    graph = parse(source_path=source_path, language=language, use_cache=use_cache)

    if focus:
        return _drill_down_package(graph, focus)

    # Top-level summary
    root = Path(source_path)
    kind_counts = Counter(e.kind for e in graph.entities.values())
    languages = Counter(e.language for e in graph.entities.values())

    return {
        "project": root.name,
        "language": languages.most_common(1)[0][0] if languages else None,
        "num_entities": graph.num_entities,
        "num_edges": graph.num_edges,
        "num_packages": len(graph.packages),
        "entity_kinds": dict(sorted(kind_counts.items())),
        "packages": _build_package_tree(graph),
        "hotspots": _find_hotspots(graph),
        "entry_points": _find_entry_points(graph),
    }
