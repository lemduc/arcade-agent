#!/usr/bin/env python3
"""Compare current analysis results against a baseline and output Markdown.

Uses arcade-agent's compare tool (A2A analysis with Hungarian algorithm) for
proper architecture-to-architecture comparison when entity data is available.

Usage:
    python scripts/compare_baseline.py current.json baseline.json [--output comment.md]

Exits with code 0 always (comparison is informational, not a pass/fail gate).
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure arcade_agent is importable from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.tools.compare import compare


def _delta(new: float, old: float) -> str:
    diff = new - old
    if abs(diff) < 0.0001:
        return "→ (no change)"
    arrow = "↑" if diff > 0 else "↓"
    return f"{arrow} ({diff:+.4f})"


def _severity_icon(severity: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity.lower(), "⚪")


def _rci_icon(rci: float) -> str:
    if rci >= 0.8:
        return "🟢"
    if rci >= 0.6:
        return "🟡"
    return "🔴"


def _quality_label(rci: float) -> str:
    if rci >= 0.8:
        return "Good"
    if rci >= 0.6:
        return "Fair"
    return "Poor"


def _reconstruct_architecture(data: dict) -> Architecture | None:
    """Reconstruct an Architecture object from stored JSON data."""
    components_data = data.get("components", [])
    if not components_data or "entities" not in components_data[0]:
        return None
    components = [
        Component(
            name=c["name"],
            responsibility=c.get("responsibility", ""),
            entities=c.get("entities", []),
        )
        for c in components_data
    ]
    return Architecture(components=components, algorithm=data.get("algorithm", ""))


def _run_a2a_comparison(baseline: dict, current: dict) -> dict | None:
    """Run A2A comparison using arcade-agent's compare tool."""
    arch_a = _reconstruct_architecture(baseline)
    arch_b = _reconstruct_architecture(current)
    if arch_a is None or arch_b is None:
        return None
    return compare(arch_a, arch_b)


