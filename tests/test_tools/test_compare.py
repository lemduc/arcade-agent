"""Tests for the compare tool's structural classification."""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.tools.compare import compare


def _arch(**components: list[str]) -> Architecture:
    return Architecture(
        components=[
            Component(name=name, responsibility="", entities=list(entities))
            for name, entities in components.items()
        ],
        algorithm="test",
    )


def test_summary_uses_accurate_split_merge_keys():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    result = compare(arch_a, arch_b)
    assert result["summary"]["splits"] == 1
    assert result["summary"]["merges"] == 0
    assert "possible_splits" not in result["summary"]
    assert "possible_merges" not in result["summary"]


def test_split_is_not_double_counted_as_an_addition():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    result = compare(arch_a, arch_b)
    assert result["summary"]["components_added"] == 0


def test_refactored_rename_is_not_labelled_a_split():
    arch_a = _arch(util=["u.1", "u.2", "u.3", "u.4"])
    arch_b = _arch(common=["u.1", "u.2", "u.3", "u.4"])
    result = compare(arch_a, arch_b)
    assert result["summary"]["splits"] == 0
    assert result["summary"]["merges"] == 0


def test_similarity_and_matches_are_preserved():
    arch = _arch(auth=["a.A", "a.B"])
    result = compare(arch, arch)
    assert result["overall_similarity"] == 1.0
    assert isinstance(result["matches"], list)
