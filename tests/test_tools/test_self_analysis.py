"""Tests for repository self-analysis filtering."""

import sys
from pathlib import Path

from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.run_self_analysis import _filter_non_architectural_entities


def test_self_analysis_filters_registration_import_edges_only():
    graph = DependencyGraph(
        entities={
            "arcade_agent.tools.compare.compare": Entity(
                fqn="arcade_agent.tools.compare.compare",
                name="compare",
                package="arcade_agent.tools",
                file_path="src/arcade_agent/tools/compare.py",
                kind="function",
                language="python",
            ),
            "arcade_agent.tools.registry.tool": Entity(
                fqn="arcade_agent.tools.registry.tool",
                name="tool",
                package="arcade_agent.tools",
                file_path="src/arcade_agent/tools/registry.py",
                kind="function",
                language="python",
            ),
            "arcade_agent.algorithms.matching.match_components": Entity(
                fqn="arcade_agent.algorithms.matching.match_components",
                name="match_components",
                package="arcade_agent.algorithms",
                file_path="src/arcade_agent/algorithms/matching.py",
                kind="function",
                language="python",
            ),
        },
        edges=[
            Edge(
                source="arcade_agent.tools.compare.compare",
                target="arcade_agent.tools.registry.tool",
                relation="import",
            ),
            Edge(
                source="arcade_agent.tools.compare.compare",
                target="arcade_agent.algorithms.matching.match_components",
                relation="import",
            ),
        ],
        packages={
            "arcade_agent.tools": [
                "arcade_agent.tools.compare.compare",
                "arcade_agent.tools.registry.tool",
            ],
            "arcade_agent.algorithms": [
                "arcade_agent.algorithms.matching.match_components",
            ],
        },
    )

    filtered = _filter_non_architectural_entities(graph)

    assert (
        "arcade_agent.tools.compare.compare",
        "arcade_agent.tools.registry.tool",
        "import",
    ) not in filtered.to_edge_tuples()
    assert (
        "arcade_agent.tools.compare.compare",
        "arcade_agent.algorithms.matching.match_components",
        "import",
    ) in filtered.to_edge_tuples()
