"""Regression tests for shared source-file exclusion policy."""

from pathlib import Path

import pytest

from arcade_agent.source_filter import is_excluded_source_path


@pytest.mark.parametrize(
    "relative_path",
    [
        "src/test/java/com/example/ExampleTest.java",
        "src/tests/kotlin/com/example/ExampleTest.kt",
        "src/integrationTest/java/com/example/ExampleIT.java",
        "src/integration-test/kotlin/com/example/ExampleIT.kt",
        "src/testFixtures/java/com/example/Fixture.java",
        "src/androidTestDebug/kotlin/com/example/DeviceTest.kt",
        "src/smokeTest/java/com/example/SmokeTest.java",
        "src/it/kotlin/com/example/IntegrationSpec.kt",
        "Tests/ExampleTest.java",
        "__tests__/example.ts",
        "vendor/example.py",
        "build/generated/Generated.java",
    ],
)
def test_excludes_test_and_non_production_paths(
    tmp_path: Path,
    relative_path: str,
):
    assert is_excluded_source_path(tmp_path / relative_path, tmp_path)


@pytest.mark.parametrize(
    "relative_path",
    [
        "src/main/java/com/example/Contest.java",
        "src/main/kotlin/com/example/Latest.kt",
        "src/latest/java/com/example/Latest.java",
        "src/main/java/com/example/testing/Testing.java",
    ],
)
def test_keeps_production_paths_with_test_substrings(
    tmp_path: Path,
    relative_path: str,
):
    assert not is_excluded_source_path(tmp_path / relative_path, tmp_path)


def test_path_outside_root_is_not_excluded(tmp_path: Path):
    assert not is_excluded_source_path(
        tmp_path.parent / "tests" / "Outside.java",
        tmp_path,
    )
