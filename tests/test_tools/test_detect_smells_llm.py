"""Tests for LLM-based smell detection."""

from unittest.mock import patch

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.concern import (
    _build_component_summary,
    detect_concerns_llm,
)
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.tools.detect_smells import detect_smells


def _make_large_arch():
    """Build an architecture with a clearly overloaded component."""
    entities = {}
    big_list = []
    for i in range(30):
        fqn = f"com.big.Class{i}"
        entities[fqn] = Entity(
            fqn=fqn, name=f"Class{i}", package="com.big",
            file_path=f"Class{i}.java", kind="class", language="java",
        )
        big_list.append(fqn)

    small_fqn = "com.small.Helper"
    entities[small_fqn] = Entity(
        fqn=small_fqn, name="Helper", package="com.small",
        file_path="Helper.java", kind="class", language="java",
    )

    graph = DependencyGraph(
        entities=entities,
        edges=[Edge(source=big_list[0], target=small_fqn, relation="import")],
        packages={"com.big": big_list, "com.small": [small_fqn]},
    )
    arch = Architecture(
        components=[
            Component(name="BigModule", responsibility="Everything", entities=big_list),
            Component(name="SmallModule", responsibility="Helpers", entities=[small_fqn]),
        ],
        algorithm="test",
    )
    return arch, graph


def test_build_component_summary():
    """Verify the LLM prompt builder produces expected structure."""
    arch, graph = _make_large_arch()
    summary = _build_component_summary(arch, graph)
    assert len(summary) == 2
    big = summary[0]
    assert big["name"] == "BigModule"
    assert big["num_entities"] == 30
    assert len(big["entities"]) == 30
    assert big["depends_on"] == ["SmallModule"]


def test_detect_concerns_llm_mock_mode():
    """In mock mode, LLM detection returns empty list."""
    arch, graph = _make_large_arch()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        result = detect_concerns_llm(arch, graph)
    assert result == []


def test_detect_concerns_llm_returns_smells():
    """Verify LLM response is correctly parsed into smell dicts."""
    arch, graph = _make_large_arch()

    llm_response = {
        "smells": [
            {
                "smell_type": "Concern Overload",
                "severity": "high",
                "affected_components": ["BigModule"],
                "description": "BigModule mixes UI, persistence, and business logic.",
                "explanation": "Multiple unrelated concerns in one component.",
                "suggestion": "Split into UI, Persistence, and Domain components.",
            },
            {
                "smell_type": "Scattered Parasitic Functionality",
                "severity": "medium",
                "affected_components": ["BigModule", "SmallModule"],
                "description": "Logging is scattered across both modules.",
                "explanation": "Changes to logging require touching multiple modules.",
                "suggestion": "Centralize logging into a dedicated component.",
            },
        ]
    }

    with patch("arcade_agent.algorithms.llm.ask_claude_json", return_value=llm_response), \
         patch("arcade_agent.algorithms.llm.MOCK_MODE", False):
        result = detect_concerns_llm(arch, graph)

    assert len(result) == 2
    assert result[0]["smell_type"] == "Concern Overload"
    assert result[0]["severity"] == "high"
    assert result[0]["affected_components"] == ["BigModule"]
    assert result[1]["smell_type"] == "Scattered Parasitic Functionality"
    assert result[1]["affected_components"] == ["BigModule", "SmallModule"]


def test_detect_concerns_llm_filters_invalid_components():
    """LLM may hallucinate component names — verify they are filtered."""
    arch, graph = _make_large_arch()

    llm_response = {
        "smells": [
            {
                "smell_type": "Concern Overload",
                "severity": "medium",
                "affected_components": ["NonExistent"],
                "description": "Fake smell.",
                "explanation": "N/A",
                "suggestion": "N/A",
            },
            {
                "smell_type": "Concern Overload",
                "severity": "medium",
                "affected_components": ["BigModule", "NonExistent"],
                "description": "Partially valid.",
                "explanation": "N/A",
                "suggestion": "N/A",
            },
        ]
    }

    with patch("arcade_agent.algorithms.llm.ask_claude_json", return_value=llm_response), \
         patch("arcade_agent.algorithms.llm.MOCK_MODE", False):
        result = detect_concerns_llm(arch, graph)

    # First smell fully invalid — dropped. Second partially valid — kept.
    assert len(result) == 1
    assert result[0]["affected_components"] == ["BigModule"]


def test_detect_smells_use_llm_flag():
    """Verify detect_smells(use_llm=True) routes to LLM detection."""
    arch, graph = _make_large_arch()

    llm_response = {
        "smells": [
            {
                "smell_type": "Concern Overload",
                "severity": "high",
                "affected_components": ["BigModule"],
                "description": "Overloaded module.",
                "explanation": "Too many concerns.",
                "suggestion": "Split it.",
            },
        ]
    }

    with patch("arcade_agent.algorithms.llm.ask_claude_json", return_value=llm_response), \
         patch("arcade_agent.algorithms.llm.MOCK_MODE", False):
        smells = detect_smells(arch, graph, use_llm=True)

    concern_smells = [s for s in smells if s.smell_type == "Concern Overload"]
    assert len(concern_smells) == 1
    assert concern_smells[0].description == "Overloaded module."


def test_detect_smells_default_uses_heuristics():
    """Verify detect_smells() without use_llm uses heuristic detection."""
    arch, graph = _make_large_arch()

    # Should not call LLM at all
    with patch("arcade_agent.algorithms.llm.ask_claude_json") as mock_llm:
        smells = detect_smells(arch, graph, use_llm=False)
        mock_llm.assert_not_called()

    # Heuristic should find concern overload (30 entities > 20 threshold)
    concern_smells = [s for s in smells if s.smell_type == "Concern Overload"]
    assert len(concern_smells) >= 1
