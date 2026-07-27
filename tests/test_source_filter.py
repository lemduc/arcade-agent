"""Regression tests for shared source-file exclusion policy."""

from pathlib import Path

import pytest

from arcade_agent.source_filter import (
    is_excluded_source_path,
    normalize_exclude_dirs,
)


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


def test_custom_exclusion_matches_exact_relative_directory_and_descendants(
    tmp_path: Path,
):
    exclude_dirs = normalize_exclude_dirs(
        ["integrationTest", "modules/api/spec"],
    )

    assert is_excluded_source_path(
        tmp_path / "integrationTest/java/Example.java",
        tmp_path,
        exclude_defaults=False,
        exclude_dirs=exclude_dirs,
    )
    assert is_excluded_source_path(
        tmp_path / "modules/api/spec/java/Example.java",
        tmp_path,
        exclude_defaults=False,
        exclude_dirs=exclude_dirs,
    )
    assert not is_excluded_source_path(
        tmp_path / "nested/integrationTest/java/Example.java",
        tmp_path,
        exclude_defaults=False,
        exclude_dirs=exclude_dirs,
    )
    assert not is_excluded_source_path(
        tmp_path / "integrationTesting/java/Example.java",
        tmp_path,
        exclude_defaults=False,
        exclude_dirs=exclude_dirs,
    )


def test_custom_exclusions_are_portable_deduplicated_and_ordered():
    assert normalize_exclude_dirs(
        ["src\\e2e", "./integrationTest/", "src/e2e"],
    ) == (
        ("integrationTest",),
        ("src", "e2e"),
    )


@pytest.mark.parametrize(
    "exclude_dir",
    [
        "",
        ".",
        "./",
        "/tmp/tests",
        "C:\\tests",
        "C:tests",
        "../tests",
        "src/../tests",
    ],
)
def test_custom_exclusions_reject_unsafe_or_root_paths(exclude_dir: str):
    with pytest.raises(ValueError, match="exclude_dirs"):
        normalize_exclude_dirs([exclude_dir])
