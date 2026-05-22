"""Tests for MCP server adapter."""

import pytest

from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.serialization import (
    architecture_to_dict,
    dict_to_architecture,
    dict_to_graph,
    graph_to_dict,
    serialize_result,
)

# ---------------------------------------------------------------------------
# Serialization roundtrip tests
# ---------------------------------------------------------------------------


def test_graph_roundtrip(sample_graph):
    d = graph_to_dict(sample_graph)
    restored = dict_to_graph(d)
    assert restored.num_entities == sample_graph.num_entities
    assert restored.num_edges == sample_graph.num_edges
    assert set(restored.entities.keys()) == set(sample_graph.entities.keys())
    for fqn in sample_graph.entities:
        assert restored.entities[fqn].name == sample_graph.entities[fqn].name
        assert restored.entities[fqn].kind == sample_graph.entities[fqn].kind
        assert restored.entities[fqn].package == sample_graph.entities[fqn].package


def test_architecture_roundtrip(sample_architecture):
    d = architecture_to_dict(sample_architecture)
    restored = dict_to_architecture(d)
    assert len(restored.components) == len(sample_architecture.components)
    assert restored.algorithm == sample_architecture.algorithm
    assert restored.rationale == sample_architecture.rationale
    for orig, rest in zip(sample_architecture.components, restored.components):
        assert rest.name == orig.name
        assert rest.entities == orig.entities


def test_serialize_result_graph(sample_graph):
    result = serialize_result(sample_graph)
    assert isinstance(result, dict)
    assert "entities" in result
    assert "edges" in result


def test_serialize_result_primitives():
    assert serialize_result(42) == 42
    assert serialize_result("hello") == "hello"
    assert serialize_result(None) is None
    assert serialize_result(True) is True


def test_serialize_result_list(sample_graph):
    result = serialize_result([sample_graph])
    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], dict)


def test_serialize_result_path():
    from pathlib import Path
    result = serialize_result(Path("/tmp/test"))
    assert result == "/tmp/test"


# ---------------------------------------------------------------------------
# Session store tests
# ---------------------------------------------------------------------------


def test_session_store_and_resolve(sample_graph):
    from arcade_agent.tools.adapters.mcp import _resolve, _session, _store

    # Clear session
    _session.clear()

    sid = _store(sample_graph, "DependencyGraph")
    assert isinstance(sid, str)
    assert len(sid) == 12

    resolved = _resolve(sid, "DependencyGraph")
    assert resolved is sample_graph


def test_resolve_inline_dict():
    from arcade_agent.tools.adapters.mcp import _resolve

    graph_dict = {
        "entities": {
            "Main": {
                "fqn": "Main", "name": "Main", "package": "",
                "file_path": "Main.java", "kind": "class", "language": "java",
            }
        },
        "edges": [],
        "packages": {},
    }
    resolved = _resolve(graph_dict, "DependencyGraph")
    assert isinstance(resolved, DependencyGraph)
    assert resolved.num_entities == 1


def test_resolve_invalid_ref():
    from arcade_agent.tools.adapters.mcp import _resolve

    with pytest.raises(ValueError, match="Invalid reference"):
        _resolve("nonexistent_id_123")


def test_list_sessions(sample_graph, sample_architecture):
    from arcade_agent.tools.adapters.mcp import _session, _store

    _session.clear()
    sid1 = _store(sample_graph, "DependencyGraph")
    sid2 = _store(sample_architecture, "Architecture")

    assert sid1 in _session
    assert sid2 in _session
    assert _session[sid1]["label"] == "DependencyGraph"
    assert _session[sid2]["label"] == "Architecture"


# ---------------------------------------------------------------------------
# Summary generation tests
# ---------------------------------------------------------------------------


def test_make_summary_graph(sample_graph):
    from arcade_agent.tools.adapters.mcp import _make_summary, _session

    _session.clear()
    summary = _make_summary(sample_graph, "DependencyGraph")
    assert "session_id" in summary
    assert summary["type"] == "DependencyGraph"
    assert summary["num_entities"] == 3
    assert summary["num_edges"] == 3
    assert summary["num_packages"] == 2


def test_make_summary_architecture(sample_architecture):
    from arcade_agent.tools.adapters.mcp import _make_summary, _session

    _session.clear()
    summary = _make_summary(sample_architecture, "Architecture")
    assert summary["num_components"] == 2
    assert summary["algorithm"] == "pkg"
    assert len(summary["components"]) == 2
    assert summary["components"][0]["name"] == "Calc"
    assert summary["components"][0]["num_entities"] == 2


# ---------------------------------------------------------------------------
# Budget integration test
# ---------------------------------------------------------------------------


def test_apply_budget_passthrough():
    from arcade_agent.tools.adapters.mcp import _apply_budget

    data = {"key": "value"}
    assert _apply_budget(data, None) == data


def test_apply_budget_truncates():
    from arcade_agent.tools.adapters.mcp import _apply_budget

    data = {"graph": {"entities": {f"e{i}": {"kind": "class"} for i in range(100)}}}
    result = _apply_budget(data, max_tokens=50)
    assert isinstance(result, dict)
