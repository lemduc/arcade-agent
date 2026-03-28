"""Shared test fixtures."""

from pathlib import Path

import pytest

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def java_files():
    return sorted(FIXTURES_DIR.glob("*.java"))


@pytest.fixture
def python_files():
    return sorted(FIXTURES_DIR.glob("*.py"))


@pytest.fixture
def sample_graph():
    """A simple dependency graph for testing."""
    entities = {
        "com.example.calc.Calculator": Entity(
            fqn="com.example.calc.Calculator",
            name="Calculator",
            package="com.example.calc",
            file_path="Calculator.java",
            kind="class",
            language="java",
            imports=["com.example.util.MathHelper"],
        ),
        "com.example.calc.AdvancedCalculator": Entity(
            fqn="com.example.calc.AdvancedCalculator",
            name="AdvancedCalculator",
            package="com.example.calc",
            file_path="AdvancedCalculator.java",
            kind="class",
            language="java",
            imports=["com.example.util.MathHelper"],
            superclass="Calculator",
        ),
        "com.example.util.MathHelper": Entity(
            fqn="com.example.util.MathHelper",
            name="MathHelper",
            package="com.example.util",
            file_path="MathHelper.java",
            kind="class",
            language="java",
        ),
    }
    edges = [
        Edge(
            source="com.example.calc.Calculator",
            target="com.example.util.MathHelper",
            relation="import",
        ),
        Edge(
            source="com.example.calc.AdvancedCalculator",
            target="com.example.util.MathHelper",
            relation="import",
        ),
        Edge(
            source="com.example.calc.AdvancedCalculator",
            target="com.example.calc.Calculator",
            relation="extends",
        ),
    ]
    packages = {
        "com.example.calc": ["com.example.calc.Calculator", "com.example.calc.AdvancedCalculator"],
        "com.example.util": ["com.example.util.MathHelper"],
    }
    return DependencyGraph(entities=entities, edges=edges, packages=packages)


@pytest.fixture
def sample_architecture(sample_graph):
    """A simple architecture for testing."""
    return Architecture(
        components=[
            Component(
                name="Calc",
                responsibility="Calculator functionality",
                entities=["com.example.calc.Calculator", "com.example.calc.AdvancedCalculator"],
            ),
            Component(
                name="Util",
                responsibility="Utility helpers",
                entities=["com.example.util.MathHelper"],
            ),
        ],
        rationale="Package-based grouping",
        algorithm="pkg",
    )
