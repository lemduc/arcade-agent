"""Tests for architecture and graph serialization."""

import pytest

from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.serialization import (
    load_architecture,
    load_graph,
    save_architecture,
    save_graph,
)


@pytest.fixture
def arch():
    return Architecture(
        components=[
            Component(
                name="Core",
                responsibility="Core logic",
                entities=["com.example.Core", "com.example.Engine"],
            ),
            Component(
                name="Util",
                responsibility="Utilities",
                entities=["com.example.Helper"],
            ),
        ],
        rationale="Package-based grouping",
        algorithm="pkg",
        metadata={"depth": 2, "version": "1.0"},
    )


def test_save_load_roundtrip(arch, tmp_path):
    path = tmp_path / "baseline.json"
    save_architecture(arch, path)
    loaded = load_architecture(path)

    assert loaded.algorithm == arch.algorithm
    assert loaded.rationale == arch.rationale
    assert len(loaded.components) == len(arch.components)
    for orig, loaded_c in zip(arch.components, loaded.components):
        assert loaded_c.name == orig.name
        assert loaded_c.responsibility == orig.responsibility
        assert loaded_c.entities == orig.entities


def test_load_nonexistent(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_architecture(tmp_path / "does_not_exist.json")


def test_save_creates_directory(arch, tmp_path):
    path = tmp_path / "nested" / "deep" / "baseline.json"
    save_architecture(arch, path)
    assert path.exists()
    loaded = load_architecture(path)
    assert len(loaded.components) == 2


def test_roundtrip_preserves_metadata(arch, tmp_path):
    path = tmp_path / "baseline.json"
    save_architecture(arch, path)
    loaded = load_architecture(path)

    assert loaded.metadata == {"depth": 2, "version": "1.0"}
    assert loaded.algorithm == "pkg"
    assert loaded.rationale == "Package-based grouping"


# ---------------------------------------------------------------------------
# DependencyGraph serialization
# ---------------------------------------------------------------------------


@pytest.fixture
def graph():
    return DependencyGraph(
        entities={
            "com.example.Main": Entity(
                fqn="com.example.Main",
                name="Main",
                package="com.example",
                file_path="Main.java",
                kind="class",
                language="java",
                imports=["com.example.Helper"],
                superclass=None,
                interfaces=["Runnable"],
                properties={"visibility": "public"},
            ),
            "com.example.Helper": Entity(
                fqn="com.example.Helper",
                name="Helper",
                package="com.example",
                file_path="Helper.java",
                kind="class",
                language="java",
            ),
        },
        edges=[
            Edge(source="com.example.Main", target="com.example.Helper", relation="import"),
        ],
        packages={"com.example": ["com.example.Main", "com.example.Helper"]},
    )


def test_graph_save_load_roundtrip(graph, tmp_path):
    path = tmp_path / "graph.json"
    save_graph(graph, path)
    loaded = load_graph(path)

    assert loaded.num_entities == graph.num_entities
    assert loaded.num_edges == graph.num_edges
    assert set(loaded.entities.keys()) == set(graph.entities.keys())

    main = loaded.entities["com.example.Main"]
    assert main.name == "Main"
    assert main.imports == ["com.example.Helper"]
    assert main.interfaces == ["Runnable"]
    assert main.properties == {"visibility": "public"}

    assert loaded.edges[0].source == "com.example.Main"
    assert loaded.edges[0].relation == "import"
    assert loaded.packages == graph.packages


def test_graph_load_nonexistent(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_graph(tmp_path / "nonexistent.json")
