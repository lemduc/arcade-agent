"""TypeScript/JavaScript parser using tree-sitter (stub for Phase 5)."""

from pathlib import Path

from arcade_agent.parsers.base import LanguageParser
from arcade_agent.parsers.graph import DependencyGraph


class TypeScriptParser(LanguageParser):
    """TypeScript/JavaScript parser (not yet implemented)."""

    @property
    def language(self) -> str:
        return "typescript"

    @property
    def file_extensions(self) -> list[str]:
        return [".ts", ".tsx", ".js", ".jsx"]

    def parse(self, files: list[Path], root: Path) -> DependencyGraph:
        raise NotImplementedError(
            "TypeScript parser not yet implemented. "
            "Install tree-sitter-typescript and contribute!"
        )
