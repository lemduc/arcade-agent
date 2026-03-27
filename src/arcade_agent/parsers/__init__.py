"""Language-agnostic source code parsers."""

# Import parsers to trigger registration via @register_parser.
# Core parsers (Java, Python) are always available.
# Optional parsers (C, TypeScript) require extra dependencies.
import arcade_agent.parsers.java  # noqa: F401
import arcade_agent.parsers.python  # noqa: F401

try:
    import arcade_agent.parsers.c  # noqa: F401
except ImportError:
    pass

from arcade_agent.parsers.base import LanguageParser, get_parser

__all__ = ["LanguageParser", "get_parser"]
