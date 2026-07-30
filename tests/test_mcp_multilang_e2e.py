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

    def test_ingest_session_chains_languages_and_files_into_parse(self, server):
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
                "source_path": ingest_result["session_id"],
                "use_cache": False,
            },
        )
        assert parse_result["num_entities"] >= 2
        full = _call(server, "get_full_result", {"session_id": parse_result["session_id"]})
        entity_fqns = set(full["data"]["entities"])
        assert "com.example.JavaGreeter" in entity_fqns
        assert "com.example.KotlinGreeter" in entity_fqns

    def test_direct_parse_excludes_jvm_tests_by_default(
        self,
        server,
        jvm_project_with_tests: Path,
    ):
        parse_result = _call(
            server,
            "parse",
            {
                "source_path": str(jvm_project_with_tests),
                "languages": ["java", "kotlin"],
                "use_cache": False,
            },
        )

        full = _call(
            server,
            "get_full_result",
            {"session_id": parse_result["session_id"]},
        )
        entity_fqns = set(full["data"]["entities"])
        assert entity_fqns == {
            "com.example.LatestJava",
            "com.example.MainJava",
            "com.example.MainKotlin",
        }

    def test_ingest_parse_chain_preserves_include_tests_override(
        self,
        server,
        jvm_project_with_tests: Path,
    ):
        ingest_result = _call(
            server,
            "ingest",
            {
                "source": str(jvm_project_with_tests),
                "languages": ["java", "kotlin"],
                "exclude_tests": False,
            },
        )
        parse_result = _call(
            server,
            "parse",
            {
                "source_path": ingest_result["session_id"],
                "use_cache": False,
            },
        )
        full = _call(
            server,
            "get_full_result",
            {"session_id": parse_result["session_id"]},
        )
        entity_fqns = set(full["data"]["entities"])
        assert "com.example.UnitJavaTest" in entity_fqns
        assert "com.example.UnitKotlinTest" in entity_fqns
        assert "com.example.IntegrationJavaTest" in entity_fqns
        assert "com.example.FixtureKotlin" in entity_fqns

    def test_direct_parse_honors_exact_custom_exclusions(
        self,
        server,
        jvm_project_with_custom_layout: Path,
    ):
        parse_result = _call(
            server,
            "parse",
            {
                "source_path": str(jvm_project_with_custom_layout),
                "languages": ["java", "kotlin"],
                "exclude_dirs": [
                    "integrationTest",
                    "src/e2e",
                    "modules/api/spec",
                ],
                "use_cache": False,
            },
        )
        full = _call(
            server,
            "get_full_result",
            {"session_id": parse_result["session_id"]},
        )

        assert set(full["data"]["entities"]) == {
            "com.example.Main",
            "com.example.ProductionSupport",
        }

    def test_parse_exclusions_do_not_refilter_ingest_session(
        self,
        server,
        jvm_project_with_custom_layout: Path,
    ):
        ingest_result = _call(
            server,
            "ingest",
            {
                "source": str(jvm_project_with_custom_layout),
                "languages": ["java", "kotlin"],
            },
        )
        assert ingest_result["exclude_tests"] is True
        assert ingest_result["exclude_dirs"] == []

        parse_result = _call(
            server,
            "parse",
            {
                "source_path": ingest_result["session_id"],
                "exclude_dirs": ["integrationTest", "src/e2e"],
                "use_cache": False,
            },
        )
        full = _call(
            server,
            "get_full_result",
            {"session_id": parse_result["session_id"]},
        )

        # The ingest session supplies an authoritative explicit file list.
        assert "com.example.CustomIntegration" in full["data"]["entities"]
        assert "com.example.E2eScenario" in full["data"]["entities"]

    def test_parse_rejects_non_ingest_source_session(self, server):
        from mcp.server.fastmcp.exceptions import ToolError

        parsed = _call(
            server,
            "parse",
            {"source_path": _MIXED, "language": "multi", "use_cache": False},
        )

        async def _run():
            return await server.call_tool(
                "parse",
                {"source_path": parsed["session_id"], "use_cache": False},
            )

        with pytest.raises(ToolError, match="not IngestedRepo"):
            asyncio.run(_run())
