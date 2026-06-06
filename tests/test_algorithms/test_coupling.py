"""Tests for coupling and metric algorithms."""

from arcade_agent.algorithms.coupling import (
    compute_all_metrics,
    compute_balanced_scores,
    compute_rci,
    compute_turbo_mq,
)
from arcade_agent.algorithms.smells import SmellInstance


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


def test_balanced_scores_are_bounded(sample_architecture, sample_graph):
    metrics = compute_all_metrics(sample_architecture, sample_graph)

    derived_metrics, principle_signals, score_drivers = compute_balanced_scores(
        sample_architecture,
        sample_graph,
        [],
        metrics=metrics,
    )

    assert {metric.name for metric in derived_metrics} == {
        "DependencyHealth",
        "ComponentBalance",
        "HubBalance",
        "BoundaryClarity",
        "DependencyDistribution",
        "SmellDiscipline",
        "PrincipleAlignmentScore",
        "BalancedArchitectureScore",
    }
    assert all(0.0 <= metric.value <= 1.0 for metric in derived_metrics)
    assert all(0.0 <= value <= 1.0 for value in principle_signals.values())
    assert {entry["name"] for entry in score_drivers["risks"]}
    assert {entry["name"] for entry in score_drivers["strengths"]}


def test_balanced_scores_drop_when_principle_smells_increase(sample_architecture, sample_graph):
    metrics = compute_all_metrics(sample_architecture, sample_graph)
    clean_metrics, clean_signals, _ = compute_balanced_scores(
        sample_architecture,
        sample_graph,
        [],
        metrics=metrics,
    )
    smelly_metrics, smelly_signals, _ = compute_balanced_scores(
        sample_architecture,
        sample_graph,
        [
            SmellInstance(
                smell_type="Dependency Cycle",
                severity="high",
                affected_components=["Calc", "Util"],
            ),
            SmellInstance(
                smell_type="Link/Upstream Overload",
                severity="high",
                affected_components=["Util"],
            ),
        ],
        metrics=metrics,
    )

    clean_lookup = {metric.name: metric.value for metric in clean_metrics}
    smelly_lookup = {metric.name: metric.value for metric in smelly_metrics}

    assert smelly_lookup["SmellDiscipline"] < clean_lookup["SmellDiscipline"]
    assert smelly_lookup["PrincipleAlignmentScore"] < clean_lookup["PrincipleAlignmentScore"]
    assert smelly_lookup["BalancedArchitectureScore"] < clean_lookup["BalancedArchitectureScore"]
    assert smelly_signals["AcyclicDependencies"] < clean_signals["AcyclicDependencies"]
    assert smelly_signals["InterfaceSegregation"] < clean_signals["InterfaceSegregation"]
