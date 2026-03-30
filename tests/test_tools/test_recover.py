"""Tests for the recover tool."""

import pytest

from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.tools.recover import recover


def test_package_based_recovery(sample_graph):
    arch = recover(sample_graph, algorithm="pkg")

    assert len(arch.components) >= 2
    assert arch.algorithm == "pkg"

    # All entities should be assigned
    all_entities = set()
    for comp in arch.components:
        all_entities.update(comp.entities)
    assert all_entities == set(sample_graph.entities.keys())


def test_wca_recovery(sample_graph):
    arch = recover(sample_graph, algorithm="wca", num_clusters=2)

    assert len(arch.components) >= 1
    assert arch.algorithm == "wca"


def test_wca_recovery_uses_unique_component_names(sample_graph):
    arch = recover(sample_graph, algorithm="wca", num_clusters=3)

    names = [component.name for component in arch.components]
    assert len(names) == len(set(names))


def test_acdc_recovery(sample_graph):
    arch = recover(sample_graph, algorithm="acdc")

    assert len(arch.components) >= 1
    assert arch.algorithm == "acdc"


def test_package_based_recovery_reassigns_thin_facades():
    graph = DependencyGraph(
        entities={
            "com.example.api.facade": Entity(
                fqn="com.example.api.facade",
                name="facade",
                package="com.example.api",
                file_path="api.py",
                kind="function",
                language="python",
            ),
            "com.example.api.registry": Entity(
                fqn="com.example.api.registry",
                name="registry",
                package="com.example.api",
                file_path="api.py",
                kind="function",
                language="python",
            ),
            "com.example.api.tool": Entity(
                fqn="com.example.api.tool",
                name="tool",
                package="com.example.api",
                file_path="api.py",
                kind="function",
                language="python",
            ),
            "com.example.impl.worker": Entity(
                fqn="com.example.impl.worker",
                name="worker",
                package="com.example.impl",
                file_path="impl.py",
                kind="function",
                language="python",
            ),
        },
        edges=[
            Edge(
                source="com.example.api.facade",
                target="com.example.api.tool",
                relation="import",
            ),
            Edge(
                source="com.example.api.registry",
                target="com.example.api.tool",
                relation="import",
            ),
            Edge(
                source="com.example.api.facade",
                target="com.example.impl.worker",
                relation="import",
            )
        ],
        packages={
            "com.example.api": [
                "com.example.api.facade",
                "com.example.api.registry",
                "com.example.api.tool",
            ],
            "com.example.impl": ["com.example.impl.worker"],
        },
    )

    arch = recover(graph, algorithm="pkg")
    membership = {
        entity_fqn: component.name
        for component in arch.components
        for entity_fqn in component.entities
    }

    assert membership["com.example.api.facade"] == membership["com.example.impl.worker"]
    assert membership["com.example.api.registry"] != membership["com.example.impl.worker"]
    assert "facade refinement" in arch.rationale


def test_unknown_algorithm(sample_graph):
    with pytest.raises(ValueError, match="Unknown algorithm"):
        recover(sample_graph, algorithm="unknown")
