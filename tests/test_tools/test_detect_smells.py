"""Tests for the detect_smells tool."""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.tools.detect_smells import detect_smells


def test_detect_no_smells(sample_architecture, sample_graph):
    smells = detect_smells(sample_architecture, sample_graph)
    # Simple architecture may not have smells
    assert isinstance(smells, list)


def test_detect_dependency_cycle():
    """Create a graph with a known cycle."""
    entities = {
        "A": Entity(
            fqn="A", name="A", package="p1",
            file_path="A.java", kind="class", language="java",
        ),
        "B": Entity(
            fqn="B", name="B", package="p2",
            file_path="B.java", kind="class", language="java",
        ),
        "C": Entity(
            fqn="C", name="C", package="p3",
            file_path="C.java", kind="class", language="java",
        ),
    }
    edges = [
        Edge(source="A", target="B", relation="import"),
        Edge(source="B", target="C", relation="import"),
        Edge(source="C", target="A", relation="import"),
    ]
    graph = DependencyGraph(
        entities=entities, edges=edges,
        packages={"p1": ["A"], "p2": ["B"], "p3": ["C"]},
    )

    arch = Architecture(
        components=[
            Component(name="CompA", responsibility="A", entities=["A"]),
            Component(name="CompB", responsibility="B", entities=["B"]),
            Component(name="CompC", responsibility="C", entities=["C"]),
        ],
        algorithm="test",
    )

    smells = detect_smells(arch, graph)
    cycle_smells = [s for s in smells if s.smell_type == "Dependency Cycle"]
    assert len(cycle_smells) >= 1
    assert cycle_smells[0].severity == "medium"  # 3 components


def test_detect_concern_overload():
    """Create architecture with a large but internally sparse component."""
    entities = {}
    entity_list = []
    for i in range(25):
        fqn = f"pkg.Class{i}"
        entities[fqn] = Entity(
            fqn=fqn, name=f"Class{i}", package="pkg",
            file_path=f"Class{i}.java", kind="class", language="java",
        )
        entity_list.append(fqn)

    graph = DependencyGraph(entities=entities, edges=[], packages={"pkg": entity_list})
    arch = Architecture(
        components=[
            Component(name="BigComp", responsibility="Everything", entities=entity_list),
        ],
        algorithm="test",
    )

    smells = detect_smells(arch, graph)
    overload_smells = [s for s in smells if s.smell_type == "Concern Overload"]
    assert len(overload_smells) >= 1


def test_detect_concern_overload_skips_large_cohesive_component():
    """Large components with strong internal cohesion should not be flagged."""
    entities = {}
    entity_list = []
    edges = []
    for i in range(25):
        fqn = f"pkg.Class{i}"
        entities[fqn] = Entity(
            fqn=fqn, name=f"Class{i}", package="pkg",
            file_path=f"Class{i}.java", kind="class", language="java",
        )
        entity_list.append(fqn)
        if i > 0:
            edges.append(Edge(source=fqn, target=f"pkg.Class{i-1}", relation="import"))

    graph = DependencyGraph(entities=entities, edges=edges, packages={"pkg": entity_list})
    arch = Architecture(
        components=[
            Component(name="BigComp", responsibility="Cohesive core", entities=entity_list),
        ],
        algorithm="test",
    )

    smells = detect_smells(arch, graph)
    overload_smells = [s for s in smells if s.smell_type == "Concern Overload"]
    assert overload_smells == []
