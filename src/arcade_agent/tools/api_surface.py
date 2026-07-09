"""Tool: Extract the public API surface of a codebase."""

from typing import Any

from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool

_NOTE = (
    "Public API surface only: implementation bodies, private members, and "
    "parameter/return types are omitted (parsers store no signatures). A "
    "'signature' here is name + kind (+ superclass/interfaces for types). "
    "Public is derived, not read from a field: an entity is treated as public "
    "unless its simple name starts with '_' (Python private convention); "
    "'depended_on' additionally flags entities with incoming edges from outside "
    "their own file."
)


def _is_public(name: str) -> bool:
    """Return whether a simple name is public by Python naming convention.

    Args:
        name: The entity's simple (unqualified) name.

    Returns:
        True unless the name starts with a single underscore (private).
    """
    return not name.startswith("_")


def _external_dependents(dep_graph: DependencyGraph) -> set[str]:
    """Find entities that have incoming edges from a different file.

    An entity is part of the structural public surface if something outside
    its own file depends on it. This is the same kind of signal
    ``explain_component`` uses to derive ``api_surface`` — incoming edges from
    outside a boundary — but the boundary here is the *file*, not a recovered
    component, so the two results differ for components spanning several files.

    Args:
        dep_graph: The dependency graph to inspect.

    Returns:
        Set of FQNs that are depended on from outside their own file.
    """
    depended_on: set[str] = set()
    entities = dep_graph.entities
    for edge in dep_graph.edges:
        src = entities.get(edge.source)
        tgt = entities.get(edge.target)
        if tgt is None:
            continue
        # Structural signal: incoming edge originating from a different file.
        if src is None or src.file_path != tgt.file_path:
            depended_on.add(edge.target)
    return depended_on


@tool(
    name="api_surface",
    description="Extract the public API surface of a codebase — public top-level "
    "types and their public members, grouped by package. Omits implementation "
    "detail and parameter types (the 'what can I call' view).",
)
def api_surface(
    dep_graph: DependencyGraph,
    scope: str | None = None,
    include_members: bool = True,
) -> dict[str, Any]:
    """Extract only the public interface of a codebase.

    Public is *derived*, never read from a field (the graph has no visibility
    attribute). The naming heuristic is used: an entity is public unless its
    simple name starts with an underscore (Python private convention). The
    structural signal is surfaced as ``depended_on``: an entity is flagged when
    it has incoming edges from outside its own file, exactly as
    ``explain_component`` computes ``api_surface``.

    Output is grouped by package, then by top-level type/function. Methods and
    functions carrying ``properties["owner"]`` are nested as ``members`` under
    their owner type (only when ``include_members`` is True and the member is
    public); members whose owner is absent from the graph are skipped.

    Signatures are name + kind (+ superclass/interfaces for types) — parameter
    and return types are never fabricated. Implementation bodies are omitted.

    Args:
        dep_graph: Dependency graph to extract the public surface from.
        scope: Optional package prefix; only entities whose package starts with
            it are included.
        include_members: Nest public members under their owner type when True.

    Returns:
        Dict with keys: ``scope``, ``note``, ``num_public_entities``, and
        ``packages`` — a list of ``{package, entities}`` where each entity is
        ``{fqn, name, kind, superclass?, interfaces?, depended_on, members?}``.
    """
    depended_on = _external_dependents(dep_graph)

    # Partition entities into top-level types/functions and owned members.
    top_level: list[str] = []
    members_by_owner: dict[str, list[str]] = {}

    for fqn, entity in dep_graph.entities.items():
        if scope and not entity.package.startswith(scope):
            continue
        if not _is_public(entity.name):
            continue
        owner = entity.properties.get("owner")
        if owner is not None:
            members_by_owner.setdefault(owner, []).append(fqn)
        else:
            top_level.append(fqn)

    # Group top-level entities by package.
    packages: dict[str, list[dict[str, Any]]] = {}
    num_public = 0

    for fqn in sorted(top_level):
        entity = dep_graph.entities[fqn]
        record: dict[str, Any] = {
            "fqn": fqn,
            "name": entity.name,
            "kind": entity.kind,
            "depended_on": fqn in depended_on,
        }
        if entity.superclass:
            record["superclass"] = entity.superclass
        if entity.interfaces:
            record["interfaces"] = list(entity.interfaces)

        if include_members:
            member_records: list[dict[str, Any]] = []
            for member_fqn in sorted(members_by_owner.get(fqn, [])):
                member = dep_graph.entities[member_fqn]
                member_records.append({
                    "fqn": member_fqn,
                    "name": member.name,
                    "kind": member.kind,
                })
            if member_records:
                record["members"] = member_records

        packages.setdefault(entity.package, []).append(record)
        num_public += 1

    package_list = [
        {"package": pkg, "entities": entities}
        for pkg, entities in sorted(packages.items())
    ]

    return {
        "scope": scope,
        "note": _NOTE,
        "num_public_entities": num_public,
        "packages": package_list,
    }
