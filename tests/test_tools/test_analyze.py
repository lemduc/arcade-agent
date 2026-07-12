"""Tests for the asynchronous analysis pipeline."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from unittest.mock import Mock

from arcade_agent.tools.analyze import analyze


def test_analyze_orders_dependencies_and_parallelizes_terminal_stages(monkeypatch, tmp_path):
    events: list[str] = []
    terminal_barrier = threading.Barrier(2, timeout=1)
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
        terminal_barrier.wait()
        events.append("smells")
        return [Mock()]

    def fake_metrics(**kwargs):
        terminal_barrier.wait()
        events.append("metrics")
        return [Mock(), Mock()]

    monkeypatch.setattr("arcade_agent.tools.analyze.ingest", fake_ingest)
    monkeypatch.setattr("arcade_agent.tools.parse.parse", fake_parse)
    monkeypatch.setattr("arcade_agent.tools.recover.recover", fake_recover)
    monkeypatch.setattr("arcade_agent.tools.detect_smells.detect_smells", fake_smells)
    monkeypatch.setattr("arcade_agent.tools.compute_metrics.compute_metrics", fake_metrics)

    result = asyncio.run(analyze(str(tmp_path), language="python", use_cache=False))

    assert events[:3] == ["ingest", "parse", "recover"]
    assert set(events[3:]) == {"smells", "metrics"}
    assert result.repository is repository
    assert result.graph is graph
    assert result.architecture is architecture
    assert len(result.smells) == 1
    assert len(result.metrics) == 2


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
