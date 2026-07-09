"""Tests for the context_for_task tool."""

from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.tools.context_for_task import (
    ROLE_DEPENDENCY,
    ROLE_DEPENDENT,
    ROLE_DIRECT,
    ROLE_SIBLING,
    context_for_task,
)


def _roles(result: dict) -> dict[str, str]:
    """Flatten a result into an fqn -> role map across all files."""
    roles: dict[str, str] = {}
    for f in result["files"]:
        for e in f["entities"]:
            roles[e["fqn"]] = e["role"]
    return roles


def test_direct_match_included(sample_graph):
    result = context_for_task(sample_graph, "Calculator")
    files = [f["file_path"] for f in result["files"]]
    assert "Calculator.java" in files
    roles = _roles(result)
    assert roles["com.example.calc.Calculator"] == ROLE_DIRECT


def test_keywords_extracted(sample_graph):
    result = context_for_task(sample_graph, "math helper")
    assert "math" in result["keywords"]
    assert "helper" in result["keywords"]


def test_dependency_expansion(sample_graph):
    # Calculator imports MathHelper -> MathHelper is a dependency of the match.
    result = context_for_task(sample_graph, "Calculator")
    roles = _roles(result)
    assert "com.example.util.MathHelper" in roles
    assert roles["com.example.util.MathHelper"] == ROLE_DEPENDENCY


def test_dependent_expansion(sample_graph):
    # AdvancedCalculator and Calculator both point at MathHelper, so matching
    # MathHelper should surface them as dependents.
    result = context_for_task(sample_graph, "MathHelper")
    roles = _roles(result)
    assert roles["com.example.util.MathHelper"] == ROLE_DIRECT
    assert roles["com.example.calc.Calculator"] == ROLE_DEPENDENT
    assert roles["com.example.calc.AdvancedCalculator"] == ROLE_DEPENDENT


def test_direct_match_ranks_above_neighbour(sample_graph):
    result = context_for_task(sample_graph, "Calculator")
    # The directly matched file should score at least as high as its neighbours.
    assert result["files"][0]["file_path"] == "Calculator.java"


def test_reason_mentions_keyword_and_relationship(sample_graph):
    result = context_for_task(sample_graph, "MathHelper")
    helper = next(
        f for f in result["files"] if f["file_path"] == "MathHelper.java"
    )
    assert "math" in helper["reason"].lower()
    assert "depended on by" in helper["reason"].lower()


def test_component_sibling(sample_graph, sample_architecture):
    # "utility helpers" matches the Util component's responsibility only; its
    # single entity is also a direct name match, so exercise sibling tagging
    # with a query that hits the component but not every member by name.
    graph = DependencyGraph(
        entities={
            "com.example.util.MathHelper": Entity(
                fqn="com.example.util.MathHelper",
                name="MathHelper",
                package="com.example.util",
                file_path="MathHelper.java",
                kind="class",
                language="java",
            ),
            "com.example.util.StringUtil": Entity(
                fqn="com.example.util.StringUtil",
                name="StringUtil",
                package="com.example.util",
                file_path="StringUtil.java",
                kind="class",
                language="java",
            ),
        },
        edges=[],
        packages={
            "com.example.util": [
                "com.example.util.MathHelper",
                "com.example.util.StringUtil",
            ]
        },
    )
    from arcade_agent.algorithms.architecture import Architecture, Component

    arch = Architecture(
        components=[
            Component(
                name="Util",
                responsibility="Utility helpers",
                entities=[
                    "com.example.util.MathHelper",
                    "com.example.util.StringUtil",
                ],
            )
        ],
        rationale="",
        algorithm="pkg",
    )
    # "utility" matches responsibility; "MathHelper" matches one entity by name.
    result = context_for_task(graph, "MathHelper utility", architecture=arch)
    roles = _roles(result)
    assert roles["com.example.util.MathHelper"] == ROLE_DIRECT
    # StringUtil is not a name match but is pulled in as a component sibling.
    assert roles["com.example.util.StringUtil"] == ROLE_SIBLING


def test_no_keywords(sample_graph):
    result = context_for_task(sample_graph, "")
    assert result["num_files"] == 0
    assert result["files"] == []
    assert "error" in result


def test_no_match(sample_graph):
    result = context_for_task(sample_graph, "zzzznotfound")
    assert result["num_files"] == 0
    assert result["files"] == []
    assert "error" not in result


def test_max_files_cap(sample_graph):
    result = context_for_task(sample_graph, "example", max_files=1)
    assert result["num_files"] <= 1


def test_cycle_does_not_hang():
    # Alpha <-> Beta mutual dependency must not infinite-loop during expansion.
    entities = {
        "pkg.Alpha": Entity(
            fqn="pkg.Alpha", name="Alpha", package="pkg", file_path="Alpha.py",
            kind="class", language="python",
        ),
        "pkg.Beta": Entity(
            fqn="pkg.Beta", name="Beta", package="pkg", file_path="Beta.py",
            kind="class", language="python",
        ),
    }
    edges = [
        Edge(source="pkg.Alpha", target="pkg.Beta", relation="uses"),
        Edge(source="pkg.Beta", target="pkg.Alpha", relation="uses"),
    ]
    graph = DependencyGraph(
        entities=entities, edges=edges, packages={"pkg": ["pkg.Alpha", "pkg.Beta"]}
    )
    result = context_for_task(graph, "Alpha Beta")
    roles = _roles(result)
    assert "pkg.Alpha" in roles
    assert "pkg.Beta" in roles
