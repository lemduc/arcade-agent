"""Tests for the Java parser."""

from pathlib import Path

from arcade_agent.parsers.java import JavaParser


def test_java_parser_entities(java_files, fixtures_dir):
    parser = JavaParser()
    graph = parser.parse(java_files, fixtures_dir)

    assert graph.num_entities >= 3
    assert "com.example.calc.Calculator" in graph.entities
    assert "com.example.util.MathHelper" in graph.entities
    assert "com.example.calc.AdvancedCalculator" in graph.entities


def test_java_parser_entity_details(java_files, fixtures_dir):
    parser = JavaParser()
    graph = parser.parse(java_files, fixtures_dir)

    calc = graph.entities["com.example.calc.Calculator"]
    assert calc.name == "Calculator"
    assert calc.package == "com.example.calc"
    assert calc.kind == "class"
    assert calc.language == "java"
    assert "com.example.util.MathHelper" in calc.imports


def test_java_parser_edges(java_files, fixtures_dir):
    parser = JavaParser()
    graph = parser.parse(java_files, fixtures_dir)

    edge_tuples = {(e.source, e.target, e.relation) for e in graph.edges}

    # Calculator imports MathHelper
    assert ("com.example.calc.Calculator", "com.example.util.MathHelper", "import") in edge_tuples

    # AdvancedCalculator extends Calculator
    assert (
        "com.example.calc.AdvancedCalculator",
        "com.example.calc.Calculator",
        "extends",
    ) in edge_tuples


def test_java_parser_packages(java_files, fixtures_dir):
    parser = JavaParser()
    graph = parser.parse(java_files, fixtures_dir)

    assert "com.example.calc" in graph.packages
    assert "com.example.util" in graph.packages
    assert len(graph.packages["com.example.calc"]) >= 2
    assert len(graph.packages["com.example.util"]) >= 1


def test_java_parser_empty():
    parser = JavaParser()
    graph = parser.parse([], Path("/tmp"))
    assert graph.num_entities == 0
    assert graph.num_edges == 0


def test_java_parser_properties():
    parser = JavaParser()
    assert parser.language == "java"
    assert ".java" in parser.file_extensions


def test_java_parser_extracts_methods(java_files, fixtures_dir):
    parser = JavaParser()
    graph = parser.parse(java_files, fixtures_dir)

    assert "com.example.calc.Calculator.add" in graph.entities
    assert graph.entities["com.example.calc.Calculator.add"].kind == "method"
    assert graph.entities["com.example.calc.Calculator.add"].properties["owner"] == (
        "com.example.calc.Calculator"
    )
