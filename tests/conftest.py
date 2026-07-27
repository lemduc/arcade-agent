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
def kotlin_files():
    return sorted((FIXTURES_DIR / "kotlin_project").rglob("*.kt"))


@pytest.fixture
def kotlin_embabel_pattern_files():
    return sorted((FIXTURES_DIR / "kotlin_embabel_patterns").rglob("*.kt"))


@pytest.fixture
def jvm_project_with_tests(tmp_path: Path) -> Path:
    """Create a JVM project with main, test, and custom Gradle source sets."""
    sources = {
        "src/main/java/com/example/MainJava.java": (
            "package com.example; public class MainJava {}\n"
        ),
        "src/main/kotlin/com/example/MainKotlin.kt": (
            "package com.example\nclass MainKotlin\n"
        ),
        "src/test/java/com/example/UnitJavaTest.java": (
            "package com.example; public class UnitJavaTest {}\n"
        ),
        "src/test/kotlin/com/example/UnitKotlinTest.kt": (
            "package com.example\nclass UnitKotlinTest\n"
        ),
        "src/integrationTest/java/com/example/IntegrationJavaTest.java": (
            "package com.example; public class IntegrationJavaTest {}\n"
        ),
        "src/integrationTest/kotlin/com/example/IntegrationKotlinTest.kt": (
            "package com.example\nclass IntegrationKotlinTest\n"
        ),
        "src/testFixtures/java/com/example/FixtureJava.java": (
            "package com.example; public class FixtureJava {}\n"
        ),
        "src/testFixtures/kotlin/com/example/FixtureKotlin.kt": (
            "package com.example\nclass FixtureKotlin\n"
        ),
        "src/latest/java/com/example/LatestJava.java": (
            "package com.example; public class LatestJava {}\n"
        ),
    }
    for relative_path, source in sources.items():
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source)
    return tmp_path


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
