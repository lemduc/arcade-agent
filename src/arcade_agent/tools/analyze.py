"""Async end-to-end architecture analysis pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.ingest import IngestedRepo, ingest
from arcade_agent.tools.registry import tool


@dataclass(frozen=True)
class AnalysisResult:
    """Artifacts produced by a complete architecture analysis."""

    repository: IngestedRepo
    graph: DependencyGraph
    architecture: Architecture
    smells: list[SmellInstance]
    metrics: list[MetricResult]


@tool(
    name="analyze",
    description=(
        "Run the complete architecture analysis pipeline asynchronously: "
        "ingest, parse, recover, then detect smells and compute metrics in parallel."
    ),
)
async def analyze(
    source: str,
    language: str | None = None,
    source_root: str | None = None,
    exclude_tests: bool = True,
    algorithm: str = "pkg",
    num_clusters: int | None = None,
    use_cache: bool = True,
    use_llm: bool = False,
) -> AnalysisResult:
    """Run a complete analysis without blocking the caller's event loop.

    The dependency-bearing stages remain ordered. Smell detection and metric
    computation only depend on the recovered architecture, so they run
    concurrently once recovery completes. Existing synchronous tools remain
    unchanged for callers that need individual stages.
    """
    from arcade_agent.tools.compute_metrics import compute_metrics
    from arcade_agent.tools.detect_smells import detect_smells
    from arcade_agent.tools.parse import parse
    from arcade_agent.tools.recover import recover

    repository = await asyncio.to_thread(
        ingest,
        source=source,
        language=language,
        exclude_tests=exclude_tests,
        source_root=source_root,
    )
    graph = await asyncio.to_thread(
        parse,
        source_path=str(repository.path),
        language=repository.language or language,
        files=[str(path) for path in repository.source_files],
        use_cache=use_cache,
    )
    architecture = await asyncio.to_thread(
        recover,
        dep_graph=graph,
        algorithm=algorithm,
        num_clusters=num_clusters,
    )
    smells, metrics = await asyncio.gather(
        asyncio.to_thread(
            detect_smells,
            architecture=architecture,
            dep_graph=graph,
            use_llm=use_llm,
        ),
        asyncio.to_thread(
            compute_metrics,
            architecture=architecture,
            dep_graph=graph,
        ),
    )
    return AnalysisResult(
        repository=repository,
        graph=graph,
        architecture=architecture,
        smells=smells,
        metrics=metrics,
    )
