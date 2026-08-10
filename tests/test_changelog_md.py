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
    assert "`auth` split — kept 3, moved 3 to `authz`" in out


def test_split_without_kept_omits_kept_clause() -> None:
    out = render_changelog_markdown(_changelog(components={
        "added": [], "removed": [], "renamed": [], "stable": [], "merged": [],
        "split": [{"from": "auth", "into": ["authz", "session"],
                   "entities": {"authz": 9, "session": 5}}],
    }))
    assert "`auth` split — moved 9 to `authz`, 5 to `session`" in out
    assert "kept" not in out


def test_merged_is_rendered() -> None:
    out = render_changelog_markdown(_changelog(components={
        "added": [], "removed": [], "renamed": [], "stable": [], "split": [],
        "merged": [{"into": "core", "from": ["core", "util"],
                    "entities": {"core": 31, "util": 6}}],
    }))
    assert "### Merged" in out
    assert "`core` absorbed 6 from `util` (kept 31 of its own)" in out


def test_merged_multi_source_without_kept() -> None:
    out = render_changelog_markdown(_changelog(components={
        "added": [], "removed": [], "renamed": [], "stable": [], "split": [],
        "merged": [{"into": "core", "from": ["util", "legacy"],
                    "entities": {"util": 6, "legacy": 3}}],
    }))
    assert "`core` absorbed 6 from `util`, 3 from `legacy`" in out
    assert "kept" not in out


def test_components_added_removed_renamed_are_rendered() -> None:
    out = render_changelog_markdown(_changelog(components={
        "added": ["parsers.kotlin"], "removed": ["legacy_io"],
        "renamed": [{"from": "util", "to": "common"}],
        "stable": [], "split": [], "merged": [],
    }))
    assert "### Component changes" in out
    assert "- added `parsers.kotlin`" in out
    assert "- removed `legacy_io`" in out
    assert "- renamed `util` → `common`" in out


def test_rewritten_component_is_rendered_instead_of_added_plus_removed() -> None:
    out = render_changelog_markdown(_changelog(components={
        "added": [], "removed": [], "renamed": [],
        "stable": [], "split": [], "merged": [],
        "rewritten": [{"name": "PkgAuth", "before": 12, "after": 12, "retained": 0}],
    }))
    assert "### Component changes" in out
    assert "- rewritten `PkgAuth` — 12 → 12 entities, none in common" in out
    assert "- added `PkgAuth`" not in out
    assert "- removed `PkgAuth`" not in out


def test_rewritten_component_reports_retained_entities() -> None:
    out = render_changelog_markdown(_changelog(components={
        "added": [], "removed": [], "renamed": [],
        "stable": [], "split": [], "merged": [],
        "rewritten": [{"name": "PkgAuth", "before": 12, "after": 9, "retained": 1}],
    }))
    assert "- rewritten `PkgAuth` — 12 → 9 entities, 1 in common" in out


def test_payload_without_a_rewritten_key_still_renders() -> None:
    # `components` payloads persisted before rewrites existed have no
    # "rewritten" key; rendering one must not raise.
    out = render_changelog_markdown(_changelog(components={
        "added": ["parsers.kotlin"], "removed": [], "renamed": [],
        "stable": [], "split": [], "merged": [],
    }))
    assert "- added `parsers.kotlin`" in out


def test_responsibility_shifts_are_rendered() -> None:
    out = render_changelog_markdown(_changelog(
        responsibility_shifts=[{"entity": "a.b.C", "from": "auth", "to": "api"}]
    ))
    assert "### Responsibility shifts (1)" in out
    assert "- `a.b.C`: `auth` → `api`" in out


def test_responsibility_shifts_truncate_at_twenty() -> None:
    shifts = [
        {"entity": f"a.b.E{i}", "from": "auth", "to": "api"} for i in range(25)
    ]
    out = render_changelog_markdown(_changelog(responsibility_shifts=shifts))
    assert "### Responsibility shifts (25)" in out
    for i in range(20):
        assert f"a.b.E{i}" in out
    for i in range(20, 25):
        assert f"a.b.E{i}" not in out
    assert "- …and 5 more" in out


