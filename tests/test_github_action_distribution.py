"""Regression tests for distributable GitHub Actions integration."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPYABLE_WORKFLOW = ROOT / "examples/workflows/arcade-agent-analysis.yml"
ANALYZE_ACTION = ROOT / "actions/analyze/action.yml"


def _package_version() -> str:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return pyproject["project"]["version"]


def test_reusable_workflow_installs_released_package_not_tooling_checkout():
    workflow = (ROOT / ".github/workflows/architecture-analysis-reusable.yml").read_text()
    expected_install_spec = (
        "arcade-agent${{ inputs.install-extras }}==${{ inputs.arcade-agent-version }}"
    )

    assert "arcade-agent-version" in workflow
    assert 'default: "latest"' in workflow
    assert 'if [ "${{ inputs.arcade-agent-version }}" = "latest" ]; then' in workflow
    assert 'python -m pip install "arcade-agent${{ inputs.install-extras }}"' in workflow
    assert "pip install -e" not in workflow
    assert "tooling-repo" not in workflow
    assert "tooling-repository" not in workflow
    assert "tooling-ref" not in workflow
    assert expected_install_spec in workflow
    assert "arcade-self-analysis" in workflow
    assert "arcade-compare-baseline" in workflow
    assert "filter-non-architectural-helpers" in workflow
    assert "default: false" in workflow


def test_self_dogfood_ci_pins_release_package_version():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    version = _package_version()

    assert f'arcade-agent-version: "{version}"' in workflow
    assert "filter-non-architectural-helpers: true" in workflow
    assert "tooling-ref:" not in workflow
    assert "tooling-repository:" not in workflow


def test_readme_documents_copyable_standalone_ci_template():
    readme = (ROOT / "README.md").read_text()
    version = _package_version()

    assert f"uses: lemduc/arcade-agent/actions/analyze@v{version}" in readme
    assert "arcade-agent-version: latest" in readme
    assert f'arcade-agent-version: "{version}"' in readme
    assert "standalone" in readme
    assert "examples/workflows/arcade-agent-analysis.yml" in readme
    assert "Copy `.github/workflows/arch-drift.yml`" not in readme


def test_reusable_workflow_does_not_hardcode_consumer_default_branch():
    workflow = (ROOT / ".github/workflows/architecture-analysis-reusable.yml").read_text()
    readme = (ROOT / "README.md").read_text()

    assert "baseline-branch" in workflow
    assert "BASELINE_BRANCH:" in workflow
    assert "github.event.repository.default_branch" in workflow
    assert "branch: '${{ env.BASELINE_BRANCH }}'" in workflow
    assert "format('refs/heads/{0}', env.BASELINE_BRANCH)" in workflow
    assert "store-baseline-on-push" in workflow
    assert "store-baseline-on-main-push" not in workflow
    assert "branches: [main]" not in readme


def test_reusable_workflow_does_not_hardcode_consumer_workflow_filename():
    workflow = (ROOT / ".github/workflows/architecture-analysis-reusable.yml").read_text()

    assert 'default: ""' in workflow
    assert "listWorkflowRunsForRepo" in workflow
    assert "const baselineWorkflowId = '${{ inputs.baseline-workflow-id }}';" in workflow
    assert 'default: "ci.yml"' not in workflow


def test_legacy_drift_workflow_uses_default_branch_for_baseline_updates():
    workflow = (ROOT / ".github/workflows/arch-drift.yml").read_text()

    assert "github.event.repository.default_branch" in workflow
    assert "refs/heads/main" not in workflow


def test_copyable_workflow_template_is_standalone():
    workflow = COPYABLE_WORKFLOW.read_text()

    assert "workflow_call:" not in workflow
    assert "uses: lemduc/arcade-agent/.github/workflows/" not in workflow
    assert "python -m pip install \"arcade-agent${INSTALL_EXTRAS}\"" in workflow
    assert "arcade-self-analysis" in workflow
    assert "arcade-compare-baseline" in workflow
    assert "github.event.repository.default_branch" in workflow
    assert "listWorkflowRunsForRepo" in workflow
    assert "github.event.pull_request.head.repo.full_name == github.repository" in workflow
    assert "refs/heads/main" not in workflow


def test_analyze_composite_action_provides_short_market_style_api():
    action = ANALYZE_ACTION.read_text()
    readme = (ROOT / "README.md").read_text()
    version = _package_version()

    assert "runs:" in action
    assert "using: composite" in action
    assert "arcade-agent-version:" in action
    assert "source-path:" in action
    assert "baseline-branch:" in action
    assert "python -m pip install \"arcade-agent${INSTALL_EXTRAS}\"" in action
    assert "arcade-self-analysis" in action
    assert "arcade-compare-baseline" in action
    assert "github.event.repository.default_branch" in action
    assert "github.event.pull_request.head.repo.full_name == github.repository" in action
    assert "refs/heads/main" not in action

    assert f"uses: lemduc/arcade-agent/actions/analyze@v{version}" in readme
    assert "arcade-agent-version: latest" in readme
