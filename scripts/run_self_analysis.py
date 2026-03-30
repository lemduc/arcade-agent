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
from arcade_agent.exporters.json import build_component_summary, build_graph_summary
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
    responsibilities, and decorator-registration imports such as ``@tool`` or
    ``@register_parser`` can create misleading coupling across recovered
    components after facade reassignment. Exclude those from the self-analysis
    graph only; the underlying parser output remains unchanged.
    """
    kept_entities = {
        fqn: entity
        for fqn, entity in graph.entities.items()
        if entity.kind != "method"
        and not (
            entity.language == "python"
            and entity.kind == "function"
            and entity.name.startswith("_")
        )
    }

    kept_edges = []
    registration_helpers = {"tool", "register_parser"}
    for edge in graph.edges:
        if edge.source not in kept_entities or edge.target not in kept_entities:
            continue

        source_entity = kept_entities[edge.source]
        target_entity = kept_entities[edge.target]
        if (
            edge.relation == "import"
            and source_entity.package
            and source_entity.package == target_entity.package
            and target_entity.kind == "function"
            and target_entity.name in registration_helpers
        ):
            continue

        kept_edges.append(edge)

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
    parser = argparse.ArgumentParser(description="Run architecture self-analysis on a source tree")
    parser.add_argument(
        "--source",
        default=".",
        help="Path to the source repository or project root",
    )
    parser.add_argument(
        "--language",
        default="",
        help="Optional language override (java, python, typescript, c)",
    )
    parser.add_argument(
        "--repo-name",
        default="",
        help="Optional project name override for reports",
    )
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

    source = str(Path(args.source).resolve())
    language = args.language or None

    print(f"[1/5] Ingesting {source}...")
    repo = ingest(source, language=language)
    print(f"  Found {len(repo.source_files)} source files")

    if not repo.source_files:
        print("  No source files found. Exiting.")
        sys.exit(1)

    print("[2/5] Parsing dependencies...")
    raw_graph = parse(
        str(repo.path),
        language=repo.language or language or "python",
        files=[str(f) for f in repo.source_files],
    )
    graph = _filter_non_architectural_entities(raw_graph)
    print(f"  {graph.num_entities} entities, {graph.num_edges} edges")

    print(f"[3/5] Recovering architecture ({args.algorithm})...")
    arch = recover(graph, algorithm=args.algorithm, num_clusters=args.num_clusters)
    print(f"  {len(arch.components)} components recovered")

    print("[4/5] Detecting smells and computing metrics...")
    smells = detect_smells(arch, graph)
    metrics = compute_metrics(arch, graph)

    print("[5/5] Saving results...")
    source_summary = build_graph_summary(raw_graph)
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_name": args.repo_name or repo.name,
        "language": repo.language or language,
        "commit_sha": os.environ.get("GITHUB_SHA", "local"),
        "ref": os.environ.get("GITHUB_REF", "local"),
        "algorithm": args.algorithm,
        "num_components": len(arch.components),
        "num_entities": graph.num_entities,
        "num_edges": graph.num_edges,
        "source_num_entities": source_summary["num_entities"],
        "class_count": source_summary["class_count"],
        "function_count": source_summary["function_count"],
        "method_count": source_summary["method_count"],
        "entity_kind_counts": source_summary["entity_kind_counts"],
        "component_dependencies": [
            {"source": source, "target": target}
            for source, target in arch.component_dependencies(graph)
        ],
        "components": [
            build_component_summary(c, graph, stats_graph=raw_graph)
            for c in arch.components
        ],
        "metrics": {m.name: round(m.value, 4) for m in metrics},
        "smells": [_smell_to_dict(s) for s in smells],
    }

    output_json = Path(args.output_json)
    output_json.write_text(json.dumps(results, indent=2, default=str))
    print(f"  JSON results → {output_json}")

    html_out = visualize(
        args.repo_name or repo.name,
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
