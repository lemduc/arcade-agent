"""Tests for baseline comparison reporting."""

import importlib.util
from pathlib import Path

from arcade_agent.ci.compare_baseline import _component_map, _normalize_snapshot
from arcade_agent.exporters.html import (
    build_snapshot_mermaid,
    export_evolution_html,
    export_html,
)
from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.models.graph import DependencyGraph, Entity
from arcade_agent.models.metrics import MetricResult

_COMPARE_BASELINE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compare_baseline.py"
_COMPARE_BASELINE_SPEC = importlib.util.spec_from_file_location(
    "compare_baseline",
    _COMPARE_BASELINE_PATH,
)
assert _COMPARE_BASELINE_SPEC and _COMPARE_BASELINE_SPEC.loader
_COMPARE_BASELINE_MODULE = importlib.util.module_from_spec(_COMPARE_BASELINE_SPEC)
_COMPARE_BASELINE_SPEC.loader.exec_module(_COMPARE_BASELINE_MODULE)
build_report_payload = _COMPARE_BASELINE_MODULE.build_report_payload
build_comment = _COMPARE_BASELINE_MODULE.build_comment


def _snapshot(commit_sha: str, component_name: str, classes: int, methods: int) -> dict:
    return {
        "repo_name": "sample-repo",
        "commit_sha": commit_sha,
        "algorithm": "pkg",
        "num_components": 1,
        "num_entities": 1,
        "num_edges": 0,
        "source_num_entities": 1 + methods,
        "class_count": classes,
        "function_count": 0,
        "method_count": methods,
        "component_dependencies": [],
        "components": [
            {
                "name": component_name,
                "responsibility": component_name,
                "num_entities": 1,
                "class_count": classes,
                "function_count": 0,
                "method_count": methods,
                "entity_kind_counts": {"class": classes, "method": methods},
                "entities": [f"pkg.{component_name}"],
            }
        ],
        "metrics": {"RCI": 0.7, "TurboMQ": 0.4},
        "smells": [],
    }


def test_build_report_payload_tracks_component_and_method_deltas():
    baseline = _snapshot("abc1234", "Core", 1, 2)
    current = _snapshot("def5678", "Core", 1, 4)

    report = build_report_payload(current, baseline, run_url="https://example.test/run")

    assert report["overview_cards"][0]["value"] == 1
    assert any(row["name"] == "Methods" and row["delta"] == "+2" for row in report["metric_rows"])
    assert report["component_rows"][0]["status"] == "matched"
    assert "+2" in report["component_rows"][0]["methods"]


def test_export_evolution_html_writes_report(tmp_path: Path):
    baseline = _snapshot("abc1234", "Core", 1, 1)
    current = _snapshot("def5678", "Core", 1, 2)
    report = build_report_payload(current, baseline)

    output = tmp_path / "comparison.html"
    export_evolution_html(report, output)

    content = output.read_text()
    assert "Architecture Evolution Report" in content
    assert "Core" in content
    assert "Methods" in content


def test_export_html_metrics_nav_uses_metric_groups(tmp_path: Path):
    graph = DependencyGraph(
        entities={
            "pkg.Core": Entity(
                fqn="pkg.Core",
                name="Core",
                package="pkg",
                file_path="core.py",
                kind="class",
                language="python",
            )
        },
        edges=[],
        packages={"pkg": ["pkg.Core"]},
    )
    architecture = Architecture(
        components=[
            Component(name="Core", responsibility="Core", entities=["pkg.Core"])
        ],
        algorithm="pkg",
    )
    output = tmp_path / "report.html"

    export_html(
        "sample-repo",
        "local",
        graph,
        architecture,
        [],
        [
            MetricResult(name="RCI", value=0.75),
            MetricResult(name="BalancedArchitectureScore", value=0.82, details=None),
        ],
        output,
    )

    content = output.read_text()
    assert '<a href="#metrics">Metrics</a>' in content
    assert "Quality Metrics" in content
    assert "BalancedArchitectureScore" in content