def build_comment(current: dict, baseline: dict | None, run_url: str = "") -> str:
    """Build a Markdown PR comment body."""
    lines: list[str] = []

    cur_metrics = current.get("metrics", {})
    cur_smells = current.get("smells", [])
    cur_components = current.get("components", [])
    cur_rci = cur_metrics.get("RCI", 0.0)
    cur_tmq = cur_metrics.get("TurboMQ", 0.0)

    rci_icon = _rci_icon(cur_rci)
    quality_label = _quality_label(cur_rci)

    lines.append("## 🤖 Architecture Analysis Summary\n")
    lines.append(
        "_Powered by [arcade-agent](https://github.com/tuannx/arcade-agent) — "
        "automatic architectural self-analysis_\n"
    )
    lines.append("---\n")

    # -- Current state -----------------------------------------------------------
    lines.append("### 🏛️ Current Architecture\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| 📦 Components | **{current.get('num_components')}** |")
    lines.append(f"| 🧩 Entities | **{current.get('num_entities')}** |")
    lines.append(f"| 🔗 Edges | **{current.get('num_edges')}** |")
    lines.append(f"| RCI {rci_icon} | **{cur_rci:.4f}** ({quality_label}) |")
    lines.append(f"| TurboMQ | **{cur_tmq:.4f}** |")
    for name, val in cur_metrics.items():
        if name not in ("RCI", "TurboMQ"):
            lines.append(f"| {name} | {val:.4f} |")
    lines.append("")

    # -- Components --------------------------------------------------------------
    if cur_components:
        lines.append("<details><summary>🏗️ Components breakdown</summary>\n")
        lines.append("| Component | Entities |")
        lines.append("|-----------|----------|")
        for comp in sorted(cur_components, key=lambda c: -(c.get("num_entities") or len(c.get("entities", [])))):
            count = comp.get("num_entities") or len(comp.get("entities", []))
            lines.append(f"| {comp['name']} | {count} |")
        lines.append("</details>\n")

    # -- Smells ------------------------------------------------------------------
    lines.append("### 🚨 Architectural Smells\n")
    if cur_smells:
        lines.append("| Severity | Type | Affected Components |")
        lines.append("|----------|------|---------------------|")
        for s in cur_smells:
            si = _severity_icon(s.get("severity", ""))
            stype = s.get("smell_type", "Unknown")
            comps = ", ".join(s.get("affected_components", []))
            lines.append(f"| {si} {s.get('severity','?')} | {stype} | {comps} |")
    else:
        lines.append("✅ No architectural smells detected.")
    lines.append("")

    # -- Evolution (before/after) ------------------------------------------------
    if baseline:
        bl_metrics = baseline.get("metrics", {})
        bl_rci = bl_metrics.get("RCI", 0.0)
        bl_tmq = bl_metrics.get("TurboMQ", 0.0)
        bl_smells = baseline.get("smells", [])
        bl_commit = baseline.get("commit_sha", "unknown")[:7]

        # Run A2A comparison via arcade-agent's compare tool
        a2a_result = _run_a2a_comparison(baseline, current)

        lines.append("### 📈 Evolution vs Baseline\n")
        lines.append(f"_Baseline commit: `{bl_commit}`_\n")

        # A2A similarity section
        if a2a_result:
            summary = a2a_result["summary"]
            lines.append("#### Architecture-to-Architecture (A2A) Comparison\n")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| A2A Similarity | **{a2a_result['overall_similarity']:.4f}** |")
            lines.append(f"| Matched Components | {summary['total_matches']} |")
            lines.append(f"| Components Added | {summary['components_added']} |")
            lines.append(f"| Components Removed | {summary['components_removed']} |")
            if summary.get("possible_splits"):
                lines.append(f"| Possible Splits | {summary['possible_splits']} |")
            if summary.get("possible_merges"):
                lines.append(f"| Possible Merges | {summary['possible_merges']} |")
            lines.append("")

            # Component-level matches detail
            matches = a2a_result.get("matches", [])
            matched = [m for m in matches if m.get("source") and m.get("target")]
            added = [m for m in matches if not m.get("source")]
            removed = [m for m in matches if not m.get("target")]

            if matched or added or removed:
                lines.append("<details><summary>Component matching details</summary>\n")
                if matched:
                    lines.append("**Matched:**")
                    lines.append("| Baseline | Current | Similarity |")
                    lines.append("|----------|---------|------------|")
                    for m in sorted(matched, key=lambda x: -x["similarity"]):
                        lines.append(
                            f"| {m['source']} | {m['target']} | {m['similarity']:.4f} |"
                        )
                    lines.append("")
                if added:
                    lines.append("**New components:** " + ", ".join(
                        f"`{m['target']}`" for m in added
                    ))
                    lines.append("")
                if removed:
                    lines.append("**Removed components:** " + ", ".join(
                        f"`{m['source']}`" for m in removed
                    ))
                    lines.append("")
                lines.append("</details>\n")

        # Metric evolution table
        lines.append("#### Metric Evolution\n")
        lines.append("| Metric | Baseline | Current | Change |")
        lines.append("|--------|----------|---------|--------|")
        lines.append(
            f"| 📦 Components | {baseline.get('num_components')} "
            f"| {current.get('num_components')} "
            f"| {_delta(current.get('num_components', 0), baseline.get('num_components', 0))} |"
        )
        lines.append(
            f"| 🧩 Entities | {baseline.get('num_entities')} "
            f"| {current.get('num_entities')} "
            f"| {_delta(current.get('num_entities', 0), baseline.get('num_entities', 0))} |"
        )
        lines.append(
            f"| 🔗 Edges | {baseline.get('num_edges')} "
            f"| {current.get('num_edges')} "
            f"| {_delta(current.get('num_edges', 0), baseline.get('num_edges', 0))} |"
        )
        lines.append(
            f"| RCI | {bl_rci:.4f} | {cur_rci:.4f} | {_delta(cur_rci, bl_rci)} |"
        )
        lines.append(
            f"| TurboMQ | {bl_tmq:.4f} | {cur_tmq:.4f} | {_delta(cur_tmq, bl_tmq)} |"
        )
        for name in bl_metrics:
            if name not in ("RCI", "TurboMQ"):
                bl_v = bl_metrics.get(name, 0.0)
                cur_v = cur_metrics.get(name, 0.0)
                lines.append(f"| {name} | {bl_v:.4f} | {cur_v:.4f} | {_delta(cur_v, bl_v)} |")
        lines.append("")

        # Smell changes
        cur_smell_types = {s.get("smell_type") for s in cur_smells}
        bl_smell_types = {s.get("smell_type") for s in bl_smells}
        new_smells = cur_smell_types - bl_smell_types
        resolved_smells = bl_smell_types - cur_smell_types

        if new_smells or resolved_smells:
            lines.append("**Smell changes:**")
            for t in new_smells:
                lines.append(f"- 🆕 New smell: `{t}`")
            for t in resolved_smells:
                lines.append(f"- ✅ Resolved: `{t}`")
            lines.append("")

    else:
        lines.append(
            "> ℹ️ No baseline available — this is the first analysis run or the "
            "baseline artifact has expired. The current results will be stored "
            "as the new baseline.\n"
        )

    # -- CI/CD Insights ----------------------------------------------------------
    lines.append("### 💡 CI/CD Insights\n")
    lines.append(f"- **Quality Score**: {rci_icon} {quality_label} (RCI={cur_rci:.4f})")

    if baseline:
        bl_rci = baseline.get("metrics", {}).get("RCI", 0.0)
        rci_trend = cur_rci - bl_rci
        if rci_trend > 0.01:
            trend = "📈 Improving modularity"
        elif rci_trend < -0.01:
            trend = "📉 Declining cohesion — consider reviewing recent refactoring"
        else:
            trend = "➡️ Stable architectural quality"
        lines.append(f"- **Trend**: {trend}")

        # A2A insight
        a2a_result = _run_a2a_comparison(baseline, current)
        if a2a_result:
            sim = a2a_result["overall_similarity"]
            if sim >= 0.9:
                lines.append(f"- **Architecture Stability**: 🟢 High (A2A={sim:.4f})")
            elif sim >= 0.7:
                lines.append(f"- **Architecture Stability**: 🟡 Moderate (A2A={sim:.4f})")
            else:
                lines.append(f"- **Architecture Stability**: 🔴 Low (A2A={sim:.4f}) — significant restructuring detected")

    smell_count = len(cur_smells)
    if smell_count == 0:
        lines.append("- **Smells**: ✅ Clean — no architectural smells")
    elif smell_count <= 2:
        lines.append(f"- **Smells**: ⚠️ {smell_count} smell(s) — review suggested")
    else:
        lines.append(f"- **Smells**: 🔴 {smell_count} smells — refactoring recommended")

    if run_url:
        lines.append(f"\n📄 [View full HTML report in CI artifacts]({run_url})")

    lines.append("\n---")
    lines.append(
        "_This comment is auto-generated by the self-dogfooding CI job. "
        "It updates on every push to this PR._"
    )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare architecture results vs baseline")
    parser.add_argument("current", help="Path to current analysis JSON")
    parser.add_argument("baseline", nargs="?", help="Path to baseline JSON (optional)")
    parser.add_argument(
        "--output",
        default="pr_comment.md",
        help="Output file for the generated Markdown comment",
    )
    parser.add_argument(
        "--run-url",
        default="",
        help="GitHub Actions run URL for artifact linking",
    )
    args = parser.parse_args()

    current_path = Path(args.current)
    if not current_path.exists():
        print(f"Error: current results file not found: {current_path}", file=sys.stderr)
        sys.exit(1)

    current = json.loads(current_path.read_text())
    baseline: dict | None = None

    if args.baseline:
        bl_path = Path(args.baseline)
        if bl_path.exists():
            baseline = json.loads(bl_path.read_text())
            print(f"Loaded baseline from {bl_path}")
        else:
            print(f"Baseline file not found: {bl_path} — running without baseline")

    comment = build_comment(current, baseline, run_url=args.run_url)

    out = Path(args.output)
    out.write_text(comment)
    print(f"PR comment written to {out}")

    # Also print inline summary to CI logs
    print("\n" + "=" * 60)
    print("BEFORE/AFTER COMPARISON SUMMARY")
    print("=" * 60)
    if baseline:
        bl_metrics = baseline.get("metrics", {})
        bl_rci = bl_metrics.get("RCI", 0.0)
        cur_rci = current.get("metrics", {}).get("RCI", 0.0)

        # A2A comparison
        a2a_result = _run_a2a_comparison(baseline, current)
        if a2a_result:
            summary = a2a_result["summary"]
            print(f"  A2A Similarity: {a2a_result['overall_similarity']:.4f}")
            print(
                f"  Components:  {summary['arch_a_components']} → "
                f"{summary['arch_b_components']} "
                f"(+{summary['components_added']} / -{summary['components_removed']})"
            )
            if summary.get("possible_splits"):
                print(f"  Possible Splits: {summary['possible_splits']}")
            if summary.get("possible_merges"):
                print(f"  Possible Merges: {summary['possible_merges']}")
        else:
            print(
                f"  Components:  {baseline.get('num_components')} → "
                f"{current.get('num_components')} "
                f"{_delta(current.get('num_components', 0), baseline.get('num_components', 0))}"
            )

        print(
            f"  Entities:    {baseline.get('num_entities')} → "
            f"{current.get('num_entities')} "
            f"{_delta(current.get('num_entities', 0), baseline.get('num_entities', 0))}"
        )
        print(
            f"  Edges:       {baseline.get('num_edges')} → "
            f"{current.get('num_edges')} "
            f"{_delta(current.get('num_edges', 0), baseline.get('num_edges', 0))}"
        )
        print(
            f"  RCI:         {bl_rci:.4f} → {cur_rci:.4f} {_delta(cur_rci, bl_rci)}"
        )
        print(
            f"  TurboMQ:     {bl_metrics.get('TurboMQ', 0):.4f} → "
            f"{current.get('metrics', {}).get('TurboMQ', 0):.4f} "
            f"{_delta(current.get('metrics', {}).get('TurboMQ', 0), bl_metrics.get('TurboMQ', 0))}"
        )
        cur_smell_count = len(current.get("smells", []))
        bl_smell_count = len(baseline.get("smells", []))
        print(f"  Smells:      {bl_smell_count} → {cur_smell_count}")

    else:
        print("  No baseline available — first run or baseline expired.")
        cur_rci = current.get("metrics", {}).get("RCI", 0.0)
        print(f"  Components:  {current.get('num_components')}")
        print(f"  Entities:    {current.get('num_entities')}")
        print(f"  RCI:         {cur_rci:.4f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
