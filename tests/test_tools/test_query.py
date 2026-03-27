"""Tests for the query tool."""

from arcade_agent.tools.query import query


def test_query_component_of(sample_architecture, sample_graph):
    result = query(
        sample_architecture, sample_graph,
        question="component_of",
        entity="com.example.calc.Calculator",
    )
    assert result["component"] == "Calc"


def test_query_dependencies(sample_architecture, sample_graph):
    result = query(
        sample_architecture, sample_graph,
        question="dependencies",
        component="Calc",
    )
    assert "Util" in result["dependencies"]


def test_query_summary(sample_architecture, sample_graph):
    result = query(
        sample_architecture, sample_graph,
        question="summary",
    )
    assert result["num_components"] == 2
    assert result["num_entities"] == 3


def test_query_largest(sample_architecture, sample_graph):
    result = query(
        sample_architecture, sample_graph,
        question="largest",
    )
    assert len(result["largest_components"]) == 2
    assert result["largest_components"][0]["entity_count"] == 2


def test_query_unknown(sample_architecture, sample_graph):
    result = query(
        sample_architecture, sample_graph,
        question="nonexistent",
    )
    assert "error" in result
