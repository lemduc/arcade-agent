"""Tests for the arch_diff script."""

import pytest

from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.models.graph import DependencyGraph, Edge, Entity
from arcade_agent.models.metrics import MetricResult
from arcade_agent.models.smells import SmellInstance, SmellType
from arcade_agent.serialization import load_architecture, save_architecture
from arcade_agent.tools.compare import compare

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


def test_diff_report_includes_balanced_scores(sample_arch, sample_graph, sample_metrics):
    """Report includes balanced scores in the legacy drift comment surface."""
    metrics = sample_metrics + [
        MetricResult(name="BalancedArchitectureScore", value=0.8125),
        MetricResult(name="PrincipleAlignmentScore", value=0.7900),
    ]

    report = build_report(
        current=sample_arch,
        graph=sample_graph,
        metrics=metrics,
        smells=[],
    )

    assert "BalancedArchitectureScore" in report
    assert "PrincipleAlignmentScore" in report


def test_diff_with_baseline(sample_arch, sample_graph, sample_metrics):
    """Report with baseline includes drift table, sourced from a real compare()."""
    baseline = Architecture(
        components=[
            Component(name="Calc", responsibility="", entities=["com.example.calc.Calculator"]),
            Component(name="Util", responsibility="", entities=["com.example.util.MathHelper"]),
        ],
        algorithm="pkg",
    )
    drift = compare(baseline, sample_arch)
    assert drift["summary"]["splits"] == 0
    assert drift["summary"]["merges"] == 0

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
    assert f"{drift['overall_similarity']:.2f}" in report
    assert "No architectural changes." in report


def test_diff_with_baseline_includes_balanced_scores(sample_arch, sample_graph, sample_metrics):
    """Baseline drift table includes balanced scores when they are computed."""
    metrics = sample_metrics + [
        MetricResult(name="BalancedArchitectureScore", value=0.8125),
        MetricResult(name="PrincipleAlignmentScore", value=0.7900),
    ]
    baseline = Architecture(
        components=[
            Component(name="Calc", responsibility="", entities=["com.example.calc.Calculator"]),
            Component(name="Util", responsibility="", entities=["com.example.util.MathHelper"]),
        ],
        algorithm="pkg",
    )
    drift = compare(baseline, sample_arch)

    report = build_report(
        current=sample_arch,
        graph=sample_graph,
        metrics=metrics,
        smells=[],
        drift=drift,
        baseline=baseline,
    )

    assert "BalancedArchitectureScore" in report
    assert "PrincipleAlignmentScore" in report


def test_diff_with_smells(sample_arch, sample_graph, sample_metrics):
    """Report includes smells section when smells are detected."""
    smells = [
        SmellInstance(
            smell_type=SmellType.DEPENDENCY_CYCLE,
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
    assert "SmellType.DEPENDENCY_CYCLE" not in report
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


def test_report_includes_the_architectural_changelog(tmp_path):
    """The PR comment shows the changelog section when a baseline exists."""
    from arcade_agent.algorithms.architecture import Architecture, Component
    from arcade_agent.ci.arch_diff import build_report
    from arcade_agent.parsers.graph import DependencyGraph
    from arcade_agent.tools.compare import compare

    baseline = Architecture(
        components=[Component(name="auth", responsibility="",
                              entities=["a.A", "a.B", "a.C", "z.X", "z.Y", "z.Z"])],
        algorithm="pkg",
    )
    current = Architecture(
        components=[
            Component(name="auth", responsibility="", entities=["a.A", "a.B", "a.C"]),
            Component(name="authz", responsibility="", entities=["z.X", "z.Y", "z.Z"]),
        ],
        algorithm="pkg",
    )
    graph = DependencyGraph()
    report = build_report(
        current, graph, metrics=[], smells=[],
        drift=compare(baseline, current), baseline=baseline,
    )
    assert "Architectural changes" in report
    assert "authz" in report


def test_arch_diff_exits_zero_even_when_drift_is_detected(tmp_path):
    """Documented behaviour: arch-diff is informational, not a gate.

    Exercises the real console script so the guarantee is tested by
    behaviour, not by grepping the source for a particular spelling of exit.
    """
    import subprocess

    repo = tmp_path / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "a.py").write_text("class A:\n    pass\n")
    (repo / "pkg" / "b.py").write_text("from pkg.a import A\n\n\nclass B(A):\n    pass\n")

    # First run stores a baseline; second run detects drift against it.
    # cwd is pinned to the throwaway repo so the default relative
    # ".arcade/baseline.json" path never touches this repo's own baseline.
    first = subprocess.run(
        ["arcade-arch-diff", "--source", str(repo), "--language", "python",
         "--update-baseline"],
        capture_output=True,
        cwd=repo,
    )
    assert first.returncode == 0, first.stderr.decode()

    (repo / "pkg" / "c.py").write_text("from pkg.b import B\n\n\nclass C(B):\n    pass\n")
    second = subprocess.run(
        ["arcade-arch-diff", "--source", str(repo), "--language", "python"],
        capture_output=True,
        cwd=repo,
    )
    assert second.returncode == 0, second.stderr.decode()
