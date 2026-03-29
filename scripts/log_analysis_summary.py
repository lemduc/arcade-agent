#!/usr/bin/env python3
"""Display arcade-agent analysis results inline in CI logs.

Usage:
    python scripts/log_analysis_summary.py results.json
"""

import json
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


def _component_count(component: dict) -> int:
    return component.get("num_entities") or len(component.get("entities", []))


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
    print(f"│{'':2}{'🏷️ Classes':20} {r.get('class_count', 0):<10}{'':29}│")
    print(f"│{'':2}{'ƒ Functions':20} {r.get('function_count', 0):<10}{'':29}│")
    print(f"│{'':2}{'🔧 Methods':20} {r.get('method_count', 0):<10}{'':29}│")
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
    for comp in sorted(components, key=lambda c: (-_component_count(c), c["name"])):
        count = _component_count(comp)
        bar = "█" * min(count // 3, 20)
        line = (
            f"  {comp['name']:<18} {count:>3} ent  "
            f"{comp.get('class_count', 0):>2} cls  {comp.get('method_count', 0):>2} mth  {bar}"
        )
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

if __name__ == "__main__":
    main()
