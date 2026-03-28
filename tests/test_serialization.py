"""Tests for architecture serialization."""

import pytest

from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.serialization import load_architecture, save_architecture


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
