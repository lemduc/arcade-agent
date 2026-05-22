"""Tests for parse result caching."""

import pytest

from arcade_agent.cache import (
    cache_key,
    get_cached_graph,
    invalidate_cache,
    put_cached_graph,
)
from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project directory with source files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "Main.java").write_text("public class Main {}")
    (src / "Helper.java").write_text("public class Helper {}")
    return tmp_path


@pytest.fixture
def small_graph():
    return DependencyGraph(
        entities={
            "Main": Entity(
                fqn="Main", name="Main", package="", file_path="Main.java",
                kind="class", language="java",
            ),
        },
        edges=[Edge(source="Main", target="Helper", relation="import")],
        packages={"": ["Main"]},
    )


def test_cache_key_deterministic(tmp_project):
    k1 = cache_key(str(tmp_project), "java", None)
    k2 = cache_key(str(tmp_project), "java", None)
    assert k1 == k2


def test_cache_key_changes_with_language(tmp_project):
    k1 = cache_key(str(tmp_project), "java", None)
    k2 = cache_key(str(tmp_project), "python", None)
    assert k1 != k2


def test_cache_key_changes_with_file_modification(tmp_project):
    k1 = cache_key(str(tmp_project), "java", None)
    # Modify a file
    (tmp_project / "src" / "Main.java").write_text("public class Main { int x; }")
    k2 = cache_key(str(tmp_project), "java", None)
    assert k1 != k2


def test_cache_miss_returns_none(tmp_project):
    result = get_cached_graph(str(tmp_project), "nonexistent_key")
    assert result is None


def test_cache_roundtrip(tmp_project, small_graph):
    key = "test_key_123"
    put_cached_graph(str(tmp_project), key, small_graph)
    loaded = get_cached_graph(str(tmp_project), key)
    assert loaded is not None
    assert loaded.num_entities == 1
    assert loaded.num_edges == 1
    assert loaded.entities["Main"].name == "Main"
    assert loaded.edges[0].source == "Main"


def test_invalidate_cache(tmp_project, small_graph):
    put_cached_graph(str(tmp_project), "key1", small_graph)
    put_cached_graph(str(tmp_project), "key2", small_graph)
    removed = invalidate_cache(str(tmp_project))
    assert removed == 2
    assert get_cached_graph(str(tmp_project), "key1") is None
    assert get_cached_graph(str(tmp_project), "key2") is None


def test_invalidate_empty_cache(tmp_project):
    removed = invalidate_cache(str(tmp_project))
    assert removed == 0


def test_corrupt_cache_file_returns_none(tmp_project):
    cache_dir = tmp_project / ".arcade-cache"
    cache_dir.mkdir()
    (cache_dir / "bad_key.json").write_text("not valid json {{{")
    result = get_cached_graph(str(tmp_project), "bad_key")
    assert result is None
    # Corrupt file should be cleaned up
    assert not (cache_dir / "bad_key.json").exists()
