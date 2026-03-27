"""Tests for the compute_metrics tool."""

from arcade_agent.tools.compute_metrics import compute_metrics


def test_compute_metrics(sample_architecture, sample_graph):
    metrics = compute_metrics(sample_architecture, sample_graph)

    assert len(metrics) == 6
    metric_names = {m.name for m in metrics}
    assert "RCI" in metric_names
    assert "TurboMQ" in metric_names
    assert "BasicMQ" in metric_names
    assert "IntraConnectivity" in metric_names
    assert "InterConnectivity" in metric_names
    assert "TwoWayPairRatio" in metric_names


def test_metric_values_in_range(sample_architecture, sample_graph):
    metrics = compute_metrics(sample_architecture, sample_graph)

    for metric in metrics:
        assert 0.0 <= metric.value <= 1.0, f"{metric.name} = {metric.value} out of [0,1] range"
