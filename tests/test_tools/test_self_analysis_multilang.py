"""Thin CLI E2E for arcade-self-analysis --languages java,kotlin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("tree_sitter_kotlin")
pytest.importorskip("tree_sitter_java")

from scripts.run_self_analysis import main as run_self_analysis_main  # noqa: E402


def test_self_analysis_languages_java_kotlin_on_mixed_fixture(
    fixtures_dir: Path, tmp_path, monkeypatch
):
    root = fixtures_dir / "java_kotlin_mixed"
    output_json = tmp_path / "results.json"
    output_html = tmp_path / "report.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_self_analysis.py",
            "--source",
            str(root),
            "--languages",
            "java,kotlin",
            "--algorithm",
            "pkg",
            "--output-json",
            str(output_json),
            "--output-html",
            str(output_html),
        ],
    )

    run_self_analysis_main()

    payload = json.loads(output_json.read_text())
    assert output_html.exists()
    assert sorted(payload["languages"]) == ["java", "kotlin"]
    assert payload["num_entities"] >= 2
    assert payload["num_components"] > 0
    assert payload["num_edges"] >= 1
