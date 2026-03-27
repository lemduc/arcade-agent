#!/usr/bin/env python3
"""Basic analysis example using arcade-agent tools.

Usage:
    python examples/basic_analysis.py /path/to/project [--language java] [--algorithm pkg]

Example with ARCADE Core (https://github.com/usc-softarch/arcade_core):
    git clone https://github.com/usc-softarch/arcade_core.git
    python examples/basic_analysis.py arcade_core --language java

See examples/arcade_core_report.html for sample output.
"""

import argparse
import sys
from pathlib import Path

# Ensure arcade_agent is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.query import query
from arcade_agent.tools.recover import recover
from arcade_agent.tools.visualize import visualize


def main():
    parser = argparse.ArgumentParser(description="Analyze software architecture")
    parser.add_argument("source", help="Path to source code directory or git URL")
    parser.add_argument("--language", "-l", default=None, help="Language (java, python)")
    parser.add_argument("--algorithm", "-a", default="pkg", help="Recovery algorithm (pkg, wca, acdc)")
    parser.add_argument("--output", "-o", default="report.html", help="Output file")
    parser.add_argument("--num-clusters", "-n", type=int, default=None, help="Target clusters (WCA)")
    args = parser.parse_args()

    # 1. Ingest
    print(f"[1/6] Ingesting {args.source}...")
    repo = ingest(args.source, language=args.language)
    print(f"  Found {len(repo.source_files)} source files ({repo.language})")
    print(f"  Version: {repo.version}")

    if not repo.source_files:
        print("  No source files found. Exiting.")
        return

    # 2. Parse
    print(f"[2/6] Parsing dependencies...")
    graph = parse(str(repo.path), language=repo.language, files=[str(f) for f in repo.source_files])
    print(f"  {graph.num_entities} entities, {graph.num_edges} edges")

    if graph.num_entities == 0:
        print("  No entities extracted. Exiting.")
        return

    # 3. Recover
    print(f"[3/6] Recovering architecture ({args.algorithm})...")
    arch = recover(graph, algorithm=args.algorithm, num_clusters=args.num_clusters)
    print(f"  {len(arch.components)} components recovered")
    for comp in arch.components:
        print(f"    - {comp.name}: {len(comp.entities)} entities")

    # 4. Detect smells
    print(f"[4/6] Detecting architectural smells...")
    smells = detect_smells(arch, graph)
    print(f"  {len(smells)} smells detected")
    for smell in smells:
        print(f"    - [{smell.severity}] {smell.smell_type}: {smell.description[:80]}")

    # 5. Compute metrics
    print(f"[5/6] Computing quality metrics...")
    metrics = compute_metrics(arch, graph)
    for metric in metrics:
        print(f"    {metric.name}: {metric.value}")

    # 6. Visualize
    print(f"[6/6] Generating report...")
    output = visualize(
        repo.name, repo.version, graph, arch, smells, metrics,
        output=args.output,
    )
    print(f"  Report written to: {output}")

    # Bonus: Show summary query
    summary = query(arch, graph, question="summary")
    print(f"\nSummary: {summary['num_components']} components, "
          f"{summary['num_entities']} entities, "
          f"{summary['num_edges']} edges")

    # Cleanup temp dir
    repo.cleanup()


if __name__ == "__main__":
    main()
