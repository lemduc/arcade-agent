"""Tests for repository self-analysis filtering."""

import importlib.util
import json
import sys
from pathlib import Path

from arcade_agent.parsers.graph import DependencyGraph, Edge, Entity
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover

_SELF_ANALYSIS_PATH = Path(__file__).resolve().parents[2] / "scripts" / "run_self_analysis.py"
_SELF_ANALYSIS_SPEC = importlib.util.spec_from_file_location(
    "run_self_analysis",
    _SELF_ANALYSIS_PATH,
)
assert _SELF_ANALYSIS_SPEC and _SELF_ANALYSIS_SPEC.loader
_SELF_ANALYSIS_MODULE = importlib.util.module_from_spec(_SELF_ANALYSIS_SPEC)
_SELF_ANALYSIS_SPEC.loader.exec_module(_SELF_ANALYSIS_MODULE)
_filter_non_architectural_entities = _SELF_ANALYSIS_MODULE._filter_non_architectural_entities
run_self_analysis_main = _SELF_ANALYSIS_MODULE.main


def test_self_analysis_preserves_registration_import_edges():
    """Registration import edges like @tool are kept because they represent real coupling."""
    graph = DependencyGraph(
        entities={
            "arcade_agent.tools.compare.compare": Entity(
                fqn="arcade_agent.tools.compare.compare",
                name="compare",
                package="arcade_agent.tools",
                file_path="src/arcade_agent/tools/compare.py",
                kind="function",
                language="python",
            ),
            "arcade_agent.tools.registry.tool": Entity(
                fqn="arcade_agent.tools.registry.tool",
                name="tool",
                package="arcade_agent.tools",
                file_path="src/arcade_agent/tools/registry.py",
                kind="function",
                language="python",
            ),
            "arcade_agent.algorithms.matching.match_components": Entity(
                fqn="arcade_agent.algorithms.matching.match_components",
                name="match_components",
                package="arcade_agent.algorithms",
                file_path="src/arcade_agent/algorithms/matching.py",
                kind="function",
                language="python",
            ),
        },
        edges=[
            Edge(
                source="arcade_agent.tools.compare.compare",
                target="arcade_agent.tools.registry.tool",
                relation="import",
            ),
            Edge(
                source="arcade_agent.tools.compare.compare",
                target="arcade_agent.algorithms.matching.match_components",
                relation="import",
            ),
        ],
        packages={
            "arcade_agent.tools": [
                "arcade_agent.tools.compare.compare",
                "arcade_agent.tools.registry.tool",
            ],
            "arcade_agent.algorithms": [
                "arcade_agent.algorithms.matching.match_components",
            ],
        },
    )

    filtered = _filter_non_architectural_entities(graph)

    assert (
        "arcade_agent.tools.compare.compare",
        "arcade_agent.tools.registry.tool",
        "import",
    ) in filtered.to_edge_tuples()
    assert (
        "arcade_agent.tools.compare.compare",
        "arcade_agent.algorithms.matching.match_components",
        "import",
    ) in filtered.to_edge_tuples()


def test_self_analysis_filter_does_not_strip_generic_project_entities():
    graph = DependencyGraph(
        entities={
            "sample_app.service.run": Entity(
                fqn="sample_app.service.run",
                name="run",
                package="sample_app",
                file_path="sample_app/service.py",
                kind="function",
                language="python",
            ),
            "sample_app.service.Worker.handle": Entity(
                fqn="sample_app.service.Worker.handle",
                name="handle",
                package="sample_app",
                file_path="sample_app/service.py",
                kind="method",
                language="python",
                properties={"owner": "sample_app.service.Worker"},
            ),
            "sample_app.service._helper": Entity(
                fqn="sample_app.service._helper",
                name="_helper",
                package="sample_app",
                file_path="sample_app/service.py",
                kind="function",
                language="python",
            ),
            "sample_app.registry.tool": Entity(
                fqn="sample_app.registry.tool",
                name="tool",
                package="sample_app",
                file_path="sample_app/registry.py",
                kind="function",
                language="python",
            ),
        },
        edges=[
            Edge(
                source="sample_app.service.run",
                target="sample_app.registry.tool",
                relation="import",
            )
        ],
        packages={
            "sample_app": [
                "sample_app.service.run",
                "sample_app.service._helper",
                "sample_app.registry.tool",
            ]
        },
    )

    filtered = _filter_non_architectural_entities(graph)

    assert "sample_app.service._helper" in filtered.entities
    assert "sample_app.service.Worker.handle" in filtered.entities
    assert (
        "sample_app.service.run",
        "sample_app.registry.tool",
        "import",
    ) in filtered.to_edge_tuples()


