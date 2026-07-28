"""End-to-end changelog over arcade-agent's own history."""

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

        # Known figures for these two tags.
        assert result["summary"]["entities_a"] > 0
        assert result["summary"]["entities_b"] > result["summary"]["entities_a"]
        assert result["refs"] == {"a": "v0.1.1", "b": "v0.2.0"}

        # The six top-level buckets classify every arch_b component exactly once.
        # Split.targets / Merge.sources are provenance detail and may name a
        # component classified elsewhere, so they are excluded from this check.
        components = result["components"]
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
