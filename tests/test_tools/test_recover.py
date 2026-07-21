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
            ),
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


def test_package_recovery_reassigns_called_facade_from_oversized_bucket():
    api_entities = {
        f"com.example.api.peer{i}": Entity(
            fqn=f"com.example.api.peer{i}",
            name=f"peer{i}",
            package="com.example.api",
            file_path=f"peer{i}.py",
            kind="function",
            language="python",
        )
        for i in range(20)
    }
    facade = Entity(
        fqn="com.example.api.facade",
        name="facade",
        package="com.example.api",
        file_path="facade.py",
        kind="function",
        language="python",
    )
    worker = Entity(
        fqn="com.example.impl.worker",
        name="worker",
        package="com.example.impl",
        file_path="worker.py",
        kind="function",
        language="python",
    )
    caller = Entity(
        fqn="com.example.cli.command",
        name="command",
        package="com.example.cli",
        file_path="command.py",
        kind="function",
        language="python",
    )
    graph = DependencyGraph(
        entities={
            **api_entities,
            facade.fqn: facade,
            worker.fqn: worker,
            caller.fqn: caller,
        },
        edges=[
            Edge(source=facade.fqn, target=worker.fqn, relation="import"),
            Edge(source=caller.fqn, target=facade.fqn, relation="import"),
        ],
        packages={
            "com.example.api": [*api_entities, facade.fqn],
            "com.example.impl": [worker.fqn],
            "com.example.cli": [caller.fqn],
        },
    )

    arch = recover(graph, algorithm="pkg")
    membership = {
        entity_fqn: component.name
        for component in arch.components
        for entity_fqn in component.entities
    }

    assert membership[facade.fqn] == membership[worker.fqn]
    assert membership[caller.fqn] != membership[worker.fqn]
    assert {membership[fqn] for fqn in api_entities} == {"Api"}


def test_package_recovery_keeps_called_facade_in_compact_boundary():
    entities = {
        fqn: Entity(
            fqn=fqn,
            name=fqn.rsplit(".", 1)[-1],
            package=package,
            file_path=f"{fqn.rsplit('.', 1)[-1]}.py",
            kind="function",
            language="python",
        )
        for fqn, package in {
            "com.example.api.facade": "com.example.api",
            "com.example.api.peer": "com.example.api",
            "com.example.impl.worker": "com.example.impl",
            "com.example.cli.command": "com.example.cli",
        }.items()
    }
    graph = DependencyGraph(
        entities=entities,
        edges=[
            Edge(
                source="com.example.api.facade",
                target="com.example.impl.worker",
                relation="import",
            ),
            Edge(
                source="com.example.cli.command",
                target="com.example.api.facade",
                relation="import",
            ),
        ],
        packages={
            "com.example.api": ["com.example.api.facade", "com.example.api.peer"],
            "com.example.impl": ["com.example.impl.worker"],
            "com.example.cli": ["com.example.cli.command"],
        },
    )

    arch = recover(graph, algorithm="pkg")
    membership = {
        entity_fqn: component.name
        for component in arch.components
        for entity_fqn in component.entities
    }

    assert membership["com.example.api.facade"] == "Api"
    assert membership["com.example.api.facade"] != membership["com.example.impl.worker"]


def test_unknown_algorithm(sample_graph):
    with pytest.raises(ValueError, match="Unknown algorithm"):
        recover(sample_graph, algorithm="unknown")