def test_self_analysis_pipeline_handles_independent_temp_project(tmp_path):
    project_dir = tmp_path / "sample-app"
    package_dir = project_dir / "sample_app"
    adapters_dir = package_dir / "adapters"
    adapters_dir.mkdir(parents=True)

    (package_dir / "__init__.py").write_text("\n")
    (adapters_dir / "__init__.py").write_text("\n")
    (package_dir / "registry.py").write_text(
        "def tool(fn):\n"
        "    return fn\n"
    )
    (package_dir / "service.py").write_text(
        "from sample_app.registry import tool\n"
        "from sample_app.adapters.worker import execute\n\n"
        "def _helper(value):\n"
        "    return value + 1\n\n"
        "@tool\n"
        "def run():\n"
        "    return execute(_helper(1))\n"
    )
    (adapters_dir / "worker.py").write_text(
        "def execute(value):\n"
        "    return value * 2\n"
    )

    repo = ingest(str(project_dir), language="python")
    raw_graph = parse(
        str(repo.path),
        language=repo.language or "python",
        files=[str(path) for path in repo.source_files],
    )
    graph = _filter_non_architectural_entities(raw_graph)
    architecture = recover(graph, algorithm="pkg")
    metrics = compute_metrics(architecture, graph)
    smells = detect_smells(architecture, graph)

    assert repo.name == "sample-app"
    assert repo.language == "python"
    assert "sample_app.service._helper" in graph.entities
    assert "sample_app.registry.tool" in graph.entities
    assert (
        "sample_app.service.run",
        "sample_app.registry.tool",
        "import",
    ) in graph.to_edge_tuples()
    assert len(architecture.components) >= 2
    assert {metric.name for metric in metrics} == {
        "RCI",
        "TurboMQ",
        "BasicMQ",
        "IntraConnectivity",
        "InterConnectivity",
        "TwoWayPairRatio",
    }
    assert isinstance(smells, list)
    assert all(not fqn.startswith("arcade_agent.") for fqn in graph.entities)


def test_self_analysis_pipeline_handles_independent_temp_java_project(tmp_path):
    project_dir = tmp_path / "sample-java-app"
    source_dir = project_dir / "src" / "main" / "java"
    api_dir = source_dir / "com" / "example" / "api"
    impl_dir = source_dir / "com" / "example" / "impl"
    api_dir.mkdir(parents=True)
    impl_dir.mkdir(parents=True)

    (api_dir / "CalculatorService.java").write_text(
        "package com.example.api;\n\n"
        "import com.example.impl.MathWorker;\n\n"
        "public class CalculatorService {\n"
        "    public int calculate(int value) {\n"
        "        return new MathWorker().doubleIt(value);\n"
        "    }\n"
        "}\n"
    )
    (impl_dir / "MathWorker.java").write_text(
        "package com.example.impl;\n\n"
        "public class MathWorker {\n"
        "    public int doubleIt(int value) {\n"
        "        return value * 2;\n"
        "    }\n"
        "}\n"
    )

    repo = ingest(str(project_dir), language="java")
    raw_graph = parse(
        str(repo.path),
        language=repo.language or "java",
        files=[str(path) for path in repo.source_files],
    )
    graph = _filter_non_architectural_entities(raw_graph)
    architecture = recover(graph, algorithm="pkg")
    metrics = compute_metrics(architecture, graph)
    smells = detect_smells(architecture, graph)

    assert repo.name == "sample-java-app"
    assert repo.language == "java"
    assert repo.path == source_dir
    assert "com.example.api.CalculatorService" in graph.entities
    assert "com.example.impl.MathWorker" in graph.entities
    assert "com.example.api.CalculatorService.calculate" in graph.entities
    assert "com.example.impl.MathWorker.doubleIt" in graph.entities
    assert (
        "com.example.api.CalculatorService",
        "com.example.impl.MathWorker",
        "import",
    ) in graph.to_edge_tuples()
    assert len(architecture.components) >= 1
    assert {
        entity_fqn
        for component in architecture.components
        for entity_fqn in component.entities
    } == set(graph.entities)
    assert len(metrics) == 6
    assert isinstance(smells, list)


def test_run_self_analysis_writes_balanced_scores(tmp_path, monkeypatch):
    project_dir = tmp_path / "sample-app"
    package_dir = project_dir / "sample_app"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("\n")
    (package_dir / "registry.py").write_text("def tool(fn):\n    return fn\n")
    (package_dir / "service.py").write_text(
        "from sample_app.registry import tool\n\n"
        "@tool\n"
        "def run():\n"
        "    return helper()\n\n"
        "def helper():\n"
        "    return 1\n"
    )

    output_json = tmp_path / "results.json"
    output_html = tmp_path / "report.html"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_self_analysis.py",
            "--source",
            str(project_dir),
            "--language",
            "python",
            "--output-json",
            str(output_json),
            "--output-html",
            str(output_html),
        ],
    )

    run_self_analysis_main()

    payload = json.loads(output_json.read_text())

    assert output_html.exists()
    assert set(payload["derived_metrics"]) == {
        "DependencyHealth",
        "ComponentBalance",
        "HubBalance",
        "BoundaryClarity",
        "DependencyDistribution",
        "SmellDiscipline",
        "PrincipleAlignmentScore",
        "BalancedArchitectureScore",
    }
    assert set(payload["principle_signals"]) == {
        "AcyclicDependencies",
        "LayeringHealth",
        "ResponsibilityFocus",
        "InterfaceSegregation",
        "ComponentBalance",
        "HubBalance",
        "BoundaryClarity",
        "DependencyDistribution",
        "SmellDiscipline",
    }
    assert set(payload["score_drivers"]) == {"risks", "strengths"}
