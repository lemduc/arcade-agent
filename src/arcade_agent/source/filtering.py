"""Shared source-file exclusion policy for repository discovery."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

type ExcludedDirectory = tuple[str, ...]
type ExcludedDirectories = tuple[ExcludedDirectory, ...]

_EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".svn",
        ".venv",
        "__pycache__",
        "__tests__",
        "build",
        "dist",
        "env",
        "ext-tools",
        "external",
        "node_modules",
        "target",
        "test",
        "tests",
        "third-party",
        "third_party",
        "thirdparty",
        "vendor",
        "venv",
    }
)

_JVM_TEST_SOURCE_SET_ALIASES = frozenset({"it"})
_SOURCE_SET_TOKEN_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|[-_.]+")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _source_set_tokens(name: str) -> set[str]:
    """Split Gradle source-set names such as ``integrationTest`` into tokens."""
    return {
        token.casefold()
        for token in _SOURCE_SET_TOKEN_RE.split(name)
        if token
    }


def _is_jvm_test_source_set(parts: tuple[str, ...]) -> bool:
    """Recognize conventional and custom JVM test source sets under ``src``."""
    for index, part in enumerate(parts[:-1]):
        if part.casefold() != "src":
            continue
        source_set = parts[index + 1]
        if source_set.casefold() in _JVM_TEST_SOURCE_SET_ALIASES:
            return True
        if _source_set_tokens(source_set) & {"test", "tests"}:
            return True
    return False


def normalize_exclude_dirs(
    exclude_dirs: Iterable[str] | None,
) -> ExcludedDirectories:
    """Validate and normalize project-relative directory exclusions.

    Values are exact project-relative directory prefixes, not globs. Absolute
    paths, parent traversal, and empty/root paths are rejected at the boundary.
    Both slash styles are accepted so MCP/CI configuration stays portable.
    """
    if exclude_dirs is None:
        return ()

    normalized: set[ExcludedDirectory] = set()
    for raw_value in exclude_dirs:
        value = raw_value.strip().replace("\\", "/")
        if not value or value in {".", "./"}:
            raise ValueError("exclude_dirs entries must name a project-relative directory")
        path = PurePosixPath(value)
        if path.is_absolute() or _WINDOWS_DRIVE_RE.match(value):
            raise ValueError(f"exclude_dirs entries must be relative: {raw_value!r}")
        if ".." in path.parts:
            raise ValueError(f"exclude_dirs entries cannot contain '..': {raw_value!r}")
        parts = tuple(part for part in path.parts if part != ".")
        if not parts:
            raise ValueError("exclude_dirs entries cannot target the project root")
        normalized.add(parts)
    return tuple(sorted(normalized))


def exclusion_cache_namespace(
    exclude_tests: bool,
    exclude_dirs: ExcludedDirectories,
) -> str:
    """Return a stable cache namespace for source-discovery exclusions."""
    return f"default={exclude_tests};extra={exclude_dirs!r}"


def _matches_excluded_directory(
    relative_parts: tuple[str, ...],
    exclude_dirs: ExcludedDirectories,
) -> bool:
    return any(
        relative_parts[: len(directory)] == directory
        for directory in exclude_dirs
    )


def is_excluded_source_path(
    file_path: Path,
    root: Path,
    *,
    exclude_defaults: bool = True,
    exclude_dirs: ExcludedDirectories = (),
) -> bool:
    """Return whether a discovered source file is non-production code.

    The default policy covers common test, dependency, generated-output, and
    virtual environment directories. It also recognizes Gradle test source-set
    names such as ``integrationTest``, ``testFixtures``, ``androidTestDebug``,
    and ``smoke-test`` without treating unrelated names such as ``latest`` as
    tests. ``exclude_dirs`` adds exact project-relative directory prefixes.
    """
    try:
        relative = file_path.relative_to(root)
    except ValueError:
        return False

    parts = relative.parts
    return (
        _matches_excluded_directory(parts, exclude_dirs)
        or (
            exclude_defaults
            and (
                any(part.casefold() in _EXCLUDED_DIRECTORY_NAMES for part in parts)
                or _is_jvm_test_source_set(parts)
            )
        )
    )
