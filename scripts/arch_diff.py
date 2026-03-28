#!/usr/bin/env python3
"""Architecture drift detection script.

Parses a codebase, recovers architecture using PKG, compares against a stored
baseline, and prints a markdown report suitable for a PR comment.

Usage:
    python scripts/arch_diff.py --source /path/to/project --language java
    python scripts/arch_diff.py --source . --update-baseline
"""

import argparse
import sys
from pathlib import Path

from arcade_agent.serialization import load_architecture, save_architecture
from arcade_agent.tools.compare import compare
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover


def build_report(
    current,
    graph,
    metrics,
    smells,
    drift=None,
    baseline=None,
) -> str:
    """Build a markdown drift report.

    Args:
        current: The current Architecture.
        graph: The current DependencyGraph.
        metrics: List of MetricResult for the current architecture.
        smells: List of SmellInstance detected.
        drift: Optional compare() result dict (if baseline exists).
        baseline: Optional baseline Architecture.

    Returns:
        Markdown string.
    """
    num_entities = graph.num_entities
    num_components = len(current.components)

    lines = [
        "## Architecture Drift Report",
        "",
        f"**Algorithm:** {current.algorithm.upper()} | "
        f"**Entities:** {num_entities} | "
        f"**Components:** {num_components}",
        "",
    ]

    # Drift table (only when baseline exists)
    if drift and baseline:
        similarity = drift["overall_similarity"]
        summary = drift["summary"]
        baseline_components = summary["arch_a_components"]

        # Build metric lookup for current and baseline delta
        metric_map = {m.name: m.value for m in metrics}

        lines.append("### Drift from Baseline")
        lines.append("")
        lines.append("| Metric | Baseline | Current | Delta |")
        lines.append("|--------|----------|---------|-------|")
        lines.append(
            f"| Components | {baseline_components} | {num_components} | "
            f"{_delta(num_components - baseline_components)} |"
        )
        lines.append(
            f"| Similarity | — | {similarity:.2f} | — |"
        )

        for name in ("RCI", "TurboMQ"):
            val = metric_map.get(name)
            if val is not None:
                lines.append(
                    f"| {name} | — | {val:.2f} | — |"
                )

        lines.append("")

        # Changes summary
        lines.append("### Changes")
        lines.append("")
        if summary["components_added"]:
            added_names = [
                m["target"]
                for m in drift["matches"]
                if not m["source"]
            ]
            lines.append(
                f"- {summary['components_added']} component(s) added: "
                f"`{'`, `'.join(added_names)}`"
            )
        if summary["components_removed"]:
            removed_names = [
                m["source"]
                for m in drift["matches"]
                if not m["target"]
            ]
            lines.append(
                f"- {summary['components_removed']} component(s) removed: "
                f"`{'`, `'.join(removed_names)}`"
            )

        # Count entity movements
        entities_moved = sum(
            len(m.get("entities_added", [])) + len(m.get("entities_removed", []))
            for m in drift["matches"]
            if m["source"] and m["target"]
        )
        if entities_moved:
            lines.append(f"- {entities_moved} entity movement(s) between components")

        if summary["possible_merges"]:
            lines.append(
                f"- {summary['possible_merges']} possible merge(s) detected"
            )
        if summary["possible_splits"]:
            lines.append(
                f"- {summary['possible_splits']} possible split(s) detected"
            )

        if not any([
            summary["components_added"],
            summary["components_removed"],
            entities_moved,
            summary["possible_merges"],
            summary["possible_splits"],
        ]):
            lines.append("- No structural changes detected")

        lines.append("")

    # Smells section
    if smells:
        lines.append(f"### Smells ({len(smells)})")
        lines.append("")
        for smell in smells:
            affected = ", ".join(smell.affected_components) if smell.affected_components else ""
            lines.append(f"- {smell.smell_type}: {affected}")
        lines.append("")
    else:
        lines.append("### Smells")
        lines.append("")
        lines.append("No architectural smells detected.")
        lines.append("")

    # Metrics table (when no baseline — still useful)
    if not drift:
        lines.append("### Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for m in metrics:
            lines.append(f"| {m.name} | {m.value:.2f} |")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(
        "*Generated by [arcade-agent](https://github.com/lemduc/arcade-agent)*"
    )
    lines.append("<!-- arcade-agent-drift-report -->")

    return "\n".join(lines)


def _delta(val: int | float) -> str:
    """Format a delta value with sign."""
    if isinstance(val, float):
        return f"+{val:.2f}" if val >= 0 else f"{val:.2f}"
    return f"+{val}" if val >= 0 else str(val)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Detect architecture drift against a stored baseline."
    )
    parser.add_argument(
        "--source",
        default=".",
        help="Path to the source code (default: current directory)",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Language to parse (auto-detect if omitted)",
    )
    parser.add_argument(
        "--baseline",
        default=".arcade/baseline.json",
        help="Path to baseline JSON (default: .arcade/baseline.json)",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Overwrite the baseline with the current architecture",
    )
    args = parser.parse_args(argv)

    source_path = Path(args.source).resolve()
    baseline_path = Path(args.baseline)

    # 1. Parse
    graph = parse(str(source_path), language=args.language)

    # 2. Recover
    current = recover(graph, algorithm="pkg")

    # 3. Load baseline and compare (if it exists)
    drift = None
    baseline = None
    if baseline_path.exists():
        baseline = load_architecture(baseline_path)
        drift = compare(baseline, current)

    # 4. Metrics and smells
    metrics = compute_metrics(current, graph)
    smells = detect_smells(current, graph)

    # 5. Update baseline if requested
    if args.update_baseline:
        save_architecture(current, baseline_path)
        print(f"Baseline updated: {baseline_path}", file=sys.stderr)

    # 6. Print report
    report = build_report(current, graph, metrics, smells, drift, baseline)
    print(report)


if __name__ == "__main__":
    main()
