"""Tests for ARC (Architecture Recovery using Concerns) algorithm."""

from unittest.mock import patch

from arcade_agent.algorithms.arc import (
    _build_concern_vectors,
    _js_divergence,
    _js_similarity,
    _merge_vectors,
    _tag_entities_heuristic,
    arc,
)
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity


def _make_graph():
    """Build a graph with clear concern separation."""
    entities = {
        "com.app.auth.LoginService": Entity(
            fqn="com.app.auth.LoginService", name="LoginService",
            package="com.app.auth", file_path="LoginService.java",
            kind="class", language="java",
            imports=["com.app.auth.TokenValidator"],
        ),
        "com.app.auth.TokenValidator": Entity(
            fqn="com.app.auth.TokenValidator", name="TokenValidator",
            package="com.app.auth", file_path="TokenValidator.java",
            kind="class", language="java",
        ),
        "com.app.db.UserRepository": Entity(
            fqn="com.app.db.UserRepository", name="UserRepository",
            package="com.app.db", file_path="UserRepository.java",
            kind="class", language="java",
            imports=["com.app.db.ConnectionPool"],
        ),
        "com.app.db.ConnectionPool": Entity(
            fqn="com.app.db.ConnectionPool", name="ConnectionPool",
            package="com.app.db", file_path="ConnectionPool.java",
            kind="class", language="java",
        ),
        "com.app.ui.Dashboard": Entity(
            fqn="com.app.ui.Dashboard", name="Dashboard",
            package="com.app.ui", file_path="Dashboard.java",
            kind="class", language="java",
            imports=["com.app.ui.Renderer"],
        ),
        "com.app.ui.Renderer": Entity(
            fqn="com.app.ui.Renderer", name="Renderer",
            package="com.app.ui", file_path="Renderer.java",
            kind="class", language="java",
        ),
    }
    edges = [
        Edge(
            source="com.app.auth.LoginService",
            target="com.app.auth.TokenValidator",
            relation="import",
        ),
        Edge(
            source="com.app.db.UserRepository",
            target="com.app.db.ConnectionPool",
            relation="import",
        ),
        Edge(
            source="com.app.ui.Dashboard",
            target="com.app.ui.Renderer",
            relation="import",
        ),
    ]
    packages = {
        "com.app.auth": ["com.app.auth.LoginService", "com.app.auth.TokenValidator"],
        "com.app.db": ["com.app.db.UserRepository", "com.app.db.ConnectionPool"],
        "com.app.ui": ["com.app.ui.Dashboard", "com.app.ui.Renderer"],
    }
    return DependencyGraph(entities=entities, edges=edges, packages=packages)


def test_js_divergence_identical():
    """Identical distributions should have 0 divergence."""
    p = [0.5, 0.3, 0.2]
    assert _js_divergence(p, p) < 1e-10


def test_js_divergence_different():
    """Different distributions should have positive divergence."""
    p = [0.9, 0.05, 0.05]
    q = [0.05, 0.05, 0.9]
    d = _js_divergence(p, q)
    assert d > 0.3


def test_js_similarity_range():
    """JS similarity should be in [0, 1]."""
    p = [0.7, 0.2, 0.1]
    q = [0.1, 0.2, 0.7]
    s = _js_similarity(p, q)
    assert 0.0 <= s <= 1.0


def test_merge_vectors_weighted():
    """Merged vector should be weighted by cluster sizes."""
    vec_a = [0.8, 0.1, 0.1]
    vec_b = [0.1, 0.1, 0.8]
    merged = _merge_vectors(vec_a, 3, vec_b, 1)
    # vec_a has 3x the weight
    assert merged[0] > merged[2]
    # Should be normalized
    assert abs(sum(merged) - 1.0) < 1e-6


def test_build_concern_vectors():
    """Concern vectors should have correct dimensions and be normalized."""
    entities = ["A", "B", "C"]
    tags = {
        "A": ["auth", "security"],
        "B": ["auth"],
        "C": ["persistence", "data"],
    }
    labels, vectors = _build_concern_vectors(entities, tags)
    assert len(labels) == 4  # auth, data, persistence, security
    for fqn in entities:
        vec = vectors[fqn]
        assert len(vec) == 4
        assert abs(sum(vec) - 1.0) < 1e-6


def test_tag_entities_heuristic():
    """Heuristic tagger should produce tags for all entities."""
    graph = _make_graph()
    tags = _tag_entities_heuristic(graph)
    assert len(tags) == 6
    # Package-based tags
    assert "auth" in tags["com.app.auth.LoginService"]
    assert "db" in tags["com.app.db.UserRepository"]
    # Suffix-based tag for Repository
    assert "data access" in tags["com.app.db.UserRepository"]


def test_arc_mock_mode():
    """ARC in mock mode should use heuristic tagging and produce components."""
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        arch = arc(graph, num_clusters=3)
    assert arch.algorithm == "arc"
    assert len(arch.components) == 3
    # All entities should be assigned
    all_entities = []
    for comp in arch.components:
        all_entities.extend(comp.entities)
    assert sorted(all_entities) == sorted(graph.entities.keys())


def test_arc_with_llm():
    """ARC with mocked LLM should cluster by semantic concerns."""
    graph = _make_graph()

    llm_tags = {
        "com.app.auth.LoginService": ["authentication", "security"],
        "com.app.auth.TokenValidator": ["authentication", "validation"],
        "com.app.db.UserRepository": ["persistence", "data access"],
        "com.app.db.ConnectionPool": ["persistence", "connection management"],
        "com.app.ui.Dashboard": ["ui rendering", "visualization"],
        "com.app.ui.Renderer": ["ui rendering", "graphics"],
    }

    with patch("arcade_agent.algorithms.llm.MOCK_MODE", False), \
         patch("arcade_agent.algorithms.llm.ask_claude_json", return_value=llm_tags):
        arch = arc(graph, num_clusters=3)

    assert arch.algorithm == "arc"
    assert len(arch.components) == 3

    # Entities with shared concerns should cluster together
    for comp in arch.components:
        fqns = set(comp.entities)
        # Auth entities should be together
        if "com.app.auth.LoginService" in fqns:
            assert "com.app.auth.TokenValidator" in fqns
        # DB entities should be together
        if "com.app.db.UserRepository" in fqns:
            assert "com.app.db.ConnectionPool" in fqns
        # UI entities should be together
        if "com.app.ui.Dashboard" in fqns:
            assert "com.app.ui.Renderer" in fqns


def test_arc_components_have_responsibility():
    """ARC components should have concern-derived responsibility strings."""
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        arch = arc(graph, num_clusters=3)
    for comp in arch.components:
        assert comp.responsibility  # Not empty
        assert comp.name  # Not empty


def test_arc_hybrid_weight():
    """Different hybrid weights should produce valid architectures."""
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        # Pure semantic
        arch_sem = arc(graph, num_clusters=3, hybrid_weight=1.0)
        assert len(arch_sem.components) == 3

        # Pure structural
        arch_str = arc(graph, num_clusters=3, hybrid_weight=0.0)
        assert len(arch_str.components) == 3

        # Hybrid
        arch_hyb = arc(graph, num_clusters=3, hybrid_weight=0.5)
        assert len(arch_hyb.components) == 3


def test_recover_tool_arc():
    """Verify recover() accepts algorithm='arc'."""
    from arcade_agent.tools.recover import recover
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        arch = recover(graph, algorithm="arc", num_clusters=3)
    assert arch.algorithm == "arc"
    assert len(arch.components) == 3
