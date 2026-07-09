"""Tests for the api_surface tool."""

from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.tools.api_surface import api_surface


def _member(fqn: str, name: str, package: str, file_path: str, owner: str) -> Entity:
    """Build a method/function entity owned by a type."""
    return Entity(
        fqn=fqn,
        name=name,
        package=package,
        file_path=file_path,
        kind="method",
        language="java",
        properties={"owner": owner},
    )


def test_happy_path_groups_by_package(sample_graph):
    """Public top-level types are grouped by package."""
    result = api_surface(sample_graph)

    assert result["scope"] is None
    assert "note" in result and result["note"]
    assert result["num_public_entities"] == 3

    packages = {p["package"]: p for p in result["packages"]}
    assert set(packages) == {"com.example.calc", "com.example.util"}

    calc_names = {e["name"] for e in packages["com.example.calc"]["entities"]}
    assert calc_names == {"Calculator", "AdvancedCalculator"}

    # AdvancedCalculator exposes its superclass in the signature.
    adv = next(
        e for e in packages["com.example.calc"]["entities"]
        if e["name"] == "AdvancedCalculator"
    )
    assert adv["superclass"] == "Calculator"
    assert adv["kind"] == "class"


def test_depended_on_from_external_file(sample_graph):
    """MathHelper is depended on from another file, so it is flagged."""
    result = api_surface(sample_graph)
    packages = {p["package"]: p for p in result["packages"]}

    helper = packages["com.example.util"]["entities"][0]
    assert helper["name"] == "MathHelper"
    assert helper["depended_on"] is True


def test_private_entities_excluded():
    """Underscore-prefixed names are excluded from the public surface."""
    graph = DependencyGraph(
        entities={
            "pkg.Public": Entity("pkg.Public", "Public", "pkg", "a.py", "class", "python"),
            "pkg._Private": Entity("pkg._Private", "_Private", "pkg", "a.py", "class", "python"),
        }
    )
    result = api_surface(graph)
    names = {
        e["name"]
        for p in result["packages"]
        for e in p["entities"]
    }
    assert names == {"Public"}
    assert result["num_public_entities"] == 1


def test_members_nested_under_owner():
    """Public members nest under their owner; private members are dropped."""
    graph = DependencyGraph(
        entities={
            "pkg.Svc": Entity("pkg.Svc", "Svc", "pkg", "svc.py", "class", "python"),
            "pkg.Svc.run": _member("pkg.Svc.run", "run", "pkg", "svc.py", "pkg.Svc"),
            "pkg.Svc._helper": _member(
                "pkg.Svc._helper", "_helper", "pkg", "svc.py", "pkg.Svc"
            ),
        }
    )
    result = api_surface(graph)
    svc = result["packages"][0]["entities"][0]
    assert svc["name"] == "Svc"
    member_names = {m["name"] for m in svc["members"]}
    assert member_names == {"run"}
    # Members are not counted as top-level public entities.
    assert result["num_public_entities"] == 1


def test_include_members_false_omits_members():
    """When include_members is False, no members key is emitted."""
    graph = DependencyGraph(
        entities={
            "pkg.Svc": Entity("pkg.Svc", "Svc", "pkg", "svc.py", "class", "python"),
            "pkg.Svc.run": _member("pkg.Svc.run", "run", "pkg", "svc.py", "pkg.Svc"),
        }
    )
    result = api_surface(graph, include_members=False)
    svc = result["packages"][0]["entities"][0]
    assert "members" not in svc


def test_member_with_missing_owner_is_skipped():
    """A member whose owner is absent from the graph is not attached anywhere."""
    graph = DependencyGraph(
        entities={
            "pkg.orphan": _member("pkg.orphan", "orphan", "pkg", "x.py", "pkg.Gone"),
        }
    )
    result = api_surface(graph)
    # No top-level types, so nothing surfaces.
    assert result["num_public_entities"] == 0
    assert result["packages"] == []


def test_scope_filters_by_package_prefix(sample_graph):
    """Scope limits results to entities whose package starts with the prefix."""
    result = api_surface(sample_graph, scope="com.example.util")
    assert result["scope"] == "com.example.util"
    assert result["num_public_entities"] == 1
    assert len(result["packages"]) == 1
    assert result["packages"][0]["package"] == "com.example.util"


def test_empty_graph():
    """An empty graph yields an empty public surface."""
    result = api_surface(DependencyGraph())
    assert result["num_public_entities"] == 0
    assert result["packages"] == []


def test_no_match_scope(sample_graph):
    """A scope matching nothing returns an empty package list."""
    result = api_surface(sample_graph, scope="org.nomatch")
    assert result["num_public_entities"] == 0
    assert result["packages"] == []


def test_cyclic_edges_do_not_hang():
    """Cyclic dependency edges are handled without infinite looping."""
    graph = DependencyGraph(
        entities={
            "pkg.A": Entity("pkg.A", "A", "pkg", "a.py", "class", "python"),
            "pkg.B": Entity("pkg.B", "B", "pkg", "b.py", "class", "python"),
        },
        edges=[
            Edge("pkg.A", "pkg.B", "uses"),
            Edge("pkg.B", "pkg.A", "uses"),
        ],
    )
    result = api_surface(graph)
    flagged = {
        e["name"]: e["depended_on"]
        for p in result["packages"]
        for e in p["entities"]
    }
    # Both are depended on across file boundaries.
    assert flagged == {"A": True, "B": True}
