"""Tests for the asynchronous analysis pipeline."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from arcade_agent.tools.analyze import PartialAnalysisError, analyze
from arcade_agent.tools.registry import get_tool


def test_analyze_is_registered_as_async_tool():
    import arcade_agent.tools.parse  # noqa: F401 — register sync tool

    tool = get_tool("analyze")
    assert tool.is_async is True
    assert get_tool("parse").is_async is False


def test_analyze_runs_stages_sequentially(monkeypatch, tmp_path):
    events: list[str] = []
    repository = Mock(path=tmp_path, language="python", source_files=[Path("example.py")])
    graph = Mock()
    architecture = Mock()

    def fake_ingest(**kwargs):
        events.append("ingest")
        return repository

    def fake_parse(**kwargs):
        assert events == ["ingest"]
        events.append("parse")
        return graph

    def fake_recover(**kwargs):
        assert events == ["ingest", "parse"]
        events.append("recover")
        return architecture

    def fake_smells(**kwargs):
        assert events == ["ingest", "parse", "recover"]
        events.append("smells")
        return [Mock()]

    def fake_metrics(**kwargs):
        assert events == ["ingest", "parse", "recover", "smells"]
        events.append("metrics")
        return [Mock(), Mock()]

    monkeypatch.setattr("arcade_agent.tools.analyze.ingest", fake_ingest)
    monkeypatch.setattr("arcade_agent.tools.parse.parse", fake_parse)
    monkeypatch.setattr("arcade_agent.tools.recover.recover", fake_recover)
    monkeypatch.setattr("arcade_agent.tools.detect_smells.detect_smells", fake_smells)
    monkeypatch.setattr("arcade_agent.tools.compute_metrics.compute_metrics", fake_metrics)

    result = asyncio.run(analyze(str(tmp_path), language="python", use_cache=False))

    assert events == ["ingest", "parse", "recover", "smells", "metrics"]
    assert result.repository is repository
    assert result.graph is graph
    assert result.architecture is architecture
    assert len(result.smells) == 1
    assert len(result.metrics) == 2


def test_analyze_forwards_recover_and_ingest_tuning_params(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    repository = Mock(path=tmp_path, language="python", source_files=[])

    def fake_ingest(**kwargs):
        captured["ingest"] = kwargs
        return repository

    def fake_recover(**kwargs):
        captured["recover"] = kwargs
        return Mock()

    monkeypatch.setattr("arcade_agent.tools.analyze.ingest", fake_ingest)
    monkeypatch.setattr("arcade_agent.tools.parse.parse", lambda **kwargs: Mock())
    monkeypatch.setattr("arcade_agent.tools.recover.recover", fake_recover)
    monkeypatch.setattr("arcade_agent.tools.detect_smells.detect_smells", lambda **kwargs: [])
    monkeypatch.setattr("arcade_agent.tools.compute_metrics.compute_metrics", lambda **kwargs: [])

    asyncio.run(
        analyze(
            str(tmp_path),
            language="python",
            work_dir="/tmp/work",
            algorithm="wca",
            num_clusters=4,
            similarity_measure="js",
            pkg_depth=2,
            hybrid_weight=0.25,
            use_cache=False,
        )
    )

    assert captured["ingest"]["work_dir"] == "/tmp/work"
    assert captured["recover"]["algorithm"] == "wca"
    assert captured["recover"]["num_clusters"] == 4
    assert captured["recover"]["similarity_measure"] == "js"
    assert captured["recover"]["pkg_depth"] == 2
    assert captured["recover"]["hybrid_weight"] == 0.25


def test_analyze_yields_control_while_blocking_work_runs(monkeypatch, tmp_path):
    started = threading.Event()
    release = threading.Event()
    repository = Mock(path=tmp_path, language="python", source_files=[])

    def fake_ingest(**kwargs):
        started.set()
        release.wait(timeout=1)
        return repository

    monkeypatch.setattr("arcade_agent.tools.analyze.ingest", fake_ingest)

    async def exercise():
        task = asyncio.create_task(analyze(str(tmp_path), language="python"))
        await asyncio.to_thread(started.wait, 1)
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        await task

    monkeypatch.setattr("arcade_agent.tools.parse.parse", lambda **kwargs: Mock())
    monkeypatch.setattr("arcade_agent.tools.recover.recover", lambda **kwargs: Mock())
    monkeypatch.setattr("arcade_agent.tools.detect_smells.detect_smells", lambda **kwargs: [])
    monkeypatch.setattr("arcade_agent.tools.compute_metrics.compute_metrics", lambda **kwargs: [])

    asyncio.run(exercise())


def test_analyze_raises_partial_error_with_completed_artifacts(monkeypatch, tmp_path):
    repository = Mock(path=tmp_path, language="python", source_files=[])
    graph = Mock()
    architecture = Mock()
    stages: list[str] = []

    monkeypatch.setattr(
        "arcade_agent.tools.analyze.ingest",
        lambda **kwargs: repository,
    )
    monkeypatch.setattr("arcade_agent.tools.parse.parse", lambda **kwargs: graph)
    monkeypatch.setattr("arcade_agent.tools.recover.recover", lambda **kwargs: architecture)
    monkeypatch.setattr(
        "arcade_agent.tools.detect_smells.detect_smells",
        Mock(side_effect=RuntimeError("smell boom")),
    )
    monkeypatch.setattr(
        "arcade_agent.tools.compute_metrics.compute_metrics",
        Mock(side_effect=AssertionError("metrics should not run")),
    )

    with pytest.raises(PartialAnalysisError) as exc_info:
        asyncio.run(
            analyze(
                str(tmp_path),
                language="python",
                on_stage=lambda name, _value: stages.append(name),
            )
        )

    err = exc_info.value
    assert err.stage == "terminal"
    assert err.repository is repository
    assert err.graph is graph
    assert err.architecture is architecture
    assert stages == ["repository", "graph", "architecture"]
