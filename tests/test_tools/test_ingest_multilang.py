"""Multi-language ingest discovery (roadmap #18)."""

from __future__ import annotations

from pathlib import Path

import pytest

from arcade_agent.tools.ingest import ingest


def test_ingest_languages_discovers_both_maven_roots(fixtures_dir: Path):
    root = fixtures_dir / "maven_java_kotlin"
    repo = ingest(str(root), languages=["java", "kotlin"])

    suffixes = {p.suffix for p in repo.source_files}
    assert ".java" in suffixes
    assert ".kt" in suffixes
    assert sorted(repo.languages) == ["java", "kotlin"]
    # Project root kept so both Maven source trees remain visible.
    assert repo.path.resolve() == root.resolve()


def test_ingest_language_multi_finds_java_and_kotlin(fixtures_dir: Path):
    root = fixtures_dir / "maven_java_kotlin"
    repo = ingest(str(root), language="multi")
    assert "java" in repo.languages
    assert "kotlin" in repo.languages
    assert any(p.name == "JavaGreeter.java" for p in repo.source_files)
    assert any(p.name == "KotlinGreeter.kt" for p in repo.source_files)


def test_ingest_single_language_still_narrows_to_matching_root(fixtures_dir: Path):
    root = fixtures_dir / "maven_java_kotlin"
    java_repo = ingest(str(root), language="java")
    assert all(p.suffix == ".java" for p in java_repo.source_files)
    assert java_repo.language == "java"
    assert java_repo.languages == ["java"]


def test_ingest_rejects_language_and_languages_together(fixtures_dir: Path):
    root = fixtures_dir / "maven_java_kotlin"
    with pytest.raises(ValueError, match="language and languages"):
        ingest(str(root), language="java", languages=["kotlin"])
