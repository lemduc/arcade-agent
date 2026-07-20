"""Tests for DependencyGraph.merge and cross-language relink (roadmap #18)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_kotlin")
pytest.importorskip("tree_sitter_java")

from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity  # noqa: E402
from arcade_agent.parsers.java import JavaParser  # noqa: E402
from arcade_agent.parsers.kotlin import KotlinParser  # noqa: E402
from arcade_agent.parsers.multilang import merge_and_relink, relink_edges  # noqa: E402


def test_merge_unions_entities_and_edges():
    left = DependencyGraph(
        entities={
            "a.A": Entity(
                fqn="a.A",
                name="A",
                package="a",
                file_path="A.java",
                kind="class",
                language="java",
            )
        },
        edges=[Edge(source="a.A", target="a.B", relation="import")],
        packages={"a": ["a.A"]},
    )
    right = DependencyGraph(
        entities={
            "a.B": Entity(
                fqn="a.B",
                name="B",
                package="a",
                file_path="B.kt",
                kind="class",
                language="kotlin",
            )
        },
        edges=[],
        packages={"a": ["a.B"]},
    )

    merged = left.merge(right)
    assert set(merged.entities) == {"a.A", "a.B"}
    assert merged.num_edges == 1
    assert sorted(merged.packages["a"]) == ["a.A", "a.B"]


def test_naive_merge_misses_cross_language_extends(fixtures_dir: Path):
    root = fixtures_dir / "java_kotlin_mixed"
    java_files = sorted(root.rglob("*.java"))
    kotlin_files = sorted(root.rglob("*.kt"))

    java_graph = JavaParser().parse(java_files, root)
    kotlin_graph = KotlinParser().parse(kotlin_files, root)
    naive = java_graph.merge(kotlin_graph)

    edge_tuples = set(naive.to_edge_tuples())
    assert (
        "com.example.mixed.KotlinService",
        "com.example.mixed.JavaBaseService",
        "extends",
    ) not in edge_tuples


def test_relink_adds_cross_language_extends_and_implements(fixtures_dir: Path):
    root = fixtures_dir / "java_kotlin_mixed"
    java_files = sorted(root.rglob("*.java"))
    kotlin_files = sorted(root.rglob("*.kt"))

    java_graph = JavaParser().parse(java_files, root)
    kotlin_graph = KotlinParser().parse(kotlin_files, root)
    linked = merge_and_relink(java_graph, kotlin_graph)

    edge_tuples = set(linked.to_edge_tuples())
    assert (
        "com.example.mixed.KotlinService",
        "com.example.mixed.JavaBaseService",
        "extends",
    ) in edge_tuples
    assert (
        "com.example.mixed.KotlinService",
        "com.example.mixed.SharedContract",
        "implements",
    ) in edge_tuples


def test_relink_is_idempotent(fixtures_dir: Path):
    root = fixtures_dir / "java_kotlin_mixed"
    java_files = sorted(root.rglob("*.java"))
    kotlin_files = sorted(root.rglob("*.kt"))
    linked = merge_and_relink(
        JavaParser().parse(java_files, root),
        KotlinParser().parse(kotlin_files, root),
    )
    again = relink_edges(linked)
    assert set(again.to_edge_tuples()) == set(linked.to_edge_tuples())


def test_merge_and_relink_keeps_first_on_cross_language_fqn_collision():
    left = DependencyGraph(
        entities={
            "a.Shared": Entity(
                fqn="a.Shared",
                name="Shared",
                package="a",
                file_path="Shared.java",
                kind="class",
                language="java",
            )
        },
        packages={"a": ["a.Shared"]},
    )
    right = DependencyGraph(
        entities={
            "a.Shared": Entity(
                fqn="a.Shared",
                name="Shared",
                package="a",
                file_path="Shared.kt",
                kind="class",
                language="kotlin",
            )
        },
        packages={"a": ["a.Shared"]},
    )

    merged = merge_and_relink(left, right)
    assert merged.entities["a.Shared"].language == "java"
    assert merged.entities["a.Shared"].file_path == "Shared.java"


def test_relink_does_not_resolve_qualified_external_name_to_local_leaf():
    graph = DependencyGraph(
        entities={
            "app.Consumer": Entity(
                fqn="app.Consumer",
                name="Consumer",
                package="app",
                file_path="Consumer.kt",
                kind="class",
                language="kotlin",
                superclass="external.Base",
                imports=["external.Contract"],
            ),
            "app.Base": Entity(
                fqn="app.Base",
                name="Base",
                package="app",
                file_path="Base.java",
                kind="class",
                language="java",
            ),
            "app.Contract": Entity(
                fqn="app.Contract",
                name="Contract",
                package="app",
                file_path="Contract.java",
                kind="interface",
                language="java",
            ),
        }
    )

    assert relink_edges(graph).edges == []


def test_relink_does_not_guess_when_simple_name_is_ambiguous():
    graph = DependencyGraph(
        entities={
            "consumer.Child": Entity(
                fqn="consumer.Child",
                name="Child",
                package="consumer",
                file_path="Child.kt",
                kind="class",
                language="kotlin",
                superclass="Base",
            ),
            "one.Base": Entity(
                fqn="one.Base",
                name="Base",
                package="one",
                file_path="Base.java",
                kind="class",
                language="java",
            ),
            "two.Base": Entity(
                fqn="two.Base",
                name="Base",
                package="two",
                file_path="Base.kt",
                kind="class",
                language="kotlin",
            ),
        }
    )

    assert relink_edges(graph).edges == []
