"""Tests for LIMBO (information-theoretic clustering) algorithm."""

from unittest.mock import patch

from arcade_agent.algorithms.arc import _js_divergence
from arcade_agent.algorithms.limbo import _info_loss, limbo
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


# ---------------------------------------------------------------------------
# _info_loss tests
# ---------------------------------------------------------------------------

def test_info_loss_identical_vectors():
    """Identical vectors should produce zero information loss."""
    vec = [0.5, 0.3, 0.2]
    loss = _info_loss(vec, 2, vec, 3, 10)
    assert loss < 1e-10


def test_info_loss_different_vectors():
    """Different vectors should produce positive information loss."""
    p = [0.9, 0.05, 0.05]
    q = [0.05, 0.05, 0.9]
    loss = _info_loss(p, 2, q, 3, 10)
    assert loss > 0.0


def test_info_loss_scales_with_size():
    """Larger clusters should produce more information loss for the same divergence."""
    p = [0.9, 0.05, 0.05]
    q = [0.05, 0.05, 0.9]
    loss_small = _info_loss(p, 1, q, 1, 10)
    loss_large = _info_loss(p, 4, q, 4, 10)
    assert loss_large > loss_small


def test_info_loss_formula():
    """Verify info loss matches (size_a + size_b) / total * JS(a, b)."""
    p = [0.7, 0.2, 0.1]
    q = [0.1, 0.2, 0.7]
    size_a, size_b, total = 3, 2, 10
    expected = (size_a + size_b) / total * _js_divergence(p, q)
    actual = _info_loss(p, size_a, q, size_b, total)
    assert abs(actual - expected) < 1e-10


# ---------------------------------------------------------------------------
# LIMBO algorithm tests
# ---------------------------------------------------------------------------

def test_limbo_empty_graph():
    """LIMBO on empty graph should return empty architecture."""
    graph = DependencyGraph(entities={}, edges=[], packages={})
    arch = limbo(graph)
    assert arch.algorithm == "limbo"
    assert len(arch.components) == 0


def test_limbo_mock_mode():
    """LIMBO in mock mode should produce valid components."""
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        arch = limbo(graph, num_clusters=3)
    assert arch.algorithm == "limbo"
    assert len(arch.components) == 3
    # All entities should be assigned
    all_entities = []
    for comp in arch.components:
        all_entities.extend(comp.entities)
    assert sorted(all_entities) == sorted(graph.entities.keys())


def test_limbo_with_llm():
    """LIMBO with mocked LLM should cluster by semantic concerns."""
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
        arch = limbo(graph, num_clusters=3)

    assert arch.algorithm == "limbo"
    assert len(arch.components) == 3

    # Entities with shared concerns should cluster together
    for comp in arch.components:
        fqns = set(comp.entities)
        if "com.app.auth.LoginService" in fqns:
            assert "com.app.auth.TokenValidator" in fqns
        if "com.app.db.UserRepository" in fqns:
            assert "com.app.db.ConnectionPool" in fqns
        if "com.app.ui.Dashboard" in fqns:
            assert "com.app.ui.Renderer" in fqns


def test_limbo_components_have_responsibility():
    """LIMBO components should have concern-derived responsibility strings."""
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        arch = limbo(graph, num_clusters=3)
    for comp in arch.components:
        assert comp.responsibility
        assert comp.name


def test_limbo_hybrid_weight():
    """Different hybrid weights should produce valid architectures."""
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        # Pure semantic (info-loss only)
        arch_sem = limbo(graph, num_clusters=3, hybrid_weight=1.0)
        assert len(arch_sem.components) == 3

        # Pure structural
        arch_str = limbo(graph, num_clusters=3, hybrid_weight=0.0)
        assert len(arch_str.components) == 3

        # Hybrid
        arch_hyb = limbo(graph, num_clusters=3, hybrid_weight=0.5)
        assert len(arch_hyb.components) == 3


def test_limbo_metadata():
    """LIMBO should populate metadata with algorithm parameters."""
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        arch = limbo(graph, num_clusters=3, hybrid_weight=0.7)
    assert arch.metadata["hybrid_weight"] == 0.7
    assert arch.metadata["num_clusters"] == 3
    assert "concern_labels" in arch.metadata
    assert "num_concerns" in arch.metadata


def test_recover_tool_limbo():
    """Verify recover() accepts algorithm='limbo'."""
    from arcade_agent.tools.recover import recover
    graph = _make_graph()
    with patch("arcade_agent.algorithms.llm.MOCK_MODE", True):
        arch = recover(graph, algorithm="limbo", num_clusters=3)
    assert arch.algorithm == "limbo"
    assert len(arch.components) == 3
