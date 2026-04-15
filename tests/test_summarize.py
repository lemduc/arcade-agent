"""Tests for the summarize tool."""

from arcade_agent.tools.summarize import (
    _build_package_tree,
    _drill_down_package,
    _find_entry_points,
    _find_hotspots,
)


def test_build_package_tree(sample_graph):
    tree = _build_package_tree(sample_graph)
    assert len(tree) == 2
    pkgs = {p["package"] for p in tree}
    assert "com.example.calc" in pkgs
    assert "com.example.util" in pkgs
    calc = next(p for p in tree if p["package"] == "com.example.calc")
    assert calc["num_entities"] == 2
    assert calc["kinds"]["class"] == 2


def test_find_hotspots(sample_graph):
    hotspots = _find_hotspots(sample_graph, top_k=5)
    assert len(hotspots) > 0
    # MathHelper is imported by 2 entities, should be a hotspot
    fqns = [h["fqn"] for h in hotspots]
    assert "com.example.util.MathHelper" in fqns
    math_helper = next(h for h in hotspots if h["fqn"] == "com.example.util.MathHelper")
    assert math_helper["in_degree"] == 2


def test_find_entry_points(sample_graph):
    # No entry point patterns in sample graph
    entries = _find_entry_points(sample_graph)
    assert entries == []


def test_find_entry_points_with_main(sample_graph):
    from arcade_agent.parsers.graph import Entity
    sample_graph.entities["com.example.Main"] = Entity(
        fqn="com.example.Main", name="Main", package="com.example",
        file_path="Main.java", kind="class", language="java",
    )
    entries = _find_entry_points(sample_graph)
    assert len(entries) == 1
    assert entries[0]["name"] == "Main"


def test_drill_down_package(sample_graph):
    result = _drill_down_package(sample_graph, "com.example.calc")
    assert result["package"] == "com.example.calc"
    assert result["num_entities"] == 2
    fqns = [e["fqn"] for e in result["entities"]]
    assert "com.example.calc.Calculator" in fqns
    assert "com.example.calc.AdvancedCalculator" in fqns
    # Should have outgoing deps to MathHelper
    assert result["num_deps_out"] > 0
    assert len(result["files"]) > 0


def test_drill_down_nonexistent_package(sample_graph):
    result = _drill_down_package(sample_graph, "com.nonexistent")
    assert "error" in result


def test_drill_down_prefix_match(sample_graph):
    # "com.example" should match both sub-packages
    result = _drill_down_package(sample_graph, "com.example")
    assert result["num_entities"] == 3
