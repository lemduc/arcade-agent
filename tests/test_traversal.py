"""Tests for the shared graph traversal helpers."""

from arcade_agent.algorithms.traversal import adjacency_with_relations, walk_cone


def test_adjacency_forward(sample_graph):
    adj = adjacency_with_relations(sample_graph, reverse=False)
    # Calculator imports MathHelper (source -> target)
    assert ("com.example.util.MathHelper", "import") in adj["com.example.calc.Calculator"]


def test_adjacency_reverse(sample_graph):
    adj = adjacency_with_relations(sample_graph, reverse=True)
    # MathHelper is imported by both calculators (target -> source)
    sources = {src for src, _rel in adj["com.example.util.MathHelper"]}
    assert sources == {
        "com.example.calc.Calculator",
        "com.example.calc.AdvancedCalculator",
    }


def test_walk_cone_records_distance_and_first_relation():
    adjacency = {"a": [("b", "import")], "b": [("c", "calls")]}
    nodes, truncated = walk_cone(adjacency, ["a"], max_depth=3)
    by_fqn = {n["fqn"]: n for n in nodes}
    assert by_fqn["b"]["distance"] == 1
    assert by_fqn["b"]["via_relation"] == "import"
    # c is reached at depth 2 but carries the FIRST hop's relation
    assert by_fqn["c"]["distance"] == 2
    assert by_fqn["c"]["via_relation"] == "import"
    assert truncated is False


def test_walk_cone_excludes_seeds():
    adjacency = {"a": [("b", "import")]}
    nodes, _ = walk_cone(adjacency, ["a"], max_depth=3)
    assert all(n["fqn"] != "a" for n in nodes)


def test_walk_cone_respects_max_depth():
    adjacency = {"a": [("b", "import")], "b": [("c", "calls")]}
    nodes, _ = walk_cone(adjacency, ["a"], max_depth=1)
    assert {n["fqn"] for n in nodes} == {"b"}


def test_walk_cone_is_cycle_safe():
    adjacency = {"a": [("b", "calls")], "b": [("a", "calls")]}
    nodes, _ = walk_cone(adjacency, ["a"], max_depth=10)
    # Terminates, and does not re-report the seed
    assert {n["fqn"] for n in nodes} == {"b"}


def test_walk_cone_valid_nodes_filters_records_but_still_traverses():
    adjacency = {"a": [("ext", "import")], "ext": [("c", "calls")]}
    nodes, _ = walk_cone(
        adjacency, ["a"], max_depth=3, valid_nodes={"a", "c"}
    )
    fqns = {n["fqn"] for n in nodes}
    # "ext" is traversed (so c is reachable) but not recorded
    assert "ext" not in fqns
    assert "c" in fqns
    assert nodes[[n["fqn"] for n in nodes].index("c")]["distance"] == 2


def test_walk_cone_max_nodes_truncates_closest_first():
    adjacency = {"a": [("b", "r"), ("c", "r")], "b": [("d", "r")]}
    nodes, truncated = walk_cone(adjacency, ["a"], max_depth=3, max_nodes=2)
    assert truncated is True
    assert len(nodes) == 2
    # closest (distance 1) kept before the distance-2 node
    assert {n["fqn"] for n in nodes} == {"b", "c"}
