"""Tests for coupling and metric algorithms."""

from arcade_agent.algorithms.coupling import (
    compute_all_metrics,
    compute_rci,
    compute_turbo_mq,
)


def test_rci(sample_architecture, sample_graph):
    result = compute_rci(sample_architecture, sample_graph)
    assert result.name == "RCI"
    assert 0.0 <= result.value <= 1.0


def test_turbo_mq(sample_architecture, sample_graph):
    result = compute_turbo_mq(sample_architecture, sample_graph)
    assert result.name == "TurboMQ"
    assert 0.0 <= result.value <= 1.0


def test_all_metrics(sample_architecture, sample_graph):
    results = compute_all_metrics(sample_architecture, sample_graph)
    assert len(results) == 6
