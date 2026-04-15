"""Tests for the explain_component tool."""

from arcade_agent.tools.explain_component import explain_component


def test_explain_component_basic(sample_architecture, sample_graph):
    result = explain_component(sample_architecture, sample_graph, "Calc")
    assert result["name"] == "Calc"
    assert result["responsibility"] == "Calculator functionality"
    assert result["num_entities"] == 2
    assert len(result["entities"]) == 2


def test_explain_component_dependencies(sample_architecture, sample_graph):
    result = explain_component(sample_architecture, sample_graph, "Calc")
    # Calc depends on Util (via MathHelper import)
    assert "Util" in result["depends_on"]
    assert result["outgoing_edges"] > 0


def test_explain_component_depended_on_by(sample_architecture, sample_graph):
    result = explain_component(sample_architecture, sample_graph, "Util")
    # Util is depended on by Calc
    assert "Calc" in result["depended_on_by"]
    assert result["incoming_edges"] > 0


def test_explain_component_api_surface(sample_architecture, sample_graph):
    result = explain_component(sample_architecture, sample_graph, "Util")
    # MathHelper is imported from outside, so it's part of API surface
    assert "com.example.util.MathHelper" in result["api_surface"]


def test_explain_component_cohesion(sample_architecture, sample_graph):
    result = explain_component(sample_architecture, sample_graph, "Calc")
    assert 0.0 <= result["cohesion"] <= 1.0


def test_explain_component_not_found(sample_architecture, sample_graph):
    result = explain_component(sample_architecture, sample_graph, "NonExistent")
    assert "error" in result
    assert "available" in result
    assert "Calc" in result["available"]
    assert "Util" in result["available"]
