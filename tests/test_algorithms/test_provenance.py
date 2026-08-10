"""Tests for entity provenance between two architectures."""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.provenance import (
    Flow,
    Merge,
    Rewrite,
    Split,
    classify_structural_changes,
    entity_flows,
    structural_dict,
)


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


def test_identity_is_all_stable():
    arch = _arch(auth=["a.A", "a.B", "a.C"])
    changes = classify_structural_changes(arch, arch)
    assert changes.stable == ("auth",)
    assert changes.added == ()
    assert changes.removed == ()
    assert changes.renamed == ()
    assert changes.split == ()
    assert changes.merged == ()


def test_pure_rename():
    arch_a = _arch(util=["u.A", "u.B", "u.C"])
    arch_b = _arch(common=["u.A", "u.B", "u.C"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.renamed == (("util", "common"),)
    assert changes.added == ()
    assert changes.removed == ()
    assert changes.rename_map == (("util", "common"),)


def test_clean_split_does_not_also_report_an_addition():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.split == (
        Split(source="auth", targets=("auth", "authz"),
              entities=(("auth", 3), ("authz", 3))),
    )
    assert changes.added == ()
    assert changes.renamed == ()


def test_clean_merge_does_not_also_report_a_removal():
    arch_a = _arch(core=["c.A", "c.B", "c.C"], util=["u.X", "u.Y", "u.Z"])
    arch_b = _arch(core=["c.A", "c.B", "c.C", "u.X", "u.Y", "u.Z"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.merged == (
        Merge(target="core", sources=("core", "util"),
              entities=(("core", 3), ("util", 3))),
    )
    assert changes.removed == ()
    assert changes.renamed == ()


def test_precedence_absorbed_component_is_not_also_a_rename():
    # util's entities all land in core, and core also keeps its own -> merge.
    # util has exactly one outgoing flow, which would otherwise read as a rename.
    arch_a = _arch(core=["c.A", "c.B", "c.C"], util=["u.X", "u.Y", "u.Z"])
    arch_b = _arch(core=["c.A", "c.B", "c.C", "u.X", "u.Y", "u.Z"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.renamed == ()
    assert changes.stable == ()
    assert changes.removed == ()
    assert [m.target for m in changes.merged] == ["core"]


def test_precedence_split_product_is_not_also_an_addition_or_rename():
    arch_a = _arch(auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])
    arch_b = _arch(auth=["a.A", "a.B", "a.C"], authz=["z.X", "z.Y", "z.Z"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert "authz" not in changes.added
    assert changes.renamed == ()
    assert changes.split[0].targets == ("auth", "authz")


def test_split_and_merge_in_the_same_diff():
    arch_a = _arch(
        auth=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"],
        util=["u.1", "u.2", "u.3"],
        core=["c.1", "c.2", "c.3"],
    )
    arch_b = _arch(
        auth=["a.A", "a.B", "a.C"],
        authz=["z.X", "z.Y", "z.Z"],
        core=["c.1", "c.2", "c.3", "u.1", "u.2", "u.3"],
    )
    changes = classify_structural_changes(arch_a, arch_b)
    assert [s.source for s in changes.split] == ["auth"]
    assert [m.target for m in changes.merged] == ["core"]
    assert changes.added == ()
    assert changes.removed == ()


def test_sub_threshold_flow_is_not_a_split():
    # One entity leaves a large component: below min_entities=3 and below
    # 20% of min(9, 1)=1 ... share is 1/1 = 1.0, so raise min_share above it
    # by making the target large too.
    arch_a = _arch(
        big=["b.1", "b.2", "b.3", "b.4", "b.5", "b.6", "b.7", "b.8", "b.9"],
        other=["o.1", "o.2", "o.3", "o.4", "o.5"],
    )
    arch_b = _arch(
        big=["b.1", "b.2", "b.3", "b.4", "b.5", "b.6", "b.7", "b.8"],
        other=["o.1", "o.2", "o.3", "o.4", "o.5", "b.9"],
    )
    changes = classify_structural_changes(arch_a, arch_b, min_entities=3, min_share=0.5)
    assert changes.split == ()
    assert changes.stable == ("big", "other")


def test_component_with_no_significant_outflow_is_removed():
    arch_a = _arch(dead=["d.1", "d.2", "d.3"], keep=["k.1", "k.2", "k.3"])
    arch_b = _arch(keep=["k.1", "k.2", "k.3"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.removed == ("dead",)
    assert changes.stable == ("keep",)


def test_brand_new_component_is_added():
    arch_a = _arch(keep=["k.1", "k.2", "k.3"])
    arch_b = _arch(keep=["k.1", "k.2", "k.3"], fresh=["f.1", "f.2", "f.3"])
    changes = classify_structural_changes(arch_a, arch_b)
    assert changes.added == ("fresh",)


def test_component_rewritten_in_place_is_not_both_added_and_removed():
    # A component that keeps its name while every one of its entities churns
    # has neither a significant outgoing nor a significant incoming flow. It
    # used to fall into `added` *and* `removed`, so the same name was printed
    # as "added `PkgAuth`" directly above "removed `PkgAuth`" while the
    # component table showed it unchanged. It is a rewrite, not both.
    arch_a = _arch(auth=[f"old.M{i:02d}" for i in range(12)])
    arch_b = _arch(auth=[f"new.S{i:02d}" for i in range(12)])
    changes = classify_structural_changes(arch_a, arch_b)

    assert changes.added == ()
    assert changes.removed == ()
    assert changes.rewritten == (
        Rewrite(name="auth", before=12, after=12, retained=0),
    )
    assert changes.stable == ()
    assert changes.renamed == ()


def test_rewrite_records_sub_threshold_retained_entities():
    # One entity survives -- too few to be a significant self-flow (1 of 12 is
    # under both min_entities=8 and min_share=0.20), but the reader deserves
    # to know the rewrite was not total.
    kept = "keep.K"
    arch_a = _arch(auth=[kept] + [f"old.M{i:02d}" for i in range(11)])
    arch_b = _arch(auth=[kept] + [f"new.S{i:02d}" for i in range(11)])
    changes = classify_structural_changes(arch_a, arch_b)

    assert changes.rewritten == (
        Rewrite(name="auth", before=12, after=12, retained=1),
    )
    assert changes.added == ()
    assert changes.removed == ()


def test_empty_component_on_both_sides_is_stable_not_added_and_removed():
    # Zero entities on both sides means zero flows, which also landed the name
    # in `added` and `removed` at once. Nothing changed, so it is stable --
    # calling it "rewritten" would overstate a component that has no content
    # to rewrite.
    arch_a = _arch(ghost=[], keep=["k.1", "k.2", "k.3"])
    arch_b = _arch(ghost=[], keep=["k.1", "k.2", "k.3"])
    changes = classify_structural_changes(arch_a, arch_b)

    assert changes.added == ()
    assert changes.removed == ()
    assert changes.rewritten == ()
    assert changes.stable == ("ghost", "keep")


def test_emptied_component_that_keeps_its_name_is_a_rewrite_not_a_removal():
    arch_a = _arch(auth=[f"old.M{i:02d}" for i in range(12)], keep=["k.1", "k.2", "k.3"])
    arch_b = _arch(auth=[], keep=["k.1", "k.2", "k.3"])
    changes = classify_structural_changes(arch_a, arch_b)

    assert changes.removed == ()
    assert changes.rewritten == (
        Rewrite(name="auth", before=12, after=0, retained=0),
    )


def test_surviving_name_is_not_reported_removed_when_it_is_a_rename_target():
    # `X`'s own entities are all deleted, but the name survives in arch_b as
    # the destination of `util`'s entities. Reporting "renamed util -> X" and
    # "removed X" in the same report contradicts itself: X is still there.
    arch_a = _arch(X=["x.1", "x.2", "x.3"], util=["u.1", "u.2", "u.3"])
    arch_b = _arch(X=["u.1", "u.2", "u.3"])
    changes = classify_structural_changes(arch_a, arch_b)

    assert changes.renamed == (("util", "X"),)
    assert changes.removed == ()
    assert changes.added == ()


def test_added_and_removed_never_name_the_same_component():
    arch_a = _arch(
        auth=[f"old.M{i:02d}" for i in range(12)],
        dead=["d.1", "d.2", "d.3"],
    )
    arch_b = _arch(
        auth=[f"new.S{i:02d}" for i in range(12)],
        fresh=["f.1", "f.2", "f.3"],
    )
    changes = classify_structural_changes(arch_a, arch_b)

    assert set(changes.added) & set(changes.removed) == set()
    assert changes.added == ("fresh",)
    assert changes.removed == ("dead",)
    assert [r.name for r in changes.rewritten] == ["auth"]


def test_structural_dict_serialises_rewrites():
    arch_a = _arch(auth=[f"old.M{i:02d}" for i in range(12)])
    arch_b = _arch(auth=[f"new.S{i:02d}" for i in range(12)])
    payload = structural_dict(classify_structural_changes(arch_a, arch_b))

    assert payload["rewritten"] == [
        {"name": "auth", "before": 12, "after": 12, "retained": 0}
    ]
    assert payload["added"] == []
    assert payload["removed"] == []


def test_both_sides_empty():
    changes = classify_structural_changes(Architecture(), Architecture())
    assert changes.added == ()
    assert changes.removed == ()
    assert changes.flows == ()


def test_invalid_min_share_raises():
    import pytest

    with pytest.raises(ValueError, match="min_share"):
        classify_structural_changes(Architecture(), Architecture(), min_share=0.0)


def test_split_source_may_also_appear_in_a_merges_sources():
    # S splits into (S, T); T also independently absorbs X. S is genuinely
    # both a split source and one of T's merge sources -- Split.targets and
    # Merge.sources are descriptive provenance, not classification, and may
    # name a component that is itself classified elsewhere. See the
    # StructuralChanges docstring for the ruling this test pins.
    arch_a = _arch(S=["s1", "s2", "s3", "s4", "s5", "s6"], X=["x1", "x2", "x3"])
    arch_b = _arch(S=["s1", "s2", "s3"], T=["s4", "s5", "s6", "x1", "x2", "x3"])
    changes = classify_structural_changes(arch_a, arch_b)

    assert changes.split == (
        Split(source="S", targets=("S", "T"), entities=(("S", 3), ("T", 3))),
    )
    assert changes.merged == (
        Merge(target="T", sources=("S", "X"), entities=(("S", 3), ("X", 3))),
    )
    # The documented overlap: "S" names both a split source and a merge source.
    assert changes.split[0].source == "S"
    assert "S" in changes.merged[0].sources

    # The six top-level buckets still classify every component exactly once.
    assert changes.removed == ()
    assert changes.renamed == ()
    assert changes.stable == ()
    assert changes.added == ()

    # arch_a: "S" is classified as a split source; "X" has no top-level
    # bucket of its own -- it is absorbed into the merge (present only in
    # Merge.sources), which is the documented resolution, not a bug.
    assert "X" not in changes.removed
    assert "X" not in changes.stable
    assert all(s.source != "X" for s in changes.split)
    assert any("X" in m.sources for m in changes.merged)

    # arch_b: "T" is classified as a merge target. "S" (arch_b) has no
    # top-level bucket of its own -- it is a split product (present only in
    # Split.targets), the documented resolution for the other direction.
    assert any(m.target == "T" for m in changes.merged)
    assert "S" not in changes.added
    assert all(m.target != "S" for m in changes.merged)
    assert any("S" in s.targets for s in changes.split)
