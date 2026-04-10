"""Tests for baseline comparison reporting."""

import importlib.util
from pathlib import Path

from arcade_agent.exporters.html import export_evolution_html

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
