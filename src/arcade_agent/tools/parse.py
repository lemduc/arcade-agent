"""Tool: Parse source code and extract dependency graph."""

from pathlib import Path

from arcade_agent.parsers.base import detect_language, get_parser
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.registry import tool


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
) -> DependencyGraph:
    """Parse source code and extract a dependency graph.

    Args:
        source_path: Root directory of the project.
        language: Language to parse (java, python, etc.). Auto-detected if None.
        files: Specific files to parse. If None, discovers all files.

    Returns:
        DependencyGraph with entities, edges, and package info.
    """
    root = Path(source_path)

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
    return parser.parse(file_paths, root)
