"""Language-agnostic source code parsers."""

from arcade_agent.parsers.base import LanguageParser, get_parser

# Import parsers to trigger registration via @register_parser
import arcade_agent.parsers.java  # noqa: F401
import arcade_agent.parsers.python  # noqa: F401
import arcade_agent.parsers.c  # noqa: F401

__all__ = ["LanguageParser", "get_parser"]
