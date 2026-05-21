"""End-to-end tests for the MCP server adapter.

These tests exercise the actual FastMCP server by calling ``server.call_tool()``
so the full request/response pipeline (session store, budget, serialisation) is
covered — not just individual helper functions.

The ``mcp`` package must be installed (``pip install -e ".[mcp]"``).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Path to the arcade-agent source so we can point 'parse' at it
_REPO_ROOT = str(Path(__file__).parent.parent / "src")


def _call(server, tool: str, args: dict) -> dict:
    """Invoke a FastMCP tool (async) and return the parsed JSON response.

    FastMCP.call_tool() is a coroutine that returns ``(content_list, is_error)``
    where ``content_list`` is a sequence of ``TextContent`` objects.
    """
    async def _run():
        result = await server.call_tool(tool, args)
        # Unpack (content_list, is_error) tuple
        if isinstance(result, tuple):
            content_list, is_error = result
            text = content_list[0].text if content_list else ""
        elif isinstance(result, list):
            text = result[0].text
        elif isinstance(result, str):
            text = result
        else:
            raise TypeError(f"Unexpected call_tool result type: {type(result)}")
        return json.loads(text)

    return asyncio.run(_run())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def server():
    """Return the FastMCP server singleton (requires mcp extra)."""
    pytest.importorskip("mcp", reason="mcp extra not installed")
    from arcade_agent.tools.adapters.mcp import _session, get_server

    _session.clear()
    return get_server()


# ---------------------------------------------------------------------------
# E2E: parse → recover pipeline
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("CI") is None and not Path(_REPO_ROOT).is_dir(),
    reason="source directory not available",
)
class TestMcpE2E:
    """Invoke server.call_tool() end-to-end for the core analysis pipeline."""

    def test_parse_returns_session_id(self, server):
        result = _call(server, "parse", {"source_path": _REPO_ROOT, "language": "python"})
        assert "session_id" in result, result
        assert "num_entities" in result
        assert result["num_entities"] > 0
        assert result["type"] == "DependencyGraph"

    def test_recover_uses_parse_session_id(self, server):
        # parse first
        parse_result = _call(server, "parse", {"source_path": _REPO_ROOT, "language": "python"})
        graph_sid = parse_result["session_id"]

        # recover using the session id
        recover_result = _call(server, "recover", {"dep_graph": graph_sid, "algorithm": "pkg"})
        assert "session_id" in recover_result, recover_result
        assert "num_components" in recover_result
        assert recover_result["num_components"] > 0
        assert recover_result["type"] == "Architecture"

    def test_list_sessions_populated(self, server):
        result = _call(server, "list_sessions", {})
        assert "sessions" in result
        assert len(result["sessions"]) > 0

    def test_get_full_result(self, server):
        parse_result = _call(server, "parse", {"source_path": _REPO_ROOT, "language": "python"})
        sid = parse_result["session_id"]

        full = _call(server, "get_full_result", {"session_id": sid})
        assert full["session_id"] == sid
        assert "data" in full
        assert "entities" in full["data"]

    # ------------------------------------------------------------------
    # Budget enforcement
    # ------------------------------------------------------------------

    def test_max_tokens_enforced_on_summary(self, server):
        """max_tokens must actually reduce the parse summary output."""
        full_result = _call(server, "parse", {"source_path": _REPO_ROOT, "language": "python"})
        tiny_result = _call(server, "parse", {
            "source_path": _REPO_ROOT,
            "language": "python",
            "max_tokens": 5,
        })
        full_text = json.dumps(full_result)
        tiny_text = json.dumps(tiny_result)
        assert len(tiny_text) < len(full_text), (
            "Response with max_tokens=5 should be smaller than unconstrained response"
        )
        assert tiny_result.get("_budget_truncated") is True

    def test_max_tokens_none_passthrough(self, server):
        """No budget flag should appear when max_tokens is not set."""
        result = _call(server, "parse", {"source_path": _REPO_ROOT, "language": "python"})
        assert "_budget_truncated" not in result

