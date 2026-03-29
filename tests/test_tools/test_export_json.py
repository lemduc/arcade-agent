"""Tests for JSON export summaries."""

import json

from arcade_agent.exporters.json import (
    build_component_summary,
    build_graph_summary,
    export_json,
)
from arcade_agent.parsers.graph import Entity


def test_build_graph_summary_includes_kind_counts(sample_graph):
    sample_graph.entities["com.example.calc.calculate"] = Entity(
        fqn="com.example.calc.calculate",
        name="calculate",
        package="com.example.calc",
        file_path="calc.py",
        kind="function",
        language="python",
    )
    sample_graph.entities["com.example.calc.Calculator.add"] = Entity(
        fqn="com.example.calc.Calculator.add",
        name="add",
        package="com.example.calc",
        file_path="Calculator.java",
        kind="method",
        language="java",
    )

    summary = build_graph_summary(sample_graph)

    assert summary["num_entities"] == 5
    assert summary["class_count"] == 3
    assert summary["function_count"] == 1
    assert summary["method_count"] == 1
    assert summary["entity_kind_counts"] == {
        "class": 3,
        "function": 1,
        "method": 1,
    }


def test_build_component_summary_includes_kind_counts(sample_graph, sample_architecture):
    sample_graph.entities["com.example.calc.calculate"] = Entity(
        fqn="com.example.calc.calculate",
        name="calculate",
        package="com.example.calc",
        file_path="calc.py",
        kind="function",
        language="python",
    )
    sample_architecture.components[0].entities.append("com.example.calc.calculate")

    component = build_component_summary(sample_architecture.components[0], sample_graph)

    assert component["num_entities"] == 3
    assert component["class_count"] == 2
    assert component["function_count"] == 1
    assert component["method_count"] == 0
    assert component["entity_kind_counts"] == {
        "class": 2,
        "function": 1,
    }


def test_build_component_summary_includes_owned_methods(sample_graph, sample_architecture):
    sample_graph.entities["com.example.calc.Calculator.add"] = Entity(
        fqn="com.example.calc.Calculator.add",
        name="add",
        package="com.example.calc",
        file_path="Calculator.java",
        kind="method",
        language="java",
        properties={"owner": "com.example.calc.Calculator"},
    )

    component = build_component_summary(sample_architecture.components[0], sample_graph)

    assert component["class_count"] == 2
    assert component["method_count"] == 1
    assert component["entity_kind_counts"] == {
        "class": 2,
        "method": 1,
    }


def test_export_json_embeds_derived_counts(sample_graph, sample_architecture):
    payload = json.loads(export_json(sample_graph, sample_architecture))

    assert payload["graph"]["class_count"] == 3
    assert payload["graph"]["function_count"] == 0
    assert payload["graph"]["method_count"] == 0
    assert payload["graph"]["entity_kind_counts"] == {"class": 3}
    assert payload["architecture"]["components"][0]["class_count"] == 2
    assert payload["architecture"]["components"][0]["function_count"] == 0
