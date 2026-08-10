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


def test_summary_added_count_agrees_with_structural_added_names():
    """Pins the fix for the summary-vs-matches contradiction.

    ``summary["components_added"]`` and ``structural["added"]`` must always
    describe the same set of components, even though ``matches`` (the raw
    Hungarian 1:1 view) may separately show a split product as an unmatched
    "target only" entry. Consumers must read component names from
    ``structural``, not from ``matches``, to avoid rendering the same diff
    two contradictory ways (e.g. "Components Added: 0" next to
    "New components: authz").
    """
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    result = compare(arch_a, arch_b)

    assert result["summary"]["components_added"] == len(result["structural"]["added"])
    assert result["structural"]["added"] == []
    # The split product IS present in `matches` as an unmatched target --
    # this is the raw Hungarian view the review found contradicted the
    # summary, and it must stay that way; `structural` is what disagrees
    # correctly instead.
    unmatched_targets = [m["target"] for m in result["matches"] if not m["source"]]
    assert unmatched_targets == ["authz"]
    assert "authz" not in result["structural"]["added"]
