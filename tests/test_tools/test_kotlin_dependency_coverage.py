"""Characterize structural Kotlin coverage; keep the desired detector guard visible."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_kotlin")

from arcade_agent.algorithms.concern import detect_concern_overload  # noqa: E402
from arcade_agent.parsers.graph import Edge  # noqa: E402
from arcade_agent.tools.analyze import analyze  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[2] / "examples/kotlin_dependency_coverage/src"


@pytest.fixture(scope="module")
def analysis():
    result = asyncio.run(analyze(
        str(FIXTURE), language="kotlin", algorithm="pkg",
        exclude_tests=True, use_cache=False, use_llm=False,
    ))
    yield result
    result.repository.cleanup()


def test_file_import_attribution_is_not_method_usage(analysis):
    graph = analysis.graph
    edges = [edge for edge in graph.edges if edge.source.startswith("renderer.")]
    assert {(edge.source, edge.target, edge.relation) for edge in edges} == {
        (source, f"canvas.{target}", "import")
        for source in (
            "renderer.TimelineFrameRenderer",
            "renderer.TimelineFrameRenderer.render",
            "renderer.TimelineFrameRenderer.close",
        )
        for target in ("Bitmap", "Canvas", "Paint")
    }
    assert len(edges) == 9
    assert len({(graph.entities[e.source].file_path, e.target) for e in edges}) == 3
    # close() is empty; its three imports cannot be interpreted as actual usages.
    assert "fun close() {}" in (FIXTURE / "TimelineFrameRenderer.kt").read_text()


def test_missing_internal_calls_trigger_high_finding_despite_single_computation(analysis):
    graph = analysis.graph
    assert graph.num_entities == 51
    assert graph.num_edges == 12
    assert {edge.relation for edge in graph.edges} == {"import"}
    assert detect_concern_overload(analysis.architecture, graph) == [{
        "component": "Ui", "entity_count": 42, "severity": "high",
        "internal_edges": 0, "internal_edges_per_entity": 0.0,
    }]
    assert any(
        smell.smell_type == "Concern Overload" and smell.severity == "high"
        and smell.affected_components == ["Ui"]
        for smell in analysis.smells
    )

    # Controlled counterfactual: add exactly the calls explicitly present in source.
    # This is evidence for detector sensitivity, not a replacement Kotlin resolver.
    owner = "ui.MainActivity"
    calls = [Edge(f"{owner}.render", f"{owner}.step01", "calls")]
    calls.extend(
        Edge(f"{owner}.step{i:02d}", f"{owner}.step{i+1:02d}", "calls")
        for i in range(1, 40)
    )
    source = (FIXTURE / "MainActivity.kt").read_text()
    for edge in calls:
        caller = edge.source.rsplit(".", 1)[1]
        callee = edge.target.rsplit(".", 1)[1]
        assert f"fun {caller}(): Int = {callee}()" in source
        assert edge.source in graph.entities and edge.target in graph.entities
    assert detect_concern_overload(
        analysis.architecture, replace(graph, edges=[*graph.edges, *calls]),
    ) == []


def test_source_import_cycle_survives_independently(analysis):
    graph = analysis.graph
    assert {
        (edge.source, edge.target) for edge in graph.edges
        if graph.entities[edge.source].package in {"data", "export", "view"}
    } == {
        ("data.DataNode", "export.ExportNode"),
        ("export.ExportNode", "view.ViewNode"),
        ("view.ViewNode", "data.DataNode"),
    }
    cycles = [smell for smell in analysis.smells if smell.smell_type == "Dependency Cycle"]
    assert len(cycles) == 1
    assert set(cycles[0].affected_components) == {"Data", "Export", "View"}


def test_structural_only_graph_should_not_emit_unqualified_high_cohesion_finding(analysis):
    assert not any(
        smell.smell_type == "Concern Overload" and smell.severity == "high"
        and smell.affected_components == ["Ui"]
        for smell in analysis.smells
    )
