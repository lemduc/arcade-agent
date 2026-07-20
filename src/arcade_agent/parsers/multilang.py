"""Cross-language graph merge and edge relinking (roadmap #18)."""

from __future__ import annotations

import logging

from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity

logger = logging.getLogger(__name__)


def resolve_name(
    simple_name: str,
    source_entity: Entity,
    fqn_index: dict[str, str],
    entities: dict[str, Entity],
    aliases: dict[str, str] | None = None,
) -> str | None:
    """Resolve a simple or qualified type name to an entity FQN."""
    if simple_name in entities:
        return simple_name

    if aliases and simple_name in aliases:
        aliased = aliases[simple_name]
        if aliased in entities:
            return aliased

    for imp in source_entity.imports:
        if imp.endswith(f".{simple_name}") and imp in entities:
            return imp

    if source_entity.package:
        same_pkg_fqn = f"{source_entity.package}.{simple_name}"
        if same_pkg_fqn in entities:
            return same_pkg_fqn

    # A qualified name is already explicit. Falling back to its leaf could link
    # an unavailable external type (e.g. external.Base) to an unrelated local
    # Base entity, creating a false cross-language dependency.
    if "." in simple_name:
        return None

    leaf = simple_name.split(".")[-1]
    if leaf in fqn_index:
        return fqn_index[leaf]

    return None


def _aliases_for(entity: Entity) -> dict[str, str]:
    raw = entity.properties.get("import_aliases")
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}


def _build_fqn_index(entities: dict[str, Entity]) -> dict[str, str]:
    candidates: dict[str, list[str]] = {}
    for entity in entities.values():
        candidates.setdefault(entity.name, []).append(entity.fqn)
    # Unqualified fallback is only safe when the leaf name is globally unique.
    return {name: fqns[0] for name, fqns in candidates.items() if len(fqns) == 1}


def relink_edges(graph: DependencyGraph) -> DependencyGraph:
    """Add import/extends/implements edges resolvable against the full entity set.

    Language parsers only resolve against their own entities. After merging
    Java+Kotlin (or other polyglot) graphs, re-run resolution so same-package
    and imported cross-language types become real edges.
    """
    entities = graph.entities
    fqn_index = _build_fqn_index(entities)
    seen = {(e.source, e.target, e.relation) for e in graph.edges}
    new_edges: list[Edge] = list(graph.edges)

    def add(source: str, target: str, relation: str) -> None:
        key = (source, target, relation)
        if key in seen or source == target:
            return
        seen.add(key)
        new_edges.append(Edge(source=source, target=target, relation=relation))

    for entity in entities.values():
        aliases = _aliases_for(entity)
        for imp in entity.imports:
            if imp in entities:
                add(entity.fqn, imp, "import")
            elif "." not in imp:
                resolved = fqn_index.get(imp)
                if resolved and resolved != entity.fqn:
                    add(entity.fqn, resolved, "import")

        if entity.superclass:
            target = resolve_name(
                entity.superclass, entity, fqn_index, entities, aliases
            )
            if target:
                add(entity.fqn, target, "extends")

        for iface in entity.interfaces:
            target = resolve_name(iface, entity, fqn_index, entities, aliases)
            if target:
                add(entity.fqn, target, "implements")

    packages: dict[str, list[str]] = {
        pkg: list(dict.fromkeys(fqns)) for pkg, fqns in graph.packages.items()
    }
    return DependencyGraph(entities=entities, edges=new_edges, packages=packages)


def merge_and_relink(*graphs: DependencyGraph) -> DependencyGraph:
    """Union graphs then relink edges across the combined entity set."""
    if not graphs:
        return DependencyGraph()

    entities: dict[str, Entity] = {}
    edges: list[Edge] = []
    packages: dict[str, list[str]] = {}

    for graph in graphs:
        for fqn, entity in graph.entities.items():
            if fqn in entities:
                existing = entities[fqn]
                if existing.language != entity.language:
                    logger.warning(
                        "FQN collision across languages at %s (%s vs %s); "
                        "keeping first",
                        fqn,
                        existing.language,
                        entity.language,
                    )
                continue
            entities[fqn] = entity
        edges.extend(graph.edges)
        for pkg, fqns in graph.packages.items():
            packages.setdefault(pkg, []).extend(fqns)

    packages = {pkg: list(dict.fromkeys(fqns)) for pkg, fqns in packages.items()}
    return relink_edges(
        DependencyGraph(entities=entities, edges=edges, packages=packages)
    )