def test_build_report_payload_derives_names_for_generic_components():
    baseline = _snapshot("abc1234", "Repository3", 1, 1)
    baseline["components"][0]["entities"] = [
        "sample_repo.algorithms.coupling.compute_rci",
        "sample_repo.algorithms.coupling.compute_turbo_mq",
    ]
    baseline["component_dependencies"] = [
        {"source": "Repository3", "target": "Repository3"}
    ]
    current = _snapshot("def5678", "Repository3", 1, 1)
    current["components"][0]["entities"] = list(baseline["components"][0]["entities"])
    current["component_dependencies"] = list(baseline["component_dependencies"])

    report = build_report_payload(current, baseline)

    assert report["current"]["components"][0]["comparison_name"] == "AlgorithmsCoupling"
    assert report["dependency_rows"][0]["status"] == "matched"


def test_snapshot_mermaid_uses_comparison_names_for_nodes_and_dependencies():
    baseline = _snapshot("abc1234", "Repository3", 1, 1)
    baseline["components"][0]["entities"] = [
        "sample_repo.algorithms.coupling.compute_rci",
        "sample_repo.algorithms.coupling.compute_turbo_mq",
    ]
    baseline["component_dependencies"] = [
        {"source": "Repository3", "target": "Repository3"}
    ]
    current = _snapshot("def5678", "Repository3", 1, 1)
    current["components"][0]["entities"] = list(baseline["components"][0]["entities"])
    current["component_dependencies"] = list(baseline["component_dependencies"])

    report = build_report_payload(current, baseline)
    mermaid = build_snapshot_mermaid(report["current"])

    assert 'AlgorithmsCoupling["AlgorithmsCoupling\\n' in mermaid
    assert "AlgorithmsCoupling --> AlgorithmsCoupling" in mermaid
    assert 'Repository3["' not in mermaid


def _multi_component_snapshot(commit_sha: str, packages: list[str]) -> dict:
    """Snapshot whose generic component names all get derived from entity FQNs."""
    components = [
        {
            "name": f"Cluster{index}",
            "responsibility": f"Cluster{index}",
            "num_entities": 2,
            "class_count": 1,
            "function_count": 0,
            "method_count": 1,
            "entity_kind_counts": {"class": 1, "method": 1},
            "entities": [f"app.{package}.fn0", f"app.{package}.fn1"],
        }
        for index, package in enumerate(packages)
    ]
    return {
        "repo_name": "sample-repo",
        "commit_sha": commit_sha,
        "algorithm": "pkg",
        "num_components": len(components),
        "num_entities": 2 * len(components),
        "num_edges": 0,
        "source_num_entities": 2 * len(components),
        "class_count": len(components),
        "function_count": 0,
        "method_count": len(components),
        "component_dependencies": [],
        "components": components,
        "metrics": {"RCI": 0.7, "TurboMQ": 0.4},
        "smells": [],
    }


def test_comparison_names_stay_unique_when_derived_name_looks_suffixed():
    """A derived name of ``Api2`` must not collide with the suffixed ``Api`` bucket."""
    current = _multi_component_snapshot("def5678", ["api", "api", "api2"])

    report = build_report_payload(current, None)
    names = [component["comparison_name"] for component in report["current"]["components"]]

    assert names == ["Api", "Api2", "Api22"]
    assert len(names) == len(set(names))


def test_component_map_keeps_every_component_when_names_would_collide():
    """Colliding comparison names used to silently drop a component from the map."""
    current = _multi_component_snapshot("def5678", ["api", "api", "api2"])

    normalized = _normalize_snapshot(current)
    component_map = _component_map(normalized)

    assert len(normalized["components"]) == 3
    assert len(component_map) == 3
    assert sorted(component_map) == ["Api", "Api2", "Api22"]


def test_comment_component_table_has_no_duplicate_rows():
    """The markdown breakdown used to emit the same component name twice."""
    current = _multi_component_snapshot("def5678", ["api", "api", "api2"])

    comment = build_comment(current, None)
    comment_rows = [line for line in comment.splitlines() if line.startswith("| Api")]

    assert len(comment_rows) == 3
    assert len(comment_rows) == len(set(comment_rows))


