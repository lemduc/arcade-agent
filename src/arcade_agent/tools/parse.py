"""Tool: Parse source code and extract dependency graph."""

import logging
from pathlib import Path

import arcade_agent.parsers  # noqa: F401 — register language parsers
from arcade_agent.cache import cache_key, get_cached_graph, put_cached_graph
from arcade_agent.parsers.base import detect_language, get_parser
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.parsers.multilang import merge_and_relink
from arcade_agent.tools.registry import tool

logger = logging.getLogger(__name__)


def _cache_language_key(
    language: str | None,
    languages: list[str] | None,
) -> str | None:
    if languages:
        return ",".join(sorted(languages))
    return language


def _resolve_languages(
    root: Path,
    language: str | None,
    languages: list[str] | None,
    file_paths: list[Path] | None,
) -> list[str]:
    if language is not None and languages is not None:
        raise ValueError("Pass only one of language and languages")
    if languages is not None:
        if not languages:
            raise ValueError("languages must be non-empty")
        # Sorted + de-duplicated so ["kotlin", "java"] and ["java", "kotlin"]
        # produce the same graph (merge order decides collision winners).
        return sorted(dict.fromkeys(languages))
    if language == "multi":
        discover = file_paths if file_paths is not None else [
            f for f in root.rglob("*") if f.is_file()
        ]
        detected_languages = detect_languages_from_files(discover)
        if not detected_languages:
            raise ValueError(f"Could not detect languages in {root}")
        return detected_languages
    if language:
        return [language]
    discover = file_paths if file_paths is not None else [
        f for f in root.rglob("*") if f.is_file()
    ]
    detected_language = detect_language(discover)
    if not detected_language:
        raise ValueError(f"Could not detect language in {root}")
    return [detected_language]


def detect_languages_from_files(files: list[Path]) -> list[str]:
    """Return sorted language names present among *files* (by suffix)."""
    found: set[str] = set()
    for path in files:
        ext = path.suffix.lower()
        if not ext:
            continue
        try:
            parser = get_parser(ext)
        except KeyError:
            continue
        found.add(parser.language)
    return sorted(found)


def _files_for_language(files: list[Path], language: str) -> list[Path]:
    parser = get_parser(language)
    exts = set(parser.file_extensions)
    return [f for f in files if f.suffix in exts]


def _parse_one(
    language: str,
    file_paths: list[Path],
    root: Path,
    use_cache: bool,
) -> DependencyGraph:
    parser = get_parser(language)
    if not file_paths:
        return DependencyGraph()
    if use_cache and hasattr(parser, "parse_incremental"):
        from arcade_agent.incremental import ExtractCache
        return parser.parse_incremental(file_paths, root, ExtractCache(root))
    return parser.parse(file_paths, root)


def _discover_files(root: Path, languages: list[str]) -> list[Path]:
    file_paths: list[Path] = []
    for language in languages:
        parser = get_parser(language)
        for ext in parser.file_extensions:
            file_paths.extend(sorted(root.rglob(f"*{ext}")))
    return list(dict.fromkeys(file_paths))


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
    languages: list[str] | None = None,
    files: list[str] | None = None,
    use_cache: bool = True,
) -> DependencyGraph:
    """Parse source code and extract a dependency graph.

    Polyglot support (MVP): every requested language is parsed, but
    cross-language edges are only linked *within a language family* — currently
    just the JVM family (``java`` + ``kotlin``), the one validated pair. Other
    languages each form their own family, so a Python and a Java graph are
    unioned without inventing edges between them (see
    ``arcade_agent.parsers.multilang``). Cross-family FQN collisions are kept
    (re-keyed as ``<fqn>#<language>``) and counted in ``graph.metadata``.

    Args:
        source_path: Root directory of the project.
        language: Language to parse (java, python, etc.), or "multi" to parse
            every detected language and merge+relink cross-language edges.
        languages: Explicit language list for polyglot parse
            (e.g. ["java", "kotlin"]). Sorted internally, so ordering does not
            change the result. Mutually exclusive with *language*.
        files: Specific files to parse. If None, discovers all files. Files not
            matching any resolved language are skipped (with a warning).
        use_cache: If True, return cached results when source files haven't changed.

    Returns:
        DependencyGraph with entities, edges, package info and, for polyglot
        parses, FQN-collision counts in ``metadata``.
    """
    root = Path(source_path)
    provided_files = [Path(f) for f in files] if files else None
    resolved = _resolve_languages(root, language, languages, provided_files)
    cache_lang = _cache_language_key(
        language if language != "multi" else "multi",
        resolved if len(resolved) > 1 else None,
    )

    if use_cache:
        key = cache_key(source_path, cache_lang, files)
        cached = get_cached_graph(source_path, key)
        if cached is not None:
            return cached

    if provided_files is not None:
        file_paths = provided_files
    else:
        file_paths = _discover_files(root, resolved)

    per_language = {lang: _files_for_language(file_paths, lang) for lang in resolved}
    selected = {f for files_ in per_language.values() for f in files_}
    dropped = [f for f in file_paths if f not in selected]
    if dropped:
        # Same filtering rule for one or many languages: a file whose extension
        # no resolved parser claims is not parseable and is reported, not
        # silently handed to an arbitrary parser.
        logger.warning(
            "Skipping %d file(s) not matching languages %s (e.g. %s)",
            len(dropped),
            ",".join(resolved),
            dropped[0],
        )

    if len(resolved) == 1:
        graph = _parse_one(resolved[0], per_language[resolved[0]], root, use_cache)
    else:
        graphs = [
            _parse_one(lang, per_language[lang], root, use_cache) for lang in resolved
        ]
        graphs = [g for g in graphs if g.num_entities or g.num_edges]
        graph = merge_and_relink(*graphs) if graphs else DependencyGraph()

    if use_cache:
        key = cache_key(source_path, cache_lang, files)
        put_cached_graph(source_path, key, graph)

    return graph
