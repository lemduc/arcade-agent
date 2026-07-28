"""Contract tests for pinned real-world repository CI."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "run_real_world_case.py"
MANIFEST_PATH = ROOT / "docs" / "real-world-cases.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "real-world-analysis.yml"

SPEC = importlib.util.spec_from_file_location("run_real_world_case", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_manifest_has_nine_unique_pinned_large_cases():
    cases = MODULE.load_cases(MANIFEST_PATH)

    assert [case.id for case in cases] == [f"RW-L{index:02d}" for index in range(1, 10)]
    assert len({case.ref for case in cases}) == 9
    assert all(len(case.ref) == 40 for case in cases)
    assert all(case.repository.startswith("https://github.com/") for case in cases)
    assert all(case.sparse_paths for case in cases)


def test_manifest_covers_large_polyglot_and_many_package_shapes():
    cases = {case.id: case for case in MODULE.load_cases(MANIFEST_PATH)}

    assert cases["RW-L01"].languages == ("java", "python", "go", "typescript")
    assert cases["RW-L02"].languages == ("go", "typescript")
    assert cases["RW-L03"].languages == ("c", "python", "go", "java")
    assert cases["RW-L04"].sparse_paths == ("packages", "plugins")
    assert "staging/src/k8s.io" in cases["RW-L05"].sparse_paths
    assert cases["RW-L07"].tier == "scale"


def test_scheduled_selection_is_stable_within_one_week_and_rotates():
    cases = MODULE.load_cases(MANIFEST_PATH)

    monday = MODULE.select_cases(cases, "scheduled", rotation_date=date(2026, 7, 27))
    sunday = MODULE.select_cases(cases, "scheduled", rotation_date=date(2026, 8, 2))
    next_monday = MODULE.select_cases(cases, "scheduled", rotation_date=date(2026, 8, 3))

    assert monday == sunday
    assert monday != next_monday


def test_matrix_is_bounded_and_contains_case_timeouts():
    cases = MODULE.load_cases(MANIFEST_PATH)

    selected = MODULE.select_cases(cases, "all")
    matrix = {"include": [case.matrix_entry() for case in selected]}

    assert len(matrix["include"]) == 9
    assert all(
        10 <= row["analysis_timeout_minutes"] < row["job_timeout_minutes"] <= 360
        for row in matrix["include"]
    )
    assert {row["tier"] for row in matrix["include"]} == {"large", "scale"}


def test_build_analysis_command_uses_arrays_and_exact_manifest_values(tmp_path):
    case = MODULE.load_cases(MANIFEST_PATH)[0]
    checkout = tmp_path / "checkout"
    output = tmp_path / "output"
    checkout.mkdir()
    output.mkdir()

    command = MODULE.build_analysis_command(case, checkout, output, "cold")

    assert command[0] == "arcade-self-analysis"
    assert command[command.index("--source") + 1] == str(checkout / "sdks")
    assert command[command.index("--languages") + 1] == "java,python,go,typescript"
    assert command[command.index("--exclude-dirs") + 1] == "vendor"
    assert command[command.index("--output-json") + 1] == str(
        output / "cold-analysis.json"
    )
    assert command[command.index("--output-html") + 1] == str(
        output / "cold-analysis.html"
    )


def test_cold_warm_comparison_ignores_timestamp_only(tmp_path):
    base = {
        "timestamp": "cold",
        "repo_name": "fixture",
        "num_entities": 3,
        "num_edges": 2,
        "components": [{"name": "Core"}],
    }
    cold = tmp_path / "cold.json"
    warm = tmp_path / "warm.json"
    cold.write_text(json.dumps(base))
    warm.write_text(json.dumps({**base, "timestamp": "warm"}))

    assert MODULE.compare_runs(cold, warm) == {
        "checked": True,
        "equal": True,
        "different_keys": [],
    }

    warm.write_text(json.dumps({**base, "timestamp": "warm", "num_edges": 3}))
    comparison = MODULE.compare_runs(cold, warm)
    assert comparison["equal"] is False
    assert comparison["different_keys"] == ["num_edges"]


def test_invalid_manifest_rejects_unpinned_ref(tmp_path):
    payload = json.loads(MANIFEST_PATH.read_text())
    payload["cases"][0]["ref"] = "main"
    manifest = tmp_path / "invalid.json"
    manifest.write_text(json.dumps(payload))

    with pytest.raises(MODULE.CaseConfigurationError, match="commit SHA"):
        MODULE.load_cases(manifest)


def test_runner_checks_out_and_analyzes_local_git_fixture(tmp_path):
    upstream = tmp_path / "upstream"
    source = upstream / "src"
    source.mkdir(parents=True)
    (source / "service.py").write_text(
        "class Service:\n"
        "    def run(self) -> None:\n"
        "        return None\n"
    )
    for command in (
        ["git", "init", "--quiet", str(upstream)],
        ["git", "-C", str(upstream), "config", "user.name", "Arcade Test"],
        ["git", "-C", str(upstream), "config", "user.email", "arcade@example.test"],
        ["git", "-C", str(upstream), "add", "src/service.py"],
        ["git", "-C", str(upstream), "commit", "--quiet", "-m", "fixture"],
    ):
        subprocess.run(command, check=True)
    ref = subprocess.run(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    case = MODULE.RealWorldCase(
        id="RW-L99",
        name="Local runner fixture",
        repository=str(upstream),
        ref=ref,
        source_path=".",
        languages=("python",),
        exclude_dirs=(),
        sparse_paths=("src",),
        algorithm="pkg",
        tier="large",
        timeout_minutes=10,
        scheduled=False,
    )
    checkout = tmp_path / "checkout"
    output = tmp_path / "output"
    output.mkdir()

    checkout_seconds = MODULE.checkout_case(case, checkout, output / "checkout.log")
    cold = MODULE.run_analysis(case, checkout, output, "cold")
    warm = MODULE.run_analysis(case, checkout, output, "warm")
    comparison = MODULE.compare_runs(
        output / "cold-analysis.json",
        output / "warm-analysis.json",
    )

    assert checkout_seconds >= 0
    assert cold["status"] == "success"
    assert warm["status"] == "success"
    assert comparison["equal"] is True
    assert MODULE.analysis_summary(output / "cold-analysis.json")["num_entities"] >= 1
    assert (output / "cold-analysis.html").exists()


def test_public_report_contains_reproducible_evidence_and_share_note(tmp_path):
    case = MODULE.load_cases(MANIFEST_PATH)[1]
    result = {
        "case": MODULE.asdict(case),
        "analyzer": {
            "repository": "example/arcade-agent",
            "commit_sha": "a" * 40,
            "ref": "refs/heads/main",
        },
        "status": "success",
        "checkout_seconds": 3.25,
        "runs": [
            {
                "name": "cold",
                "status": "success",
                "elapsed_seconds": 12.5,
                "peak_memory_mb": 256.25,
            },
            {
                "name": "warm",
                "status": "success",
                "elapsed_seconds": 8.5,
                "peak_memory_mb": 240.0,
            },
        ],
        "determinism": {"checked": True, "equal": True, "different_keys": []},
        "error": None,
    }
    analysis = {
        "num_components": 3,
        "num_entities": 120,
        "num_edges": 210,
        "class_count": 20,
        "function_count": 40,
        "method_count": 60,
        "metrics": {"RCI": 0.8, "TurboMQ": 0.7, "BasicMQ": 0.6},
        "derived_metrics": {
            "BalancedArchitectureScore": 0.75,
            "PrincipleAlignmentScore": 0.72,
        },
        "score_drivers": {
            "risks": [
                {"name": "Dependency Direction", "value": 0.4, "gap_to_ideal": 0.6}
            ],
            "strengths": [
                {"name": "Cohesion", "value": 0.9, "gap_to_ideal": 0.1}
            ],
        },
        "smells": [
            {
                "severity": "high",
                "smell_type": "Dependency Cycle",
                "affected_components": ["api", "core"],
                "suggestion": "Invert the dependency.",
            }
        ],
        "components": [
            {
                "name": "core",
                "num_entities": 80,
                "class_count": 10,
                "function_count": 30,
                "method_count": 40,
            }
        ],
    }
    result_path = tmp_path / "result.json"
    analysis_path = tmp_path / "cold-analysis.json"
    report_path = tmp_path / "report.md"
    share_path = tmp_path / "share-comment.md"
    result_path.write_text(json.dumps(result))
    analysis_path.write_text(json.dumps(analysis))

    MODULE.write_report_files(
        result_path,
        output_path=report_path,
        share_output_path=share_path,
        run_url="https://github.com/example/arcade-agent/actions/runs/123",
        upstream_pr_url="https://github.com/grafana/grafana/pull/456",
        campaign_title="Grafana architecture evidence",
    )

    report = report_path.read_text()
    share = share_path.read_text()
    assert "# Grafana architecture evidence" in report
    assert f"/commit/{case.ref}" in report
    assert "https://github.com/example/arcade-agent/commit/" in report
    assert "Balanced Architecture Score | `0.7500`" in report
    assert "Dependency Cycle" in report
    assert "Largest recovered components" in report
    assert "Cold/warm comparison performed: **yes**" in report
    assert "not affiliated with or endorsed" in report
    assert "https://github.com/grafana/grafana/pull/456" in report
    assert "Copy-ready upstream PR note" in report
    assert "Full reproducible CI report and artifacts" in share
    assert "review leads, not confirmed defects" in share


def test_public_report_rejects_non_http_links():
    case = MODULE.load_cases(MANIFEST_PATH)[0]
    result = {
        "case": MODULE.asdict(case),
        "status": "success",
        "runs": [],
        "determinism": {},
    }

    with pytest.raises(MODULE.CaseConfigurationError, match="absolute HTTP"):
        MODULE.render_markdown_report(
            result,
            None,
            run_url="javascript:alert(1)",
        )


def test_workflow_is_manual_and_rotating_not_per_pull_request():
    workflow = WORKFLOW_PATH.read_text()

    assert "workflow_dispatch:" in workflow
    assert "schedule:" in workflow
    assert "pull_request:" not in workflow
    assert "max-parallel: 2" in workflow
    assert "fail-fast: false" in workflow
    assert "timeout-minutes: ${{ matrix.job_timeout_minutes }}" in workflow
    assert "python -m pip install \".[languages]\"" in workflow
    assert "actions/checkout@v7" in workflow
    assert "actions/setup-python@v7" in workflow
    assert "actions/upload-artifact@v7" in workflow
    assert "if: always()" in workflow
    assert "run-name:" in workflow
    assert "campaign-title:" in workflow
    assert "upstream-pr-url:" in workflow
    assert "--share-output \"${SHARE_COMMENT}\"" in workflow
    assert 'cat "${REPORT}" >> "$GITHUB_STEP_SUMMARY"' in workflow
    assert "gh pr comment" not in workflow


def test_catalog_links_executable_manifest_and_runner():
    catalog = (ROOT / "docs" / "real-world-case-catalog.md").read_text()

    assert "docs/real-world-cases.json" in catalog
    assert "scripts/run_real_world_case.py" in catalog
