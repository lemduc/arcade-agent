"""Full ingest → parse → recover E2E for Java+Kotlin polyglot projects."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_kotlin")
pytest.importorskip("tree_sitter_java")

from arcade_agent.tools.ingest import ingest  # noqa: E402
from arcade_agent.tools.parse import parse  # noqa: E402
from arcade_agent.tools.recover import recover  # noqa: E402

_CROSS_LANG_RELATIONS = frozenset({"extends", "implements", "import"})


def _assert_java_kotlin_graph(graph) -> None:
    languages = {e.language for e in graph.entities.values()}
    assert "java" in languages
    assert "kotlin" in languages
    assert any(
        e.relation in _CROSS_LANG_RELATIONS
        and graph.entities[e.source].language != graph.entities[e.target].language
        for e in graph.edges
        if e.source in graph.entities and e.target in graph.entities
    )


def test_pipeline_java_kotlin_mixed_ingest_parse_recover(fixtures_dir: Path):
    root = fixtures_dir / "java_kotlin_mixed"
    repo = ingest(str(root), languages=["java", "kotlin"])
    assert sorted(repo.languages) == ["java", "kotlin"]
    assert any(p.suffix == ".java" for p in repo.source_files)
    assert any(p.suffix == ".kt" for p in repo.source_files)

    graph = parse(
        str(repo.path),
        languages=repo.languages,
        files=[str(f) for f in repo.source_files],
        use_cache=False,
    )
    _assert_java_kotlin_graph(graph)
    assert "com.example.mixed.JavaBaseService" in graph.entities
    assert "com.example.mixed.KotlinService" in graph.entities

    arch = recover(graph, algorithm="pkg")
    assert len(arch.components) > 0
    assert any(c.entities for c in arch.components)


def test_pipeline_maven_java_kotlin_ingest_parse_recover(fixtures_dir: Path):
    root = fixtures_dir / "maven_java_kotlin"
    repo = ingest(str(root), languages=["java", "kotlin"])
    assert sorted(repo.languages) == ["java", "kotlin"]

    graph = parse(
        str(repo.path),
        languages=repo.languages,
        files=[str(f) for f in repo.source_files],
        use_cache=False,
    )
    _assert_java_kotlin_graph(graph)
    assert "com.example.JavaGreeter" in graph.entities
    assert "com.example.KotlinGreeter" in graph.entities
    assert (
        "com.example.KotlinGreeter",
        "com.example.JavaGreeter",
        "extends",
    ) in set(graph.to_edge_tuples())

    arch = recover(graph, algorithm="pkg")
    assert len(arch.components) > 0
