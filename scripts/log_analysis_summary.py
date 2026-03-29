#!/usr/bin/env python3
"""Display arcade-agent analysis results inline in CI logs.

Usage:
    python scripts/log_analysis_summary.py results.json
"""

import json
import os
import sys
from pathlib import Path


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


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: log_analysis_summary.py <results.json>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    r = json.loads(path.read_text())

    metrics = r.get("metrics", {})
    smells = r.get("smells", [])
    components = r.get("components", [])
    rci = metrics.get("RCI", 0.0)
    turbo_mq = metrics.get("TurboMQ", 0.0)

    width = 62
    border = "─" * width

    print(f"\n┌{border}┐")
    print(f"│{'🏛️  ARCADE AGENT — ARCHITECTURE ANALYSIS RESULTS':^{width}}│")
    print(f"├{border}┤")

    # Overview
    print(f"│{'':2}{'📦 Components':20} {r.get('num_components', '?'):<10}{'':29}│")
    print(f"│{'':2}{'🧩 Entities':20} {r.get('num_entities', '?'):<10}{'':29}│")
    print(f"│{'':2}{'🔗 Edges':20} {r.get('num_edges', '?'):<10}{'':29}│")
    print(f"├{border}┤")

    # Metrics
    print(f"│{'📊 QUALITY METRICS':^{width}}│")
    print(f"├{border}┤")
    icon = _rci_icon(rci)
    label = _quality_label(rci)
    print(f"│{'':2}RCI (Cohesive Interactions) {icon} {rci:.4f}  [{label}]{'':14}│")
    print(f"│{'':2}TurboMQ (Modularization)      {turbo_mq:.4f}{'':25}│")
    for name, val in metrics.items():
        if name not in ("RCI", "TurboMQ"):
            print(f"│{'':2}{name:<28} {val:.4f}{'':25}│")
    print(f"├{border}┤")

    # Components
    print(f"│{'🏗️  COMPONENTS':^{width}}│")
    print(f"├{border}┤")
    for comp in sorted(components, key=lambda c: -(c.get("num_entities") or len(c.get("entities", [])))):
        count = comp.get("num_entities") or len(comp.get("entities", []))
        bar = "█" * min(count // 3, 20)
        line = f"  {comp['name']:<22} {count:>3} entities  {bar}"
        print(f"│{line:<{width}}│")
    print(f"├{border}┤")

    # Smells
    print(f"│{'🚨 ARCHITECTURAL SMELLS':^{width}}│")
    print(f"├{border}┤")
    if smells:
        for s in smells:
            icon = _severity_icon(s.get("severity", ""))
            stype = s.get("smell_type", "Unknown")
            comps = ", ".join(s.get("affected_components", []))
            line = f"  {icon} [{s.get('severity','?'):^6}] {stype}: {comps}"
            print(f"│{line:<{width}}│")
    else:
        print(f"│{'  ✅ No architectural smells detected':<{width}}│")

    print(f"└{border}┘")

    # GitHub Actions step summary (if available)
    summary_file = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    if summary_file != Path("/dev/null"):
        try:
            _write_step_summary(summary_file, r, rci, turbo_mq, smells, components, metrics)
        except Exception as exc:
            print(f"[warn] Could not write step summary: {exc}")


def _write_step_summary(
    path: Path,
    r: dict,
    rci: float,
    turbo_mq: float,
    smells: list,
    components: list,
    metrics: dict,
) -> None:
    icon = _rci_icon(rci)
    label = _quality_label(rci)
    lines = [
        "## 🏛️ Architecture Analysis Results\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| 📦 Components | {r.get('num_components')} |",
        f"| 🧩 Entities | {r.get('num_entities')} |",
        f"| 🔗 Edges | {r.get('num_edges')} |",
        f"| RCI {icon} | {rci:.4f} ({label}) |",
        f"| TurboMQ | {turbo_mq:.4f} |",
    ]
    for name, val in metrics.items():
        if name not in ("RCI", "TurboMQ"):
            lines.append(f"| {name} | {val:.4f} |")

    lines.append("\n### 🏗️ Components\n")
    lines.append("| Component | Entities |")
    lines.append("|-----------|----------|")
    for comp in sorted(components, key=lambda c: -(c.get("num_entities") or len(c.get("entities", [])))):
        count = comp.get("num_entities") or len(comp.get("entities", []))
        lines.append(f"| {comp['name']} | {count} |")

    lines.append("\n### 🚨 Architectural Smells\n")
    if smells:
        lines.append("| Severity | Type | Affected |")
        lines.append("|----------|------|----------|")
        for s in smells:
            si = _severity_icon(s.get("severity", ""))
            stype = s.get("smell_type", "Unknown")
            comps = ", ".join(s.get("affected_components", []))
            lines.append(f"| {si} {s.get('severity','?')} | {stype} | {comps} |")
    else:
        lines.append("✅ No architectural smells detected.")

    with path.open("a") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
