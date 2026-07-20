"""MCP end-to-end tests for polyglot Java+Kotlin ingest/parse/recover."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_kotlin")
pytest.importorskip("tree_sitter_java")

_FIXTURES = Path(__file__).parent / "fixtures"
_MIXED = str(_FIXTURES / "java_kotlin_mixed")
_MAVEN = str(_FIXTURES / "maven_java_kotlin")


def _call(server, tool: str, args: dict) -> dict:
    """Invoke a FastMCP tool (async) and return the parsed JSON response."""

    async def _run():
        result = await server.call_tool(tool, args)
        if isinstance(result, tuple):
            content_list, _is_error = result
            text = content_list[0].text if content_list else ""
        elif isinstance(result, list):
            text = result[0].text
        elif isinstance(result, str):
            text = result
        else:
            raise TypeError(f"Unexpected call_tool result type: {type(result)}")
        return json.loads(text)

    return asyncio.run(_run())


@pytest.fixture(scope="module")
def server():
    """Return the FastMCP server singleton (requires mcp extra)."""
    pytest.importorskip("mcp", reason="mcp extra not installed")
    from arcade_agent.tools.adapters.mcp import _session, get_server

    _session.clear()
    return get_server()


class TestMcpMultilangE2E:
    """MCP ingest/parse/recover against Java+Kotlin fixtures."""

    def test_parse_languages_java_kotlin_then_recover(self, server):
        parse_result = _call(
            server,
            "parse",
            {
                "source_path": _MIXED,
                "languages": ["java", "kotlin"],
                "use_cache": False,
            },
        )
        assert parse_result.get("type") == "DependencyGraph"
        assert parse_result["num_entities"] >= 2
        assert "session_id" in parse_result

        full = _call(server, "get_full_result", {"session_id": parse_result["session_id"]})
        entities = full["data"]["entities"]
        languages = {e["language"] for e in entities.values()}
        assert "java" in languages
        assert "kotlin" in languages

        edges = full["data"]["edges"]
        assert any(
            edge["relation"] in {"extends", "implements", "import"}
            and entities[edge["source"]]["language"] != entities[edge["target"]]["language"]
            for edge in edges
            if edge["source"] in entities and edge["target"] in entities
        )

        recover_result = _call(
            server,
            "recover",
            {"dep_graph": parse_result["session_id"], "algorithm": "pkg"},
        )
        assert recover_result.get("type") == "Architecture"
        assert recover_result["num_components"] > 0

    def test_parse_language_multi_on_mixed_fixture(self, server):
        result = _call(
            server,
            "parse",
            {"source_path": _MIXED, "language": "multi", "use_cache": False},
        )
        assert result["num_entities"] >= 2
        full = _call(server, "get_full_result", {"session_id": result["session_id"]})
        languages = {e["language"] for e in full["data"]["entities"].values()}
        assert languages == {"java", "kotlin"}

    def test_ingest_languages_then_parse_maven_fixture(self, server):
        ingest_result = _call(
            server,
            "ingest",
            {"source": _MAVEN, "languages": ["java", "kotlin"]},
        )
        assert ingest_result.get("type") == "IngestedRepo"
        assert sorted(ingest_result.get("languages", [])) == ["java", "kotlin"]
        assert ingest_result["num_files"] >= 2

        parse_result = _call(
            server,
            "parse",
            {
                "source_path": _MAVEN,
                "languages": ["java", "kotlin"],
                "use_cache": False,
            },
        )
        assert parse_result["num_entities"] >= 2
        full = _call(server, "get_full_result", {"session_id": parse_result["session_id"]})
        entity_fqns = set(full["data"]["entities"])
        assert "com.example.JavaGreeter" in entity_fqns
        assert "com.example.KotlinGreeter" in entity_fqns
