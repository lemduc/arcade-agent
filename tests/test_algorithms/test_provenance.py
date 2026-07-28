"""Tests for entity provenance between two architectures."""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.provenance import Flow, entity_flows


def _arch(**components: list[str]) -> Architecture:
    """Build an Architecture from name -> entity FQN list."""
    return Architecture(
        components=[
            Component(name=name, responsibility="", entities=list(entities))
            for name, entities in components.items()
        ],
        algorithm="test",
    )


def test_identical_architectures_produce_self_flows():
    arch = _arch(auth=["a.A", "a.B"])
    flows = entity_flows(arch, arch)
    assert flows == (Flow(source="auth", target="auth", entities=("a.A", "a.B")),)


def test_entity_moving_between_components_produces_cross_flow():
    arch_a = _arch(auth=["a.A", "a.B"], api=["x.X"])
    arch_b = _arch(auth=["a.A"], api=["x.X", "a.B"])
    flows = entity_flows(arch_a, arch_b)
    assert Flow(source="auth", target="api", entities=("a.B",)) in flows
    assert Flow(source="auth", target="auth", entities=("a.A",)) in flows


def test_entity_only_in_one_side_produces_no_flow():
    arch_a = _arch(auth=["a.A", "gone.G"])
    arch_b = _arch(auth=["a.A", "new.N"])
    flows = entity_flows(arch_a, arch_b)
    assert flows == (Flow(source="auth", target="auth", entities=("a.A",)),)


def test_flows_are_sorted_deterministically():
    arch_a = _arch(zeta=["z.Z"], alpha=["a.A"])
    arch_b = _arch(zeta=["z.Z"], alpha=["a.A"])
    flows = entity_flows(arch_a, arch_b)
    assert [f.source for f in flows] == ["alpha", "zeta"]


def test_empty_architectures_produce_no_flows():
    assert entity_flows(Architecture(), Architecture()) == ()
