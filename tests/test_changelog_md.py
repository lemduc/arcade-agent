"""Tests for architectural changelog markdown rendering."""

from typing import Any

from arcade_agent.exporters.changelog_md import render_changelog_markdown


def _changelog(**overrides: Any) -> dict[str, Any]:
    base = {
        "refs": {"a": "v1", "b": "v2"},
        "components": {"added": [], "removed": [], "renamed": [],
                       "split": [], "merged": [], "stable": ["core"]},
        "responsibility_shifts": [],
        "smells": {"new": [], "resolved": [], "persisting": []},
        "metrics": {},
        "languages": {"a": ["python"], "b": ["python"]},
        "summary": {"components_a": 1, "components_b": 1, "shifts": 0,
                    "entities_a": 3, "entities_b": 3, "entities_added": 0,
                    "entities_deleted": 0, "smells_new": 0, "smells_resolved": 0},
    }
    base.update(overrides)
    return base


def test_no_changes_renders_a_single_line() -> None:
    out = render_changelog_markdown(_changelog())
    assert "No architectural changes" in out
    assert "### Split" not in out


def test_header_includes_refs() -> None:
    out = render_changelog_markdown(_changelog())
    assert "v1" in out and "v2" in out


def test_split_is_rendered() -> None:
    out = render_changelog_markdown(_changelog(components={
        "added": [], "removed": [], "renamed": [], "stable": [], "merged": [],
        "split": [{"from": "auth", "into": ["auth", "authz"],
                   "entities": {"auth": 3, "authz": 3}}],
    }))
    assert "auth" in out and "authz" in out
    assert "split" in out.lower()


def test_new_smell_is_rendered() -> None:
    out = render_changelog_markdown(_changelog(smells={
        "new": [{"smell_type": "BDC", "severity": "high",
                 "affected_components": ["core"], "description": "cycle"}],
        "resolved": [], "persisting": [],
    }))
    assert "BDC" in out


def test_metric_delta_is_rendered_with_sign() -> None:
    out = render_changelog_markdown(_changelog(
        metrics={"RCI": {"a": 0.30, "b": 0.44, "delta": 0.14}}
    ))
    assert "RCI" in out
    assert "+0.14" in out


def test_language_drift_is_surfaced() -> None:
    out = render_changelog_markdown(_changelog(
        languages={"a": ["python"], "b": ["python", "kotlin"]}
    ))
    assert "kotlin" in out


def test_output_is_deterministic() -> None:
    changelog = _changelog()
    assert render_changelog_markdown(changelog) == render_changelog_markdown(changelog)
