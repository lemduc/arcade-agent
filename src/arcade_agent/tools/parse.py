"""Tool: Parse source code and extract dependency graph."""

import logging
from pathlib import Path

from arcade_agent.cache import cache_key, get_cached_graph, put_cached_graph
from arcade_agent.parsers.base import detect_language, get_parser
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool

logger = logging.getLogger(__name__)


@tool(
    name="parse",
    description=(
        "Parse source code and extract a dependency graph "
        "with entities, edges, and packages."
    ),
)
def parse(
    source_path: str,
    language: str | None = None,
    files: list[str] | None = None,
    use_cache: bool = True,
    exclude_tests: bool = True,
) -> DependencyGraph:
    """Parse source code and extract a dependency graph.

    Args:
        source_path: Root directory of the project.
        language: Language to parse (java, python, etc.). Auto-detected if None.
        files: Specific files to parse. If None, discovers all files.
        use_cache: If True, return cached results when source files haven't changed.
        exclude_tests: If True, parsers that recognize inline test constructs
            (e.g. Rust's ``#[cfg(test)] mod tests``) leave them out of the graph.
            Mirrors the `ingest` flag, which only excludes whole test *paths*.

    Returns:
        DependencyGraph with entities, edges, and package info.
    """
    root = Path(source_path)

    # Check cache before doing expensive parsing
    if use_cache:
        key = cache_key(source_path, language, files, exclude_tests)
        cached = get_cached_graph(source_path, key)
        if cached is not None:
            return cached

    if files:
        file_paths = [Path(f) for f in files]
    else:
        # Discover files
        if language:
            parser = get_parser(language)
            file_paths = []
            for ext in parser.file_extensions:
                file_paths.extend(sorted(root.rglob(f"*{ext}")))
        else:
            # Try to detect language from files
            all_files = list(root.rglob("*"))
            source_files = [f for f in all_files if f.is_file()]
            detected = detect_language(source_files)
            if not detected:
                raise ValueError(f"Could not detect language in {source_path}")
            language = detected
            parser = get_parser(language)
            file_paths = []
            for ext in parser.file_extensions:
                file_paths.extend(sorted(root.rglob(f"*{ext}")))

    if not language:
        raise ValueError("No language specified and auto-detection failed")

    parser = get_parser(language)
    parser.exclude_tests = exclude_tests

    # Two cache layers: the whole-graph cache above returns instantly when NOTHING
    # changed; when some files changed we fall here and parse incrementally —
    # re-extracting only the changed files (by content hash) and re-linking. Edges
    # are recomputed every link, so the incremental graph is identical to a full
    # parse. Parsers that don't support it (or use_cache=False) take the full path.
    if use_cache and hasattr(parser, "parse_incremental"):
        from arcade_agent.incremental import ExtractCache
        graph = parser.parse_incremental(file_paths, root, ExtractCache(root))
    else:
        graph = parser.parse(file_paths, root)

    # Store in cache for next time
    if use_cache:
        key = cache_key(source_path, language, files, exclude_tests)
        put_cached_graph(source_path, key, graph)

    return graph
