"""Shared source-file exclusion policy for repository discovery."""

from __future__ import annotations

import re
from pathlib import Path

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


def is_excluded_source_path(file_path: Path, root: Path) -> bool:
    """Return whether a discovered source file is non-production code.

    The policy covers common test, dependency, generated-output, and virtual
    environment directories. It also recognizes Gradle test source-set names
    such as ``integrationTest``, ``testFixtures``, ``androidTestDebug``, and
    ``smoke-test`` without treating unrelated names such as ``latest`` as tests.
    """
    try:
        relative = file_path.relative_to(root)
    except ValueError:
        return False

    parts = relative.parts
    return (
        any(part.casefold() in _EXCLUDED_DIRECTORY_NAMES for part in parts)
        or _is_jvm_test_source_set(parts)
    )
