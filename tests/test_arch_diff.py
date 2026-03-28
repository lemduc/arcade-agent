"""Tests for the arch_diff script."""

import pytest

from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.models.graph import DependencyGraph, Edge, Entity
from arcade_agent.models.metrics import MetricResult
from arcade_agent.models.smells import SmellInstance
from arcade_agent.serialization import load_architecture, save_architecture

# Import after arcade_agent so modules are available
from scripts.arch_diff import build_report, main


@pytest.fixture
def sample_graph():
    entities = {
        "com.example.calc.Calculator": Entity(
            fqn="com.example.calc.Calculator",
            name="Calculator",
            package="com.example.calc",
            file_path="Calculator.java",
            kind="class",
            language="java",
            imports=["com.example.util.MathHelper"],
        ),
        "com.example.util.MathHelper": Entity(
            fqn="com.example.util.MathHelper",
            name="MathHelper",
            package="com.example.util",
            file_path="MathHelper.java",
            kind="class",
            language="java",
        ),
    }
    edges = [
        Edge(
            source="com.example.calc.Calculator",
            target="com.example.util.MathHelper",
            relation="import",
        ),
    ]
    packages = {
        "com.example.calc": ["com.example.calc.Calculator"],
        "com.example.util": ["com.example.util.MathHelper"],
    }
    return DependencyGraph(entities=entities, edges=edges, packages=packages)


@pytest.fixture
def sample_arch():
    return Architecture(
        components=[
            Component(
                name="Calc",
                responsibility="Calculator functionality",
                entities=["com.example.calc.Calculator"],
            ),
            Component(
                name="Util",
                responsibility="Utility helpers",
                entities=["com.example.util.MathHelper"],
            ),
        ],
        rationale="Package-based grouping",
        algorithm="pkg",
    )


@pytest.fixture
def sample_metrics():
    return [
        MetricResult(name="RCI", value=0.75),
        MetricResult(name="TurboMQ", value=0.50),
    ]


def test_diff_no_baseline(sample_arch, sample_graph, sample_metrics):
    """Report without baseline includes metrics table and no drift section."""
    report = build_report(
        current=sample_arch,
        graph=sample_graph,
        metrics=sample_metrics,
        smells=[],
    )
    assert "## Architecture Drift Report" in report
    assert "<!-- arcade-agent-drift-report -->" in report
    assert "Drift from Baseline" not in report
    assert "### Metrics" in report
    assert "RCI" in report
    assert "0.75" in report


def test_diff_with_baseline(sample_arch, sample_graph, sample_metrics):
    """Report with baseline includes drift table."""
    drift = {
        "overall_similarity": 0.85,
        "matches": [
            {
                "source": "Calc",
                "target": "Calc",
                "similarity": 1.0,
                "entities_added": [],
                "entities_removed": [],
            },
            {
                "source": "Util",
                "target": "Util",
                "similarity": 1.0,
                "entities_added": [],
                "entities_removed": [],
            },
        ],
        "summary": {
            "total_matches": 2,
            "components_added": 0,
            "components_removed": 0,
            "possible_splits": 0,
            "possible_merges": 0,
            "arch_a_components": 2,
            "arch_b_components": 2,
        },
    }
    baseline = Architecture(
        components=[
            Component(name="Calc", responsibility="", entities=["com.example.calc.Calculator"]),
            Component(name="Util", responsibility="", entities=["com.example.util.MathHelper"]),
        ],
        algorithm="pkg",
    )

    report = build_report(
        current=sample_arch,
        graph=sample_graph,
        metrics=sample_metrics,
        smells=[],
        drift=drift,
        baseline=baseline,
    )
    assert "### Drift from Baseline" in report
    assert "Similarity" in report
    assert "0.85" in report
    assert "No structural changes detected" in report


def test_diff_with_smells(sample_arch, sample_graph, sample_metrics):
    """Report includes smells section when smells are detected."""
    smells = [
        SmellInstance(
            smell_type="Dependency Cycle",
            severity="high",
            affected_components=["Calc", "Util"],
        ),
    ]
    report = build_report(
        current=sample_arch,
        graph=sample_graph,
        metrics=sample_metrics,
        smells=smells,
    )
    assert "### Smells (1)" in report
    assert "Dependency Cycle" in report
    assert "Calc, Util" in report


def test_update_baseline(sample_arch, tmp_path):
    """--update-baseline writes the baseline file."""
    baseline_path = tmp_path / ".arcade" / "baseline.json"
    save_architecture(sample_arch, baseline_path)

    loaded = load_architecture(baseline_path)
    assert len(loaded.components) == 2
    assert loaded.algorithm == "pkg"


def test_main_update_baseline(tmp_path, monkeypatch):
    """main() with --update-baseline creates the baseline file."""
    baseline_path = tmp_path / "baseline.json"

    # Create a minimal project with a Python file
    src = tmp_path / "project" / "app.py"
    src.parent.mkdir(parents=True)
    src.write_text(
        "class Foo:\n    pass\n\nclass Bar:\n    def use_foo(self):\n        f = Foo()\n"
    )

    main([
        "--source", str(src.parent),
        "--language", "python",
        "--baseline", str(baseline_path),
        "--update-baseline",
    ])

    assert baseline_path.exists()
    loaded = load_architecture(baseline_path)
    assert loaded.algorithm == "pkg"
    assert len(loaded.components) >= 1
