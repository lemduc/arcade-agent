"""Tests for the recover tool."""

import pytest

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


def test_unknown_algorithm(sample_graph):
    with pytest.raises(ValueError, match="Unknown algorithm"):
        recover(sample_graph, algorithm="unknown")