def test_snapshot_mermaid_escapes_quotes_in_component_labels():
    snapshot = {
        "components": [
            {
                "name": 'Auth "core" (v2)',
                "comparison_name": 'Auth "core" (v2)',
                "num_entities": 1,
                "class_count": 1,
                "method_count": 1,
            }
        ],
        "component_dependencies": [],
    }

    mermaid = build_snapshot_mermaid(snapshot)
    node_line = mermaid.splitlines()[1]

    # A raw `"` inside the label terminates the node early and breaks the block.
    assert node_line.count('"') == 2
    assert "#quot;" in node_line


def test_snapshot_mermaid_gives_symbol_only_names_distinct_node_ids():
    snapshot = {
        "components": [
            {
                "name": name,
                "comparison_name": name,
                "num_entities": 1,
                "class_count": 1,
                "method_count": 1,
            }
            for name in ("###", "!!!")
        ],
        "component_dependencies": [{"source": "###", "target": "!!!"}],
    }

    mermaid = build_snapshot_mermaid(snapshot)
    node_ids = [line.split("[")[0].strip() for line in mermaid.splitlines()[1:3]]

    assert len(set(node_ids)) == 2
    assert mermaid.splitlines()[3].strip() == f"{node_ids[0]} --> {node_ids[1]}"


def test_snapshot_mermaid_caps_node_id_and_label_length():
    long_name = "A" * 120
    other_long_name = "A" * 118 + "B" * 2
    snapshot = {
        "components": [
            {
                "name": name,
                "comparison_name": name,
                "num_entities": 1,
                "class_count": 1,
                "method_count": 1,
            }
            for name in (long_name, other_long_name)
        ],
        "component_dependencies": [{"source": long_name, "target": other_long_name}],
    }

    mermaid = build_snapshot_mermaid(snapshot)
    node_lines = mermaid.splitlines()[1:3]
    node_ids = [line.split("[")[0].strip() for line in node_lines]

    assert all(len(node_id) <= 48 for node_id in node_ids)
    # Truncation must not merge two distinct components sharing a long prefix.
    assert len(set(node_ids)) == 2
    for line in node_lines:
        label = line.split('["', 1)[1].split("\\n", 1)[0]
        assert len(label) <= 48
    assert mermaid.splitlines()[3].strip() == f"{node_ids[0]} --> {node_ids[1]}"


def test_build_report_payload_uses_repo_name_from_snapshot():
    baseline = _snapshot("abc1234", "Core", 1, 1)
    current = _snapshot("def5678", "Core", 1, 1)
    current["repo_name"] = "independent-framework"

    report = build_report_payload(current, baseline)

    assert report["repo_name"] == "independent-framework"


def test_build_report_payload_marks_new_schema_counts_without_fake_zero_baseline():
    baseline = _snapshot("abc1234", "Core", 1, 1)
    baseline.pop("class_count")
    baseline.pop("function_count")
    baseline.pop("method_count")
    baseline["components"][0].pop("class_count")
    baseline["components"][0].pop("function_count")
    baseline["components"][0].pop("method_count")

    current = _snapshot("def5678", "Core", 2, 3)

    report = build_report_payload(current, baseline)
    metric_rows = {row["name"]: row for row in report["metric_rows"]}

    assert metric_rows["Classes"]["baseline"] == "n/a"
    assert metric_rows["Classes"]["delta"] == "new in schema"
    assert metric_rows["Methods"]["baseline"] == "n/a"
    assert metric_rows["Methods"]["delta"] == "new in schema"
    assert report["component_rows"][0]["classes"] == "n/a → 2 (new in schema)"
    assert report["component_rows"][0]["methods"] == "n/a → 3 (new in schema)"


def test_build_comment_includes_baseline_transition_note_when_provided():
    current = _snapshot("def5678", "Core", 1, 2)

    comment = build_comment(
        current,
        None,
        baseline_note=(
            "Improvement tracking is temporarily unavailable because the baseline "
            "algorithm changed."
        ),
    )

    assert "Improvement tracking is temporarily unavailable" in comment