def test_new_smell_is_rendered() -> None:
    out = render_changelog_markdown(_changelog(smells={
        "new": [{"smell_type": "BDC", "severity": "high",
                 "affected_components": ["core"], "description": "cycle"}],
        "resolved": [], "persisting": [],
    }))
    assert "BDC" in out


def test_new_smell_is_rendered_by_default() -> None:
    changelog = _changelog(smells={
        "new": [{"smell_type": "BDC", "severity": "high",
                 "affected_components": ["core"], "description": "cycle"}],
        "resolved": [], "persisting": [],
    })
    out = render_changelog_markdown(changelog)
    assert "### Smells" in out
    assert "BDC" in out


def test_include_smells_false_omits_the_smells_section() -> None:
    changelog = _changelog(smells={
        "new": [{"smell_type": "BDC", "severity": "high",
                 "affected_components": ["core"], "description": "cycle"}],
        "resolved": [], "persisting": [],
    })
    out = render_changelog_markdown(changelog, include_smells=False)
    assert "### Smells" not in out
    assert "BDC" not in out


def test_include_metrics_false_omits_the_metrics_section() -> None:
    """arch_diff prints its own metric table; the changelog must not duplicate it."""
    changelog = _changelog(
        metrics={"RCI": {"a": 0.30, "b": 0.44, "delta": 0.14}}
    )
    out = render_changelog_markdown(changelog, include_metrics=False)
    assert "### Metrics" not in out
    assert "RCI" not in out


def test_metrics_are_included_by_default() -> None:
    changelog = _changelog(
        metrics={"RCI": {"a": 0.30, "b": 0.44, "delta": 0.14}}
    )
    out = render_changelog_markdown(changelog)
    assert "### Metrics" in out
    assert "RCI" in out


def test_metric_delta_is_rendered_with_sign() -> None:
    out = render_changelog_markdown(_changelog(
        metrics={"RCI": {"a": 0.30, "b": 0.44, "delta": 0.14}}
    ))
    assert "RCI" in out
    assert "+0.14" in out


def test_metric_row_with_none_before_renders_em_dash() -> None:
    out = render_changelog_markdown(_changelog(
        metrics={"NewMetric": {"a": None, "b": 0.44, "delta": 0.44}}
    ))
    assert "| NewMetric | — | 0.44 | +0.44 |" in out


def test_metric_row_with_none_after_renders_em_dash() -> None:
    out = render_changelog_markdown(_changelog(
        metrics={"RetiredMetric": {"a": 0.44, "b": None, "delta": -0.44}}
    ))
    assert "| RetiredMetric | 0.44 | — | -0.44 |" in out


def test_language_drift_is_surfaced() -> None:
    out = render_changelog_markdown(_changelog(
        languages={"a": ["python"], "b": ["python", "kotlin"]}
    ))
    assert "kotlin" in out


def test_language_drift_with_multiple_languages_per_side_has_semicolon_boundary() -> None:
    out = render_changelog_markdown(_changelog(
        languages={"a": ["python", "java"], "b": ["python", "kotlin"]}
    ))
    assert "`v1`: `python`, `java`; `v2`: `python`, `kotlin`" in out


def test_output_is_deterministic() -> None:
    changelog = _changelog()
    assert render_changelog_markdown(changelog) == render_changelog_markdown(changelog)


def test_default_heading_level_is_h2() -> None:
    out = render_changelog_markdown(_changelog())
    assert out.startswith("## Architectural changes")
    assert "\n### " not in out


def test_heading_level_three_shifts_own_and_subsection_headings() -> None:
    out = render_changelog_markdown(
        _changelog(components={
            "added": [], "removed": [], "renamed": [], "stable": [], "merged": [],
            "split": [{"from": "auth", "into": ["auth", "authz"],
                       "entities": {"auth": 3, "authz": 3}}],
        }),
        heading_level=3,
    )
    assert out.startswith("### Architectural changes")
    assert "\n#### Split" in out
    assert "\n### Split" not in out
    assert "\n## " not in out
