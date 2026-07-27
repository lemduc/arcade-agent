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


def test_ingest_polyglot_excludes_jvm_test_source_sets_by_default(
    jvm_project_with_tests: Path,
):
    repo = ingest(
        str(jvm_project_with_tests),
        languages=["java", "kotlin"],
    )

    relative_files = {
        path.relative_to(jvm_project_with_tests).as_posix()
        for path in repo.source_files
    }
    assert relative_files == {
        "src/latest/java/com/example/LatestJava.java",
        "src/main/java/com/example/MainJava.java",
        "src/main/kotlin/com/example/MainKotlin.kt",
    }


def test_ingest_polyglot_can_include_jvm_test_source_sets(
    jvm_project_with_tests: Path,
):
    repo = ingest(
        str(jvm_project_with_tests),
        languages=["java", "kotlin"],
        exclude_tests=False,
    )

    relative_files = {
        path.relative_to(jvm_project_with_tests).as_posix()
        for path in repo.source_files
    }
    assert "src/test/java/com/example/UnitJavaTest.java" in relative_files
    assert "src/test/kotlin/com/example/UnitKotlinTest.kt" in relative_files
    assert (
        "src/integrationTest/java/com/example/IntegrationJavaTest.java"
        in relative_files
    )
    assert (
        "src/testFixtures/kotlin/com/example/FixtureKotlin.kt"
        in relative_files
    )


def test_ingest_excludes_exact_custom_directories(
    jvm_project_with_custom_layout: Path,
):
    repo = ingest(
        str(jvm_project_with_custom_layout),
        languages=["java", "kotlin"],
        exclude_dirs=["integrationTest", "src/e2e", "modules/api/spec"],
    )

    relative_files = {
        path.relative_to(jvm_project_with_custom_layout).as_posix()
        for path in repo.source_files
    }
    assert relative_files == {
        "integrationTesting/java/com/example/ProductionSupport.java",
        "src/main/java/com/example/Main.java",
    }


def test_ingest_custom_directories_apply_when_default_policy_is_disabled(
    jvm_project_with_custom_layout: Path,
):
    repo = ingest(
        str(jvm_project_with_custom_layout),
        languages=["java", "kotlin"],
        exclude_tests=False,
        exclude_dirs=["integrationTest"],
    )

    relative_files = {
        path.relative_to(jvm_project_with_custom_layout).as_posix()
        for path in repo.source_files
    }
    assert "integrationTest/java/com/example/CustomIntegration.java" not in relative_files
    assert "src/e2e/kotlin/com/example/E2eScenario.kt" in relative_files


def test_ingest_multi_detection_ignores_language_only_in_custom_exclusion(
    jvm_project_with_custom_layout: Path,
):
    repo = ingest(
        str(jvm_project_with_custom_layout),
        language="multi",
        exclude_dirs=["src/e2e"],
    )

    assert repo.language == "java"
    assert repo.languages == ["java"]


def test_ingest_auto_detection_ignores_test_only_language(tmp_path: Path):
    java_main = tmp_path / "src/main/java/com/example/Main.java"
    java_main.parent.mkdir(parents=True)
    java_main.write_text("package com.example; public class Main {}\n")
    kotlin_test = tmp_path / "src/test/kotlin/com/example/OnlyInTests.kt"
    kotlin_test.parent.mkdir(parents=True)
    kotlin_test.write_text("package com.example\nclass OnlyInTests\n")

    repo = ingest(str(tmp_path))

    assert repo.language == "java"
    assert repo.languages == ["java"]
    assert repo.source_files == [java_main]


def test_ingest_multi_detection_ignores_test_only_language(tmp_path: Path):
    java_main = tmp_path / "src/main/java/com/example/Main.java"
    java_main.parent.mkdir(parents=True)
    java_main.write_text("package com.example; public class Main {}\n")
    kotlin_test = tmp_path / "src/test/kotlin/com/example/OnlyInTests.kt"
    kotlin_test.parent.mkdir(parents=True)
    kotlin_test.write_text("package com.example\nclass OnlyInTests\n")

    repo = ingest(str(tmp_path), language="multi")

    assert repo.language == "java"
    assert repo.languages == ["java"]
    assert repo.source_files == [java_main]


def test_ingest_rejects_language_and_languages_together(fixtures_dir: Path):
    root = fixtures_dir / "maven_java_kotlin"
    with pytest.raises(ValueError, match="language and languages"):
        ingest(str(root), language="java", languages=["kotlin"])


def test_ingest_rejects_unknown_languages(fixtures_dir: Path):
    root = fixtures_dir / "maven_java_kotlin"
    with pytest.raises(ValueError, match="Unknown language"):
        ingest(str(root), languages=["java", "cobol"])


def test_ingest_rejects_unknown_single_language(fixtures_dir: Path):
    root = fixtures_dir / "maven_java_kotlin"
    with pytest.raises(ValueError, match="Unknown language"):
        ingest(str(root), language="cobol")
