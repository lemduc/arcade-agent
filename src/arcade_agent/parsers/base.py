"""Abstract parser interface for language-agnostic source code parsing."""

from abc import ABC, abstractmethod
from pathlib import Path

from arcade_agent.parsers.graph import DependencyGraph


class LanguageParser(ABC):
    """Abstract base class for language-specific parsers."""

    @property
    @abstractmethod
    def language(self) -> str:
        """Return the language name (e.g., 'java', 'python')."""
        ...

    @property
    @abstractmethod
    def file_extensions(self) -> list[str]:
        """Return supported file extensions (e.g., ['.java'])."""
        ...

    @abstractmethod
    def parse(self, files: list[Path], root: Path) -> DependencyGraph:
        """Parse source files and extract a dependency graph.

        Args:
            files: List of source file paths.
            root: Root directory of the project (for relative paths).

        Returns:
            DependencyGraph with entities, edges, and package info.
        """
        ...


# Parser registry
_PARSERS: dict[str, type[LanguageParser]] = {}


def register_parser(parser_cls: type[LanguageParser]) -> type[LanguageParser]:
    """Register a parser class."""
    instance = parser_cls()
    _PARSERS[instance.language] = parser_cls
    for ext in instance.file_extensions:
        _PARSERS[ext] = parser_cls
    return parser_cls


def get_parser(language_or_ext: str) -> LanguageParser:
    """Get a parser instance by language name or file extension.

    Args:
        language_or_ext: Language name (e.g., 'java') or extension (e.g., '.java').

    Returns:
        An instance of the appropriate parser.

    Raises:
        KeyError: If no parser is registered for the given language/extension.
    """
    if language_or_ext not in _PARSERS:
        available = [k for k in _PARSERS if not k.startswith(".")]
        raise KeyError(
            f"No parser for '{language_or_ext}'. Available: {available}"
        )
    return _PARSERS[language_or_ext]()


def detect_language(files: list[Path]) -> str | None:
    """Auto-detect the primary language from file extensions."""
    ext_counts: dict[str, int] = {}
    for f in files:
        ext = f.suffix.lower()
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    for ext, _ in sorted(ext_counts.items(), key=lambda x: -x[1]):
        if ext in _PARSERS:
            instance = _PARSERS[ext]()
            return instance.language
    return None
