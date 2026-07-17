"""End-to-end multi-language parse (roadmap #18)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_kotlin")
pytest.importorskip("tree_sitter_java")

from arcade_agent.tools.parse import parse  # noqa: E402


def test_parse_languages_java_kotlin_merges_and_relinks(fixtures_dir: Path):
    root = fixtures_dir / "java_kotlin_mixed"
    graph = parse(str(root), languages=["java", "kotlin"], use_cache=False)

    assert "com.example.mixed.JavaBaseService" in graph.entities
    assert "com.example.mixed.KotlinService" in graph.entities
    assert graph.entities["com.example.mixed.JavaBaseService"].language == "java"
    assert graph.entities["com.example.mixed.KotlinService"].language == "kotlin"

    edge_tuples = set(graph.to_edge_tuples())
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


def test_parse_language_multi_auto_detects_present_languages(fixtures_dir: Path):
    root = fixtures_dir / "java_kotlin_mixed"
    graph = parse(str(root), language="multi", use_cache=False)

    languages = {e.language for e in graph.entities.values()}
    assert languages == {"java", "kotlin"}
    assert any(
        e.relation == "extends"
        and e.source.endswith("KotlinService")
        and e.target.endswith("JavaBaseService")
        for e in graph.edges
    )


def test_parse_single_language_unchanged(fixtures_dir: Path):
    root = fixtures_dir / "java_kotlin_mixed"
    java_only = parse(str(root), language="java", use_cache=False)
    assert all(e.language == "java" for e in java_only.entities.values())
    assert "com.example.mixed.KotlinService" not in java_only.entities


def test_parse_rejects_language_and_languages_together(fixtures_dir: Path):
    root = fixtures_dir / "java_kotlin_mixed"
    with pytest.raises(ValueError, match="language and languages"):
        parse(str(root), language="java", languages=["kotlin"], use_cache=False)
