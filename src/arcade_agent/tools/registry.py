"""Backward-compatible exports for the tool registry."""

from arcade_agent.tooling.registry import ToolDef, get_tool, list_tools, tool

__all__ = ["ToolDef", "get_tool", "list_tools", "tool"]
