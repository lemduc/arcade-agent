#!/usr/bin/env python3
"""Run arcade-agent self-analysis and save results as JSON + HTML.

Usage:
    python scripts/run_self_analysis.py [--output-json results.json] [--output-html report.html]
"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

# Ensure arcade_agent is importable from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover
from arcade_agent.tools.visualize import visualize


def _smell_to_dict(smell: SmellInstance) -> dict:
    """Serialize a SmellInstance to a plain dict."""
    d = asdict(smell)
    # SmellType enum → string
    if hasattr(d.get("smell_type"), "value"):
        d["smell_type"] = d["smell_type"].value
    elif not isinstance(d.get("smell_type"), str):
        d["smell_type"] = str(d["smell_type"])
    return d


def _filter_non_architectural_entities(graph: DependencyGraph) -> DependencyGraph:
    """Remove low-signal helper entities from self-analysis.

    The repository self-analysis is meant to approximate architectural units, not
    every internal helper. Private Python top-level helper functions inflate
    component size and smell counts without representing stable architectural
    responsibilities, so exclude them from the self-analysis graph only.
    """
    kept_entities = {
        fqn: entity
        for fqn, entity in graph.entities.items()
        if not (
            entity.language == "python"
            and entity.kind == "function"
            and entity.name.startswith("_")
        )
    }

    kept_edges = [
        edge
        for edge in graph.edges
        if edge.source in kept_entities and edge.target in kept_entities
    ]

    kept_packages: dict[str, list[str]] = {}
    for pkg, fqns in graph.packages.items():
        filtered_fqns = [fqn for fqn in fqns if fqn in kept_entities]
        if filtered_fqns:
            kept_packages[pkg] = filtered_fqns

    return DependencyGraph(
        entities=kept_entities,
        edges=kept_edges,
        packages=kept_packages,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Self-analysis of arcade-agent codebase")
    parser.add_argument(
        "--output-json",
        default="arcade_analysis_results.json",
        help="Path to save JSON results",
    )
    parser.add_argument(
        "--output-html",
        default="arcade_analysis_report.html",
        help="Path to save HTML report",
    )
    parser.add_argument(
        "--algorithm",
        default="pkg",
        help="Architecture recovery algorithm (pkg, wca, acdc)",
    )
    parser.add_argument(
        "--num-clusters",
        type=int,
        default=None,
        help="Target cluster count for clustering algorithms such as wca.",
    )
    args = parser.parse_args()

    source = str(Path(__file__).parent.parent)

    print(f"[1/5] Ingesting {source}...")
    repo = ingest(source, language="python")
    print(f"  Found {len(repo.source_files)} source files")

    if not repo.source_files:
        print("  No source files found. Exiting.")
        sys.exit(1)

    print("[2/5] Parsing dependencies...")
    graph = parse(
        str(repo.path),
        language=repo.language,
        files=[str(f) for f in repo.source_files],
    )
    graph = _filter_non_architectural_entities(graph)
    print(f"  {graph.num_entities} entities, {graph.num_edges} edges")

    print(f"[3/5] Recovering architecture ({args.algorithm})...")
    arch = recover(graph, algorithm=args.algorithm, num_clusters=args.num_clusters)
    print(f"  {len(arch.components)} components recovered")

    print("[4/5] Detecting smells and computing metrics...")
    smells = detect_smells(arch, graph)
    metrics = compute_metrics(arch, graph)

    print("[5/5] Saving results...")
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "ref": os.environ.get("GITHUB_REF", "local"),
        "algorithm": args.algorithm,
        "num_components": len(arch.components),
        "num_entities": graph.num_entities,
        "num_edges": graph.num_edges,
        "components": [
            {
                "name": c.name,
                "responsibility": c.responsibility,
                "num_entities": len(c.entities),
                "entities": c.entities,
            }
            for c in arch.components
        ],
        "metrics": {m.name: round(m.value, 4) for m in metrics},
        "smells": [_smell_to_dict(s) for s in smells],
    }

    output_json = Path(args.output_json)
    output_json.write_text(json.dumps(results, indent=2, default=str))
    print(f"  JSON results → {output_json}")

    html_out = visualize(
        repo.name,
        repo.version,
        graph,
        arch,
        smells,
        metrics,
        output=args.output_html,
    )
    print(f"  HTML report  → {html_out}")
    print("Done.")


if __name__ == "__main__":
    main()
