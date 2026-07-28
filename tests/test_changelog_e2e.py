"""End-to-end changelog over arcade-agent's own history.

Measured datapoint that set the ``min_entities`` default (see
``algorithms/provenance.py::classify_structural_changes``): between
``v0.1.0`` and ``v0.1.1``, four entities moved from the 65-entity
``Algorithms`` component to the 56-entity ``Tools`` component -- ordinary
refactoring, about 7% of the smaller side (``min_share=0.20`` does not fire
on it either). At the old default ``min_entities=3`` this was misreported as
both a split (``Algorithms`` -> ``Algorithms`` + ``Tools``) and a merge
(``Tools`` <- ``Algorithms`` + ``Tools``). At ``min_entities=8`` both
components correctly read as stable; the underlying move is still visible as
a responsibility shift either way (entity-level shift count: 6, unaffected
by this threshold). ``min_entities`` therefore moved from 3 to 8.
``test_low_threshold_reports_algorithms_tools_as_split_and_merge`` and
``test_default_threshold_treats_algorithms_tools_move_as_stable`` below are
the durable record of this measurement.
"""

from pathlib import Path

import pytest

from arcade_agent.tools.changelog_architecture import changelog_architecture
from arcade_agent.tools.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover

REPO_ROOT = Path(__file__).resolve().parents[1]


def _has_tag(tag: str) -> bool:
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "--verify", f"{tag}^{{commit}}"],
        capture_output=True,
    )
    return result.returncode == 0


@pytest.mark.skipif(
    not (_has_tag("v0.1.1") and _has_tag("v0.2.0")),
    reason="requires the v0.1.1 and v0.2.0 tags",
)
def test_changelog_between_real_releases():
    repo_a = ingest(str(REPO_ROOT), language="python", ref="v0.1.1")
    repo_b = ingest(str(REPO_ROOT), language="python", ref="v0.2.0")
    try:
        graph_a = parse(str(repo_a.path), language="python")
        graph_b = parse(str(repo_b.path), language="python")
        arch_a = recover(graph_a, algorithm="pkg")
        arch_b = recover(graph_b, algorithm="pkg")

        result = changelog_architecture(
            arch_a, graph_a, arch_b, graph_b, ref_a="v0.1.1", ref_b="v0.2.0"
        )

        assert result["refs"] == {"a": "v0.1.1", "b": "v0.2.0"}

        # Concrete regression assertion: this is the actual observed shape of
        # the v0.1.1 -> v0.2.0 diff at the default thresholds, not just an
        # invariant a broken pipeline could still satisfy (e.g. "everything
        # stable" also trivially partitions arch_b's components). It fails if
        # pipeline behaviour changes.
        summary = result["summary"]
        assert summary["components_a"] == 9
        assert summary["components_b"] == 9
        assert summary["shifts"] == 1
        assert summary["entities_a"] == 305
        assert summary["entities_b"] == 331

        components = result["components"]
        assert components["added"] == []
        assert components["removed"] == []
        assert components["renamed"] == []
        assert components["split"] == []
        assert components["merged"] == []
        assert len(components["stable"]) == 9

        # The six top-level buckets classify every arch_b component exactly
        # once. Split.targets / Merge.sources are provenance detail and may
        # name a component classified elsewhere, so they are excluded from
        # this check. Kept as an additional invariant alongside the concrete
        # assertions above, not as the only check.
        classified = (
            list(components["added"])
            + [m["into"] for m in components["merged"]]
            + [e["to"] for e in components["renamed"]]
            + list(components["stable"])
            + [t for s in components["split"] for t in s["into"]]
        )
        names_b = {c.name for c in arch_b.components}
        assert set(classified) == names_b, "every component must be classified"
    finally:
        repo_a.cleanup()
        repo_b.cleanup()


@pytest.mark.skipif(
    not (_has_tag("v0.1.0") and _has_tag("v0.1.1")),
    reason="requires the v0.1.0 and v0.1.1 tags",
)
def test_low_threshold_reports_algorithms_tools_as_split_and_merge():
    """At min_entities=3, the Algorithms/Tools refactor reads as split+merge.

    This is the datapoint that motivated raising the default to 8 (see the
    module docstring): explicitly passing the old default reproduces the
    over-eager classification so the measurement stays pinned even after the
    library default changes.
    """
    repo_a = ingest(str(REPO_ROOT), language="python", ref="v0.1.0")
    repo_b = ingest(str(REPO_ROOT), language="python", ref="v0.1.1")
    try:
        graph_a = parse(str(repo_a.path), language="python")
        graph_b = parse(str(repo_b.path), language="python")
        arch_a = recover(graph_a, algorithm="pkg")
        arch_b = recover(graph_b, algorithm="pkg")

        result = changelog_architecture(
            arch_a, graph_a, arch_b, graph_b,
            ref_a="v0.1.0", ref_b="v0.1.1", min_entities=3,
        )

        components = result["components"]
        assert components["split"] == [
            {
                "from": "Algorithms",
                "into": ["Algorithms", "Tools"],
                "entities": {"Algorithms": 60, "Tools": 4},
            }
        ]
        assert components["merged"] == [
            {
                "into": "Tools",
                "from": ["Algorithms", "Tools"],
                "entities": {"Algorithms": 4, "Tools": 41},
            }
        ]
        assert result["summary"]["shifts"] == 6
    finally:
        repo_a.cleanup()
        repo_b.cleanup()


@pytest.mark.skipif(
    not (_has_tag("v0.1.0") and _has_tag("v0.1.1")),
    reason="requires the v0.1.0 and v0.1.1 tags",
)
def test_default_threshold_treats_algorithms_tools_move_as_stable():
    """Pins the tuning decision behind the min_entities=8 default.

    At the default threshold, the same Algorithms/Tools refactor between
    v0.1.0 and v0.1.1 no longer reports a split or a merge -- both
    components read as stable, with the entity movement still visible as a
    responsibility shift (shifts=6, same as at the lower threshold: no
    information is lost, only recategorised). This test fails if someone
    lowers the default without re-checking this datapoint.
    """
    repo_a = ingest(str(REPO_ROOT), language="python", ref="v0.1.0")
    repo_b = ingest(str(REPO_ROOT), language="python", ref="v0.1.1")
    try:
        graph_a = parse(str(repo_a.path), language="python")
        graph_b = parse(str(repo_b.path), language="python")
        arch_a = recover(graph_a, algorithm="pkg")
        arch_b = recover(graph_b, algorithm="pkg")

        result = changelog_architecture(
            arch_a, graph_a, arch_b, graph_b, ref_a="v0.1.0", ref_b="v0.1.1"
        )

        components = result["components"]
        assert components["split"] == []
        assert components["merged"] == []
        assert "Algorithms" in components["stable"]
        assert "Tools" in components["stable"]
        assert result["summary"]["shifts"] == 6
    finally:
        repo_a.cleanup()
        repo_b.cleanup()
