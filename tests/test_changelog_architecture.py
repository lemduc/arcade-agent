"""Tests for the changelog_architecture tool."""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.changelog_architecture import changelog_architecture


def _arch(**components: list[str]) -> Architecture:
    return Architecture(
        components=[
            Component(name=name, responsibility="", entities=list(entities))
            for name, entities in components.items()
        ],
        algorithm="test",
    )


def _empty_graph() -> DependencyGraph:
    return DependencyGraph()


def test_reports_structural_changes():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    result = changelog_architecture(
        arch_a, _empty_graph(), arch_b, _empty_graph(),
        smells_a=[], smells_b=[], metrics_a=[], metrics_b=[],
    )
    assert result["components"]["split"] == [
        {"from": "auth", "into": ["auth", "authz"],
         "entities": {"auth": 3, "authz": 3}}
    ]
    # note: _structural_dict converts Split.entities (a tuple of pairs) into a
    # plain dict for the output, so the serialised shape stays dict-shaped.
    assert result["components"]["added"] == []


def test_reports_responsibility_shifts_at_entity_granularity():
    arch_a = _arch(auth=["a.A", "a.B", "a.C"], api=["p.1", "p.2", "p.3"])
    arch_b = _arch(auth=["a.A", "a.B"], api=["p.1", "p.2", "p.3", "a.C"])
    result = changelog_architecture(
        arch_a, _empty_graph(), arch_b, _empty_graph(),
        smells_a=[], smells_b=[], metrics_a=[], metrics_b=[],
    )
    assert {"entity": "a.C", "from": "auth", "to": "api"} in result["responsibility_shifts"]


def test_smell_survives_a_rename_without_spurious_churn():
    arch_a = _arch(util=["u.1", "u.2", "u.3"])
    arch_b = _arch(common=["u.1", "u.2", "u.3"])
    smell_a = SmellInstance(smell_type="BDC", severity="high", affected_components=["util"])
    smell_b = SmellInstance(smell_type="BDC", severity="high", affected_components=["common"])
    result = changelog_architecture(
        arch_a, _empty_graph(), arch_b, _empty_graph(),
        smells_a=[smell_a], smells_b=[smell_b], metrics_a=[], metrics_b=[],
    )
    assert result["smells"]["new"] == []
    assert result["smells"]["resolved"] == []
    assert len(result["smells"]["persisting"]) == 1


def test_new_and_resolved_smells_are_reported():
    arch = _arch(auth=["a.1", "a.2", "a.3"])
    gone = SmellInstance(smell_type="BCO", severity="low", affected_components=["auth"])
    fresh = SmellInstance(smell_type="BDC", severity="high", affected_components=["auth"])
    result = changelog_architecture(
        arch, _empty_graph(), arch, _empty_graph(),
        smells_a=[gone], smells_b=[fresh], metrics_a=[], metrics_b=[],
    )
    assert [s["smell_type"] for s in result["smells"]["new"]] == ["BDC"]
    assert [s["smell_type"] for s in result["smells"]["resolved"]] == ["BCO"]


def test_metric_deltas():
    arch = _arch(auth=["a.1", "a.2", "a.3"])
    result = changelog_architecture(
        arch, _empty_graph(), arch, _empty_graph(),
        smells_a=[], smells_b=[],
        metrics_a=[MetricResult(name="RCI", value=0.30)],
        metrics_b=[MetricResult(name="RCI", value=0.44)],
    )
    assert result["metrics"]["RCI"]["a"] == 0.30
    assert result["metrics"]["RCI"]["b"] == 0.44
    assert round(result["metrics"]["RCI"]["delta"], 4) == 0.14


def test_metric_present_on_only_one_side_has_null_delta():
    arch = _arch(auth=["a.1", "a.2", "a.3"])
    result = changelog_architecture(
        arch, _empty_graph(), arch, _empty_graph(),
        smells_a=[], smells_b=[],
        metrics_a=[], metrics_b=[MetricResult(name="TurboMQ", value=1.5)],
    )
    assert result["metrics"]["TurboMQ"]["a"] is None
    assert result["metrics"]["TurboMQ"]["delta"] is None


def test_refs_are_recorded_as_metadata():
    arch = _arch(auth=["a.1", "a.2", "a.3"])
    result = changelog_architecture(
        arch, _empty_graph(), arch, _empty_graph(),
        smells_a=[], smells_b=[], metrics_a=[], metrics_b=[],
        ref_a="v0.1.1", ref_b="v0.2.0",
    )
    assert result["refs"] == {"a": "v0.1.1", "b": "v0.2.0"}


def test_empty_architectures_do_not_raise():
    result = changelog_architecture(
        Architecture(), _empty_graph(), Architecture(), _empty_graph(),
        smells_a=[], smells_b=[], metrics_a=[], metrics_b=[],
    )
    assert result["summary"]["components_a"] == 0
    assert result["summary"]["components_b"] == 0
