"""Tool adapter and compatibility exports for source parsing."""

from arcade_agent.source.parse import (
    _resolve_languages,
    detect_languages_from_files,
    parse,
)
from arcade_agent.tools.registry import tool

tool(
    name="parse",
    description=(
        "Parse source code and extract a dependency graph "
        "with entities, edges, and packages. Automatic discovery excludes "
        "test/vendor/build directories by default and accepts exact custom "
        "directory exclusions."
    ),
)(parse)

__all__ = ["_resolve_languages", "detect_languages_from_files", "parse"]
