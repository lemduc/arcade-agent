"""Render an architectural changelog as markdown."""

from typing import Any


def _fmt_delta(delta: float | None) -> str:
    """Format a metric delta with an explicit sign.

    Args:
        delta: The metric's delta value, or None if unavailable.

    Returns:
        A signed, two-decimal string (e.g. "+0.14"), or an em dash if delta
        is None.
    """
    if delta is None:
        return "—"
    return f"{delta:+.2f}"


def render_changelog_markdown(changelog: dict[str, Any]) -> str:
    """Render a changelog_architecture result as markdown.

    Empty sections are omitted. A changelog with no structural changes, smell
    changes or metric movement renders a single explanatory line.

    Args:
        changelog: The dict returned by changelog_architecture.

    Returns:
        A markdown string suitable for a pull-request comment.
    """
    refs = changelog.get("refs") or {}
    ref_a = refs.get("a") or "baseline"
    ref_b = refs.get("b") or "current"

    lines = [f"## Architectural changes — `{ref_a}` → `{ref_b}`", ""]

    components = changelog["components"]
    smells = changelog["smells"]
    metrics = changelog["metrics"]
    shifts = changelog["responsibility_shifts"]

    body: list[str] = []

    if components["split"]:
        body.append("### Split")
        body.append("")
        for entry in components["split"]:
            source = entry["from"]
            entities = entry["entities"]
            kept = entities.get(source)
            moved_parts = [
                f"{entities[t]} to `{t}`" for t in entry["into"] if t != source
            ]
            segments = []
            if kept is not None:
                segments.append(f"kept {kept}")
            if moved_parts:
                segments.append(f"moved {', '.join(moved_parts)}")
            body.append(f"- `{source}` split — {', '.join(segments)}")
        body.append("")

    if components["merged"]:
        body.append("### Merged")
        body.append("")
        for entry in components["merged"]:
            target = entry["into"]
            entities = entry["entities"]
            kept = entities.get(target)
            absorbed_parts = [
                f"{entities[s]} from `{s}`" for s in entry["from"] if s != target
            ]
            line = f"- `{target}` absorbed {', '.join(absorbed_parts)}"
            if kept is not None:
                line += f" (kept {kept} of its own)"
            body.append(line)
        body.append("")

    if components["added"] or components["removed"] or components["renamed"]:
        body.append("### Components")
        body.append("")
        for name in components["added"]:
            body.append(f"- added `{name}`")
        for name in components["removed"]:
            body.append(f"- removed `{name}`")
        for entry in components["renamed"]:
            body.append(f"- renamed `{entry['from']}` → `{entry['to']}`")
        body.append("")

    if shifts:
        body.append(f"### Responsibility shifts ({len(shifts)})")
        body.append("")
        for shift in shifts[:20]:
            body.append(
                f"- `{shift['entity']}`: `{shift['from']}` → `{shift['to']}`"
            )
        if len(shifts) > 20:
            body.append(f"- …and {len(shifts) - 20} more")
        body.append("")

    if smells["new"] or smells["resolved"]:
        body.append("### Smells")
        body.append("")
        for smell in smells["new"]:
            comps = ", ".join(f"`{c}`" for c in smell["affected_components"])
            body.append(f"- **new** {smell['smell_type']} ({smell['severity']}) — {comps}")
        for smell in smells["resolved"]:
            comps = ", ".join(f"`{c}`" for c in smell["affected_components"])
            body.append(f"- resolved {smell['smell_type']} — {comps}")
        body.append("")

    moved_metrics = {
        name: entry
        for name, entry in metrics.items()
        if entry.get("delta") not in (None, 0)
    }
    if moved_metrics:
        body.append("### Metrics")
        body.append("")
        body.append("| Metric | Before | After | Delta |")
        body.append("|--------|--------|-------|-------|")
        for name, entry in moved_metrics.items():
            before = "—" if entry["a"] is None else f"{entry['a']:.2f}"
            after = "—" if entry["b"] is None else f"{entry['b']:.2f}"
            body.append(f"| {name} | {before} | {after} | {_fmt_delta(entry['delta'])} |")
        body.append("")

    languages = changelog.get("languages") or {}
    lang_a = languages.get("a")
    lang_b = languages.get("b")
    if lang_a != lang_b:
        a_str = ", ".join(f"`{lang}`" for lang in (lang_a or [])) or "(none)"
        b_str = ", ".join(f"`{lang}`" for lang in (lang_b or [])) or "(none)"
        body.append(
            f"> **Language set changed** — `{ref_a}`: {a_str}; "
            f"`{ref_b}`: {b_str}. Comparisons across different "
            f"language sets are not like-for-like."
        )
        body.append("")

    if not body:
        body = ["No architectural changes.", ""]

    return "\n".join(lines + body).rstrip() + "\n"
