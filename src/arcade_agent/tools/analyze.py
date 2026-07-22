"""Async end-to-end architecture analysis pipeline."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from arcade_agent.algorithms.architecture import Architecture
from arcade_agent.algorithms.metrics import MetricResult
from arcade_agent.algorithms.smells import SmellInstance
from arcade_agent.parsers.graph import DependencyGraph
from arcade_agent.tools.ingest import IngestedRepo, ingest
from arcade_agent.tools.registry import tool

StageCallback = Callable[[str, Any], None]


@dataclass(frozen=True)
class AnalysisResult:
    """Artifacts produced by a complete architecture analysis."""

    repository: IngestedRepo
    graph: DependencyGraph
    architecture: Architecture
    smells: list[SmellInstance]
    metrics: list[MetricResult]


@dataclass
class PartialAnalysisError(Exception):
    """Raised when a pipeline stage fails after earlier stages completed.

    Carries whatever artifacts were produced so callers (e.g. the MCP adapter)
    can preserve per-stage session IDs for retry without redoing ingest/recover.
    """

    stage: str
    cause: BaseException
    repository: IngestedRepo | None = None
    graph: DependencyGraph | None = None
    architecture: Architecture | None = None

    def __str__(self) -> str:
        return f"analyze failed at stage '{self.stage}': {self.cause}"


def _run_sync_pipeline(
    source: str,
    *,
    language: str | None = None,
    source_root: str | None = None,
    work_dir: str | None = None,
    exclude_tests: bool = True,
    algorithm: str = "pkg",
    num_clusters: int | None = None,
    similarity_measure: str = "uem",
    pkg_depth: int | None = None,
    hybrid_weight: float = 0.5,
    use_cache: bool = True,
    use_llm: bool = False,
    on_stage: StageCallback | None = None,
) -> AnalysisResult:
    """Run the full analysis pipeline sequentially on the calling thread."""
    from arcade_agent.tools.compute_metrics import compute_metrics
    from arcade_agent.tools.detect_smells import detect_smells
    from arcade_agent.tools.parse import parse
    from arcade_agent.tools.recover import recover

    repository: IngestedRepo | None = None
    graph: DependencyGraph | None = None
    architecture: Architecture | None = None

    try:
        repository = ingest(
            source=source,
            language=language,
            work_dir=work_dir,
            exclude_tests=exclude_tests,
            source_root=source_root,
        )
        if on_stage is not None:
            on_stage("repository", repository)

        graph = parse(
            source_path=str(repository.path),
            language=repository.language or language,
            files=[str(path) for path in repository.source_files],
            use_cache=use_cache,
            exclude_tests=exclude_tests,
        )
        if on_stage is not None:
            on_stage("graph", graph)

        architecture = recover(
            dep_graph=graph,
            algorithm=algorithm,
            num_clusters=num_clusters,
            similarity_measure=similarity_measure,
            pkg_depth=pkg_depth,
            hybrid_weight=hybrid_weight,
        )
        if on_stage is not None:
            on_stage("architecture", architecture)

        smells = detect_smells(
            architecture=architecture,
            dep_graph=graph,
            use_llm=use_llm,
        )
        if on_stage is not None:
            on_stage("smells", smells)

        metrics = compute_metrics(
            architecture=architecture,
            dep_graph=graph,
        )
        if on_stage is not None:
            on_stage("metrics", metrics)
    except PartialAnalysisError:
        raise
    except Exception as exc:
        raise PartialAnalysisError(
            stage=_failed_stage(repository, graph, architecture),
            cause=exc,
            repository=repository,
            graph=graph,
            architecture=architecture,
        ) from exc

    return AnalysisResult(
        repository=repository,
        graph=graph,
        architecture=architecture,
        smells=smells,
        metrics=metrics,
    )


def _failed_stage(
    repository: IngestedRepo | None,
    graph: DependencyGraph | None,
    architecture: Architecture | None,
) -> str:
    if repository is None:
        return "ingest"
    if graph is None:
        return "parse"
    if architecture is None:
        return "recover"
    return "terminal"


@tool(
    name="analyze",
    description=(
        "Run the complete architecture analysis pipeline asynchronously: "
        "ingest, parse, recover, detect smells, and compute metrics. "
        "Blocking work runs in a worker thread so the caller's event loop stays responsive."
    ),
)
async def analyze(
    source: str,
    language: str | None = None,
    source_root: str | None = None,
    work_dir: str | None = None,
    exclude_tests: bool = True,
    algorithm: str = "pkg",
    num_clusters: int | None = None,
    similarity_measure: str = "uem",
    pkg_depth: int | None = None,
    hybrid_weight: float = 0.5,
    use_cache: bool = True,
    use_llm: bool = False,
    on_stage: StageCallback | None = None,
) -> AnalysisResult:
    """Run a complete analysis without blocking the caller's event loop.

    Stages run sequentially in a worker thread. Existing synchronous tools remain
    unchanged for callers that need individual stages. Optional ``on_stage`` is
    invoked after each successful stage so adapters can persist session IDs
    before later stages fail.
    """
    return await asyncio.to_thread(
        _run_sync_pipeline,
        source,
        language=language,
        source_root=source_root,
        work_dir=work_dir,
        exclude_tests=exclude_tests,
        algorithm=algorithm,
        num_clusters=num_clusters,
        similarity_measure=similarity_measure,
        pkg_depth=pkg_depth,
        hybrid_weight=hybrid_weight,
        use_cache=use_cache,
        use_llm=use_llm,
        on_stage=on_stage,
    )