def test_build_report_payload_marks_new_derived_metrics_without_fake_zero_baseline():
    baseline = _snapshot("abc1234", "Core", 1, 1)
    current = _snapshot("def5678", "Core", 1, 1)
    current["derived_metrics"] = {
        "BalancedArchitectureScore": 0.8125,
        "PrincipleAlignmentScore": 0.7900,
    }

    report = build_report_payload(current, baseline)
    metric_rows = {row["name"]: row for row in report["metric_rows"]}

    assert metric_rows["BalancedArchitectureScore"]["baseline"] == "n/a"
    assert metric_rows["BalancedArchitectureScore"]["delta"] == "new in schema"
    assert metric_rows["PrincipleAlignmentScore"]["baseline"] == "n/a"


def test_build_comment_does_not_label_rci_fallback_as_balanced_score():
    baseline = _snapshot("abc1234", "Core", 1, 1)
    baseline["metrics"]["RCI"] = 0.1234
    current = _snapshot("def5678", "Core", 1, 1)
    current["derived_metrics"] = {
        "BalancedArchitectureScore": 0.8125,
        "PrincipleAlignmentScore": 0.7900,
    }

    comment = build_comment(current, baseline)

    assert "| BalancedArchitectureScore | n/a | 0.8125 | ⚪ **new in schema** |" in comment
    assert "| BalancedArchitectureScore | 0.1234 |" not in comment


def test_build_comment_uses_quality_label_when_score_falls_back_to_rci():
    current = _snapshot("def5678", "Core", 1, 1)

    comment = build_comment(current, None)

    assert "QualityScore=0.7000" in comment
    assert "BalancedArchitectureScore=0.7000" not in comment


def test_build_comment_handles_null_score_driver_payload():
    current = _snapshot("def5678", "Core", 1, 1)
    current["score_drivers"] = None

    comment = build_comment(current, None)

    assert "Architecture Analysis Summary" in comment
    assert "Top Risk Driver" not in comment


def test_build_report_payload_marks_metrics_without_baseline_as_uncompared():
    current = _snapshot("def5678", "Core", 1, 1)
    current["derived_metrics"] = {"BalancedArchitectureScore": 0.8125}

    report = build_report_payload(current, None)
    metric_rows = {row["name"]: row for row in report["metric_rows"]}

    assert report["overview_cards"][1]["label"] == "Quality Score"
    assert metric_rows["BalancedArchitectureScore"]["baseline"] == "n/a"
    assert metric_rows["BalancedArchitectureScore"]["delta"] == "n/a"


def test_build_report_payload_uses_metric_semantics_for_lower_is_better_metrics():
    baseline = _snapshot("abc1234", "Core", 1, 1)
    current = _snapshot("def5678", "Core", 1, 1)
    baseline["metrics"]["InterConnectivity"] = 0.2000
    current["metrics"]["InterConnectivity"] = 0.1000

    report = build_report_payload(current, baseline)
    metric_rows = {row["name"]: row for row in report["metric_rows"]}

    assert metric_rows["InterConnectivity"]["delta"] == "-0.1000"
    assert metric_rows["InterConnectivity"]["delta_class"] == "delta-positive"


def test_build_comment_shows_score_drivers_when_available():
    current = _snapshot("def5678", "Core", 1, 1)
    current["derived_metrics"] = {
        "BalancedArchitectureScore": 0.8125,
        "PrincipleAlignmentScore": 0.7900,
        "HubBalance": 0.5000,
    }
    current["principle_signals"] = {
        "AcyclicDependencies": 1.0,
        "HubBalance": 0.5000,
    }
    current["score_drivers"] = {
        "risks": [{"name": "HubBalance", "value": 0.5, "gap_to_ideal": 0.5}],
        "strengths": [{"name": "AcyclicDependencies", "value": 1.0, "gap_to_ideal": 0.0}],
    }

    comment = build_comment(current, None)

    assert "### 🎯 Score Drivers" in comment
    assert "Top Risk Driver" in comment
    assert "HubBalance" in comment
