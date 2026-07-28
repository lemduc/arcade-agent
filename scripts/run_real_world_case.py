#!/usr/bin/env python3
"""Run pinned real-world repository analyses and emit CI-friendly evidence."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Sequence, TextIO
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "real-world-cases.json"
SUPPORTED_LANGUAGES = frozenset({"java", "python", "typescript", "c", "go", "kotlin"})
SUPPORTED_ALGORITHMS = frozenset({"pkg", "acdc", "wca"})
SUPPORTED_TIERS = frozenset({"large", "scale"})
CASE_ID_RE = re.compile(r"^RW-L\d{2}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
GITHUB_REPOSITORY_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?$"
)


class CaseConfigurationError(ValueError):
    """Raised when the executable case manifest is invalid."""


class CaseExecutionError(RuntimeError):
    """Raised when checkout or analysis cannot complete."""


@dataclass(frozen=True)
class RealWorldCase:
    """Validated executable definition for one pinned repository analysis."""

    id: str
    name: str
    repository: str
    ref: str
    source_path: str
    languages: tuple[str, ...]
    exclude_dirs: tuple[str, ...]
    sparse_paths: tuple[str, ...]
    algorithm: str
    tier: str
    timeout_minutes: int
    scheduled: bool

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RealWorldCase:
        case = cls(
            id=_required_string(raw, "id"),
            name=_required_string(raw, "name"),
            repository=_required_string(raw, "repository"),
            ref=_required_string(raw, "ref"),
            source_path=_required_string(raw, "source_path"),
            languages=tuple(_required_string_list(raw, "languages")),
            exclude_dirs=tuple(_required_string_list(raw, "exclude_dirs")),
            sparse_paths=tuple(_required_string_list(raw, "sparse_paths")),
            algorithm=_required_string(raw, "algorithm"),
            tier=_required_string(raw, "tier"),
            timeout_minutes=_required_int(raw, "timeout_minutes"),
            scheduled=_required_bool(raw, "scheduled"),
        )
        case.validate()
        return case

    def validate(self) -> None:
        if not CASE_ID_RE.fullmatch(self.id):
            raise CaseConfigurationError(f"Invalid case id: {self.id!r}")
        if not GITHUB_REPOSITORY_RE.fullmatch(self.repository):
            raise CaseConfigurationError(
                f"{self.id}: repository must be an HTTPS GitHub repository"
            )
        if not SHA_RE.fullmatch(self.ref):
            raise CaseConfigurationError(f"{self.id}: ref must be a 40-character commit SHA")
        if not self.languages or len(set(self.languages)) != len(self.languages):
            raise CaseConfigurationError(f"{self.id}: languages must be non-empty and unique")
        unknown_languages = set(self.languages) - SUPPORTED_LANGUAGES
        if unknown_languages:
            raise CaseConfigurationError(
                f"{self.id}: unsupported languages: {sorted(unknown_languages)}"
            )
        if self.algorithm not in SUPPORTED_ALGORITHMS:
            raise CaseConfigurationError(f"{self.id}: unsupported algorithm {self.algorithm!r}")
        if self.tier not in SUPPORTED_TIERS:
            raise CaseConfigurationError(f"{self.id}: unsupported tier {self.tier!r}")
        if not 10 <= self.timeout_minutes <= 360:
            raise CaseConfigurationError(
                f"{self.id}: timeout_minutes must be between 10 and 360"
            )
        _validate_relative_path(self.id, "source_path", self.source_path, allow_root=True)
        for value in self.exclude_dirs:
            _validate_relative_path(self.id, "exclude_dirs", value, allow_root=False)
        if not self.sparse_paths:
            raise CaseConfigurationError(f"{self.id}: sparse_paths must not be empty")
        for value in self.sparse_paths:
            _validate_relative_path(self.id, "sparse_paths", value, allow_root=False)

    def matrix_entry(self) -> dict[str, Any]:
        return {
            "case_id": self.id,
            "case_name": self.name,
            "tier": self.tier,
            "analysis_timeout_minutes": self.timeout_minutes,
            "job_timeout_minutes": min(self.timeout_minutes + 30, 360),
        }


def _required_string(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CaseConfigurationError(f"{key} must be a non-empty string")
    return value.strip()


def _required_string_list(raw: dict[str, Any], key: str) -> list[str]:
    value = raw.get(key)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise CaseConfigurationError(f"{key} must be a list of non-empty strings")
    return [item.strip() for item in value]


def _required_int(raw: dict[str, Any], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise CaseConfigurationError(f"{key} must be an integer")
    return value


def _required_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise CaseConfigurationError(f"{key} must be a boolean")
    return value


def _validate_relative_path(
    case_id: str,
    field: str,
    value: str,
    *,
    allow_root: bool,
) -> None:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise CaseConfigurationError(f"{case_id}: {field} must stay inside the checkout")
    if not allow_root and normalized in {"", ".", "./"}:
        raise CaseConfigurationError(f"{case_id}: {field} cannot target the checkout root")


def load_cases(manifest_path: Path = DEFAULT_MANIFEST) -> list[RealWorldCase]:
    """Load and validate all cases from the executable manifest."""
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CaseConfigurationError(f"Cannot read manifest {manifest_path}: {exc}") from exc
    if payload.get("schema_version") != 1:
        raise CaseConfigurationError("Unsupported real-world case manifest schema")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise CaseConfigurationError("Manifest cases must be a non-empty list")
    cases = [RealWorldCase.from_dict(raw) for raw in raw_cases]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise CaseConfigurationError("Manifest case ids must be unique")
    return sorted(cases, key=lambda case: case.id)


def select_cases(
    cases: Sequence[RealWorldCase],
    selection: str,
    *,
    rotation_date: date | None = None,
) -> list[RealWorldCase]:
    """Select one, all, or the scheduled weekly rotation case."""
    if selection == "all":
        return list(cases)
    if selection == "scheduled":
        scheduled = [case for case in cases if case.scheduled]
        if not scheduled:
            raise CaseConfigurationError("No cases are enabled for scheduled rotation")
        current_date = rotation_date or datetime.now(timezone.utc).date()
        iso_year, iso_week, _ = current_date.isocalendar()
        index = (iso_year * 53 + iso_week) % len(scheduled)
        return [scheduled[index]]
    try:
        return [next(case for case in cases if case.id == selection)]
    except StopIteration as exc:
        valid = ", ".join(["all", "scheduled", *(case.id for case in cases)])
        raise CaseConfigurationError(
            f"Unknown case selection {selection!r}. Valid values: {valid}"
        ) from exc


def build_analysis_command(
    case: RealWorldCase,
    checkout_dir: Path,
    output_dir: Path,
    run_name: str,
) -> list[str]:
    """Build a shell-free arcade-self-analysis command."""
    source = _resolve_inside(checkout_dir, case.source_path)
    command = [
        "arcade-self-analysis",
        "--source",
        str(source),
        "--algorithm",
        case.algorithm,
        "--repo-name",
        case.repository.removesuffix(".git").rsplit("/", 1)[-1],
        "--output-json",
        str(output_dir / f"{run_name}-analysis.json"),
        "--output-html",
        str(output_dir / f"{run_name}-analysis.html"),
    ]
    if len(case.languages) == 1:
        command.extend(["--language", case.languages[0]])
    else:
        command.extend(["--languages", ",".join(case.languages)])
    if case.exclude_dirs:
        command.extend(["--exclude-dirs", ",".join(case.exclude_dirs)])
    return command


def _resolve_inside(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise CaseConfigurationError(f"Path escapes checkout: {relative!r}")
    return candidate


def _run_git(
    checkout_dir: Path,
    args: Sequence[str],
    log_file: TextIO,
    *,
    timeout_seconds: int,
) -> None:
    command = ["git", "-C", str(checkout_dir), *args]
    log_file.write(f"$ {' '.join(command)}\n")
    log_file.flush()
    completed = subprocess.run(
        command,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise CaseExecutionError(
            f"Git command failed with exit code {completed.returncode}: {' '.join(args)}"
        )


def checkout_case(
    case: RealWorldCase,
    checkout_dir: Path,
    log_path: Path,
) -> float:
    """Create a partial, sparse checkout at the exact pinned commit."""
    started = time.monotonic()
    checkout_dir.mkdir(parents=True)
    checkout_timeout = min(case.timeout_minutes * 60, 30 * 60)
    with log_path.open("w") as log_file:
        _run_git(checkout_dir, ["init", "--quiet"], log_file, timeout_seconds=checkout_timeout)
        _run_git(
            checkout_dir,
            ["remote", "add", "origin", case.repository],
            log_file,
            timeout_seconds=checkout_timeout,
        )
        _run_git(
            checkout_dir,
            ["sparse-checkout", "init", "--cone"],
            log_file,
            timeout_seconds=checkout_timeout,
        )
        _run_git(
            checkout_dir,
            ["sparse-checkout", "set", *case.sparse_paths],
            log_file,
            timeout_seconds=checkout_timeout,
        )
        _run_git(
            checkout_dir,
            [
                "fetch",
                "--depth=1",
                "--filter=blob:none",
                "--no-tags",
                "origin",
                case.ref,
            ],
            log_file,
            timeout_seconds=checkout_timeout,
        )
        _run_git(
            checkout_dir,
            ["checkout", "--detach", "FETCH_HEAD"],
            log_file,
            timeout_seconds=checkout_timeout,
        )
        actual_ref = subprocess.run(
            ["git", "-C", str(checkout_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout.strip()
        if actual_ref != case.ref:
            raise CaseExecutionError(
                f"Checkout mismatch for {case.id}: expected {case.ref}, got {actual_ref}"
            )
    return round(time.monotonic() - started, 3)


def _timed_command(command: Sequence[str], metrics_path: Path) -> list[str]:
    if sys.platform.startswith("linux") and Path("/usr/bin/time").exists():
        return ["/usr/bin/time", "-v", "-o", str(metrics_path), *command]
    return list(command)


def _terminate_process_group(process: subprocess.Popen[Any]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def _parse_peak_memory_mb(metrics_path: Path) -> float | None:
    if not metrics_path.exists():
        return None
    prefix = "Maximum resident set size (kbytes):"
    for line in metrics_path.read_text().splitlines():
        if line.strip().startswith(prefix):
            raw_value = line.split(":", 1)[1].strip()
            try:
                return round(int(raw_value) / 1024, 3)
            except ValueError:
                return None
    return None


def run_analysis(
    case: RealWorldCase,
    checkout_dir: Path,
    output_dir: Path,
    run_name: str,
) -> dict[str, Any]:
    """Run one cold or warm analysis and preserve logs even on failure."""
    command = build_analysis_command(case, checkout_dir, output_dir, run_name)
    log_path = output_dir / f"{run_name}.log"
    metrics_path = output_dir / f"{run_name}-time.txt"
    environment = os.environ.copy()
    environment["GITHUB_SHA"] = case.ref
    environment["GITHUB_REF"] = f"refs/arcade-real-world/{case.id}"
    started = time.monotonic()
    timed_out = False
    with log_path.open("w") as log_file:
        log_file.write(f"$ {' '.join(command)}\n")
        log_file.flush()
        process = subprocess.Popen(
            _timed_command(command, metrics_path),
            cwd=checkout_dir,
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            return_code = process.wait(timeout=case.timeout_minutes * 60)
        except subprocess.TimeoutExpired:
            timed_out = True
            _terminate_process_group(process)
            return_code = process.returncode if process.returncode is not None else -1

    json_path = output_dir / f"{run_name}-analysis.json"
    html_path = output_dir / f"{run_name}-analysis.html"
    status = "timeout" if timed_out else ("success" if return_code == 0 else "failure")
    if status == "success" and (not json_path.exists() or not html_path.exists()):
        status = "failure"
    return {
        "name": run_name,
        "status": status,
        "exit_code": return_code,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_memory_mb": _parse_peak_memory_mb(metrics_path),
        "command": command,
        "outputs": {
            "json": json_path.name if json_path.exists() else None,
            "html": html_path.name if html_path.exists() else None,
            "log": log_path.name,
            "time": metrics_path.name if metrics_path.exists() else None,
        },
    }


def _load_analysis(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CaseExecutionError(f"Cannot read analysis output {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CaseExecutionError(f"Analysis output {path} is not a JSON object")
    return payload


def _stable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if key not in {"timestamp"}
    }


def compare_runs(cold_path: Path, warm_path: Path) -> dict[str, Any]:
    """Compare stable top-level output fields from cold and warm runs."""
    cold = _stable_payload(_load_analysis(cold_path))
    warm = _stable_payload(_load_analysis(warm_path))
    keys = sorted(set(cold) | set(warm))
    different_keys = [key for key in keys if cold.get(key) != warm.get(key)]
    return {
        "checked": True,
        "equal": not different_keys,
        "different_keys": different_keys,
    }


def analysis_summary(path: Path) -> dict[str, Any]:
    payload = _load_analysis(path)
    return {
        key: payload.get(key)
        for key in (
            "repo_name",
            "commit_sha",
            "language",
            "languages",
            "algorithm",
            "num_components",
            "num_entities",
            "num_edges",
            "source_num_entities",
            "class_count",
            "function_count",
            "method_count",
            "entity_kind_counts",
        )
    }


def _markdown_text(value: object, *, limit: int | None = None) -> str:
    """Render untrusted text as a single safe Markdown fragment."""
    text = " ".join(str(value).split())
    if limit is not None and len(text) > limit:
        text = text[: max(limit - 1, 0)].rstrip() + "…"
    return html.escape(text, quote=False).replace("|", r"\|")


def _safe_web_url(value: str | None) -> str | None:
    """Accept only absolute HTTP(S) URLs for links in public reports."""
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CaseConfigurationError(f"Report URL must be absolute HTTP(S): {value!r}")
    return value


def _format_value(value: object, *, digits: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return _markdown_text(value)


def _numeric_metric(
    payload: dict[str, Any],
    section: str,
    name: str,
) -> float | None:
    values = payload.get(section)
    if not isinstance(values, dict):
        return None
    value = values.get(name)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _repository_url(case: dict[str, Any]) -> str | None:
    repository = case.get("repository")
    if not isinstance(repository, str):
        return None
    return _safe_web_url(repository.removesuffix(".git"))


def _commit_url(case: dict[str, Any]) -> str | None:
    repository = _repository_url(case)
    ref = case.get("ref")
    if repository is None or not isinstance(ref, str) or not SHA_RE.fullmatch(ref):
        return None
    return f"{repository}/commit/{ref}"


def _analyzer_commit_link(result: dict[str, Any]) -> str | None:
    analyzer = result.get("analyzer")
    if not isinstance(analyzer, dict):
        return None
    repository = analyzer.get("repository")
    commit_sha = analyzer.get("commit_sha")
    if (
        not isinstance(repository, str)
        or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
        or not isinstance(commit_sha, str)
        or not SHA_RE.fullmatch(commit_sha)
    ):
        return None
    url = f"https://github.com/{repository}/commit/{commit_sha}"
    return f"[`{commit_sha[:12]}`]({url})"


def _report_metric_rows(analysis: dict[str, Any]) -> list[tuple[str, object]]:
    return [
        (
            "Balanced Architecture Score",
            _numeric_metric(analysis, "derived_metrics", "BalancedArchitectureScore"),
        ),
        (
            "Principle Alignment",
            _numeric_metric(analysis, "derived_metrics", "PrincipleAlignmentScore"),
        ),
        ("RCI", _numeric_metric(analysis, "metrics", "RCI")),
        ("TurboMQ", _numeric_metric(analysis, "metrics", "TurboMQ")),
        ("BasicMQ", _numeric_metric(analysis, "metrics", "BasicMQ")),
        (
            "Inter-connectivity",
            _numeric_metric(analysis, "metrics", "InterConnectivity"),
        ),
        (
            "Two-way pair ratio",
            _numeric_metric(analysis, "metrics", "TwoWayPairRatio"),
        ),
    ]


def _render_score_drivers(analysis: dict[str, Any]) -> list[str]:
    drivers = analysis.get("score_drivers")
    if not isinstance(drivers, dict):
        return []
    lines = ["## Score drivers", ""]
    found = False
    for label, key in (("Biggest review leads", "risks"), ("Strongest signals", "strengths")):
        entries = drivers.get(key)
        if not isinstance(entries, list) or not entries:
            continue
        found = True
        lines.extend([f"### {label}", ""])
        for entry in entries[:5]:
            if not isinstance(entry, dict):
                continue
            name = _markdown_text(entry.get("name", "unknown"))
            value = _format_value(entry.get("value"))
            gap = _format_value(entry.get("gap_to_ideal"))
            lines.append(f"- **{name}** — signal `{value}`, gap to ideal `{gap}`")
        lines.append("")
    return lines if found else []


def _render_components(analysis: dict[str, Any]) -> list[str]:
    components = analysis.get("components")
    if not isinstance(components, list) or not components:
        return []
    valid_components = [item for item in components if isinstance(item, dict)]

    def entity_count(item: dict[str, Any]) -> int:
        value = item.get("num_entities")
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    valid_components.sort(
        key=lambda item: (
            -entity_count(item),
            str(item.get("name", "")),
        )
    )
    lines = [
        "## Largest recovered components",
        "",
        "| Component | Entities | Classes | Functions | Methods |",
        "|---|---:|---:|---:|---:|",
    ]
    for component in valid_components[:15]:
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_text(component.get("name", "unknown"), limit=80),
                    _format_value(component.get("num_entities")),
                    _format_value(component.get("class_count")),
                    _format_value(component.get("function_count")),
                    _format_value(component.get("method_count")),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"_Showing {min(len(valid_components), 15)} of "
            f"{len(valid_components)} recovered components._",
            "",
        ]
    )
    return lines


def _render_smells(analysis: dict[str, Any]) -> list[str]:
    smells = analysis.get("smells")
    if not isinstance(smells, list):
        return []
    valid_smells = [item for item in smells if isinstance(item, dict)]
    lines = ["## Architectural review leads", ""]
    if not valid_smells:
        lines.extend(["No architectural smells were detected in this snapshot.", ""])
        return lines
    severity_order = {"high": 0, "medium": 1, "low": 2}
    valid_smells.sort(
        key=lambda item: (
            severity_order.get(str(item.get("severity", "")).lower(), 3),
            str(item.get("smell_type", "")),
        )
    )
    counts: dict[str, int] = {}
    for smell in valid_smells:
        severity = str(smell.get("severity", "unknown")).lower()
        counts[severity] = counts.get(severity, 0) + 1
    count_summary = ", ".join(
        f"{severity}: {count}"
        for severity, count in sorted(
            counts.items(), key=lambda item: severity_order.get(item[0], 3)
        )
    )
    lines.extend(
        [
            f"Detected **{len(valid_smells)}** "
            f"{'review lead' if len(valid_smells) == 1 else 'review leads'} "
            f"({_markdown_text(count_summary)}).",
            "",
            "| Severity | Type | Affected components | Suggested direction |",
            "|---|---|---|---|",
        ]
    )
    for smell in valid_smells[:20]:
        affected = smell.get("affected_components")
        component_text = (
            ", ".join(str(item) for item in affected)
            if isinstance(affected, list)
            else "—"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    _markdown_text(smell.get("severity", "unknown")),
                    _markdown_text(smell.get("smell_type", "unknown"), limit=80),
                    _markdown_text(component_text, limit=160),
                    _markdown_text(smell.get("suggestion", "—"), limit=240),
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            f"_Showing {min(len(valid_smells), 20)} of {len(valid_smells)} leads. "
            "Inspect the JSON and HTML artifacts for full details._",
            "",
        ]
    )
    return lines


def render_share_comment(
    result: dict[str, Any],
    analysis: dict[str, Any] | None,
    *,
    run_url: str | None = None,
) -> str:
    """Build a concise, paste-ready note for an upstream pull request."""
    case = result.get("case")
    case = case if isinstance(case, dict) else {}
    case_name = _markdown_text(case.get("name", case.get("id", "real-world case")))
    ref = _markdown_text(str(case.get("ref", "unknown"))[:12])
    status = _markdown_text(result.get("status", "unknown"))
    run_url = _safe_web_url(run_url)

    lines = [
        "### Independent architecture evidence",
        "",
        f"I ran **arcade-agent** independently against **{case_name}** at "
        f"pinned commit `{ref}` as supporting context for this focused change.",
        "",
    ]
    if analysis:
        balanced = _numeric_metric(
            analysis, "derived_metrics", "BalancedArchitectureScore"
        )
        smells = analysis.get("smells")
        smell_count = len(smells) if isinstance(smells, list) else 0
        smell_label = (
            "architectural review lead"
            if smell_count == 1
            else "architectural review leads"
        )
        lines.append(
            f"Snapshot: `{_format_value(analysis.get('num_entities'))}` entities, "
            f"`{_format_value(analysis.get('num_edges'))}` dependency edges, "
            f"`{_format_value(analysis.get('num_components'))}` recovered components, "
            f"`{smell_count}` {smell_label}"
            + (
                f", Balanced Architecture Score `{_format_value(balanced)}`."
                if balanced is not None
                else "."
            )
        )
    else:
        lines.append(f"The analysis run finished with status **{status}**.")
    lines.append("")
    if run_url:
        lines.append(f"Full reproducible CI report and artifacts: [view run]({run_url})")
        lines.append("")
    lines.append(
        "_This is an independent, advisory snapshot—not an upstream endorsement. "
        "Findings are review leads, not confirmed defects._"
    )
    return "\n".join(lines) + "\n"


def render_markdown_report(
    result: dict[str, Any],
    analysis: dict[str, Any] | None,
    *,
    run_url: str | None = None,
    upstream_pr_url: str | None = None,
    campaign_title: str | None = None,
) -> str:
    """Render a public, reproducible GitHub Actions evidence report."""
    case = result.get("case")
    case = case if isinstance(case, dict) else {}
    title = _markdown_text(
        campaign_title or "Independent Real-World Architecture Analysis",
        limit=140,
    )
    case_id = _markdown_text(case.get("id", "unknown case"))
    case_name = _markdown_text(case.get("name", "unknown repository"), limit=140)
    status = _markdown_text(result.get("status", "unknown"))
    repository_url = _repository_url(case)
    commit_url = _commit_url(case)
    run_url = _safe_web_url(run_url)
    upstream_pr_url = _safe_web_url(upstream_pr_url)
    analyzer_commit_link = _analyzer_commit_link(result)
    languages = case.get("languages")
    language_text = (
        ", ".join(str(language) for language in languages)
        if isinstance(languages, (list, tuple))
        else "unknown"
    )

    target_link = (
        f"[{case_name}]({repository_url})" if repository_url else case_name
    )
    ref = str(case.get("ref", "unknown"))
    commit_link = (
        f"[`{_markdown_text(ref[:12])}`]({commit_url})"
        if commit_url
        else f"`{_markdown_text(ref[:12])}`"
    )
    lines = [
        f"# {title}",
        "",
        f"## {case_id} — {case_name}",
        "",
        "> Independent snapshot generated by **arcade-agent** against an immutable "
        "upstream commit. This report is not affiliated with or endorsed by the "
        "upstream maintainers. Findings are advisory review leads, not confirmed defects.",
        "",
        "| Evidence | Value |",
        "|---|---|",
        f"| Status | **{status}** |",
        f"| Target | {target_link} |",
        f"| Pinned commit | {commit_link} |",
        f"| Source scope | `{_markdown_text(case.get('source_path', '.'))}` |",
        f"| Languages | `{_markdown_text(language_text)}` |",
        f"| Recovery algorithm | `{_markdown_text(case.get('algorithm', 'unknown'))}` |",
        f"| Checkout time | `{_format_value(result.get('checkout_seconds'), digits=3)} s` |",
    ]
    if run_url:
        lines.append(f"| Public CI evidence | [GitHub Actions run]({run_url}) |")
    if analyzer_commit_link:
        lines.append(f"| Analyzer source | {analyzer_commit_link} |")
    if upstream_pr_url:
        lines.append(f"| Related upstream PR | [Open pull request]({upstream_pr_url}) |")
    lines.append("")

    error = result.get("error")
    if error:
        lines.extend(
            [
                "## Execution diagnostic",
                "",
                f"> **{_markdown_text(error, limit=1000)}**",
                "",
                "The logs and partial artifacts are retained so this infrastructure "
                "or analysis failure remains reproducible.",
                "",
            ]
        )

    if analysis:
        lines.extend(
            [
                "## Snapshot overview",
                "",
                "| Components | Entities | Edges | Classes | Functions | Methods |",
                "|---:|---:|---:|---:|---:|---:|",
                "| "
                + " | ".join(
                    _format_value(analysis.get(key))
                    for key in (
                        "num_components",
                        "num_entities",
                        "num_edges",
                        "class_count",
                        "function_count",
                        "method_count",
                    )
                )
                + " |",
                "",
                "## Architecture quality signals",
                "",
                "| Metric | Value |",
                "|---|---:|",
            ]
        )
        for name, value in _report_metric_rows(analysis):
            lines.append(f"| {_markdown_text(name)} | `{_format_value(value)}` |")
        lines.extend(
            [
                "",
                "> Scores are workload-specific signals. They are useful for pinned "
                "baselines and focused before/after comparisons; no absolute score is "
                "treated as a universal quality gate.",
                "",
            ]
        )
        lines.extend(_render_score_drivers(analysis))
        lines.extend(_render_smells(analysis))
        lines.extend(_render_components(analysis))
    else:
        lines.extend(
            [
                "## Snapshot overview",
                "",
                "No valid analysis JSON was produced. Inspect the checkout and run logs "
                "in the attached artifact.",
                "",
            ]
        )

    runs = result.get("runs")
    if isinstance(runs, list):
        lines.extend(
            [
                "## Runtime evidence",
                "",
                "| Pass | Status | Elapsed | Peak RSS |",
                "|---|---|---:|---:|",
            ]
        )
        for run in runs:
            if not isinstance(run, dict):
                continue
            memory = run.get("peak_memory_mb")
            memory_text = (
                f"{_format_value(memory, digits=3)} MiB" if memory is not None else "—"
            )
            lines.append(
                f"| {_markdown_text(run.get('name', 'unknown'))} | "
                f"{_markdown_text(run.get('status', 'unknown'))} | "
                f"{_format_value(run.get('elapsed_seconds'), digits=3)} s | "
                f"{memory_text} |"
            )
        determinism = result.get("determinism")
        determinism = determinism if isinstance(determinism, dict) else {}
        lines.extend(
            [
                "",
                f"- Cold/warm comparison performed: "
                f"**{_format_value(determinism.get('checked'))}**",
                f"- Stable outputs equal: **{_format_value(determinism.get('equal'))}**",
                "",
            ]
        )

    lines.extend(
        [
            "## Reproduce",
            "",
            "```bash",
            "python scripts/run_real_world_case.py run \\",
            f"  --case {_markdown_text(case.get('id', 'RW-LXX'))} \\",
            f"  --output-dir real-world-results/{_markdown_text(case.get('id', 'RW-LXX'))}",
            "```",
            "",
            "The case manifest pins repository URL, commit SHA, source scope, language "
            "set, exclusions, algorithm, and timeout. The complete JSON, interactive "
            "HTML, logs, timing data, this report, and a share-ready PR note are retained "
            "as workflow artifacts.",
            "",
            "<details>",
            "<summary>Copy-ready upstream PR note</summary>",
            "",
            "```markdown",
            render_share_comment(result, analysis, run_url=run_url).rstrip(),
            "```",
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)


def write_report_files(
    result_path: Path,
    *,
    output_path: Path,
    share_output_path: Path,
    run_url: str | None = None,
    upstream_pr_url: str | None = None,
    campaign_title: str | None = None,
) -> None:
    """Load runner evidence and write the public report plus PR comment."""
    result = _load_analysis(result_path)
    cold_path = result_path.parent / "cold-analysis.json"
    analysis = _load_analysis(cold_path) if cold_path.exists() else None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    share_output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_markdown_report(
            result,
            analysis,
            run_url=run_url,
            upstream_pr_url=upstream_pr_url,
            campaign_title=campaign_title,
        )
    )
    share_output_path.write_text(
        render_share_comment(result, analysis, run_url=run_url)
    )


def run_case(
    case: RealWorldCase,
    output_dir: Path,
    *,
    run_warm: bool = True,
) -> int:
    """Checkout and analyze one case, always writing result.json."""
    output_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "schema_version": 1,
        "case": asdict(case),
        "analyzer": {
            "repository": os.environ.get("GITHUB_REPOSITORY"),
            "commit_sha": os.environ.get("GITHUB_SHA"),
            "ref": os.environ.get("GITHUB_REF"),
        },
        "status": "running",
        "started_at": started_at.isoformat(),
        "completed_at": None,
        "checkout_seconds": None,
        "runs": [],
        "determinism": {"checked": False, "equal": None, "different_keys": []},
        "analysis_summary": None,
        "error": None,
    }
    result_path = output_dir / "result.json"
    exit_code = 1

    try:
        with tempfile.TemporaryDirectory(prefix=f"arcade-{case.id.lower()}-") as temp_dir:
            checkout_dir = Path(temp_dir) / "target"
            result["checkout_seconds"] = checkout_case(
                case,
                checkout_dir,
                output_dir / "checkout.log",
            )
            source_dir = _resolve_inside(checkout_dir, case.source_path)
            cache_dir = source_dir / ".arcade-cache"
            if cache_dir.exists():
                shutil.rmtree(cache_dir)

            cold = run_analysis(case, checkout_dir, output_dir, "cold")
            result["runs"].append(cold)
            if cold["status"] != "success":
                raise CaseExecutionError(f"Cold analysis ended with status {cold['status']}")

            cold_path = output_dir / "cold-analysis.json"
            result["analysis_summary"] = analysis_summary(cold_path)

            if run_warm:
                warm = run_analysis(case, checkout_dir, output_dir, "warm")
                result["runs"].append(warm)
                if warm["status"] != "success":
                    raise CaseExecutionError(f"Warm analysis ended with status {warm['status']}")
                result["determinism"] = compare_runs(
                    cold_path,
                    output_dir / "warm-analysis.json",
                )
                if not result["determinism"]["equal"]:
                    changed = ", ".join(result["determinism"]["different_keys"])
                    raise CaseExecutionError(
                        f"Cold/warm output mismatch in stable fields: {changed}"
                    )

            result["status"] = "success"
            exit_code = 0
    except (CaseConfigurationError, CaseExecutionError, OSError, subprocess.SubprocessError) as exc:
        result["status"] = "failure"
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        result["completed_at"] = datetime.now(timezone.utc).isoformat()
        result_path.write_text(json.dumps(result, indent=2, default=str) + "\n")

    return exit_code


def _parse_rotation_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CaseConfigurationError("--date must use YYYY-MM-DD") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run pinned real-world arcade-agent acceptance cases"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help=f"Executable case manifest (default: {DEFAULT_MANIFEST})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List validated cases")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON")

    matrix_parser = subparsers.add_parser("matrix", help="Emit a GitHub Actions matrix")
    matrix_parser.add_argument(
        "--selection",
        default="scheduled",
        help="Case id, 'all', or 'scheduled'",
    )
    matrix_parser.add_argument(
        "--date",
        help="UTC rotation date override in YYYY-MM-DD format",
    )

    run_parser = subparsers.add_parser("run", help="Run one pinned case")
    run_parser.add_argument("--case", required=True, help="Case id")
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for result, logs, JSON, and HTML artifacts",
    )
    run_parser.add_argument(
        "--skip-warm",
        action="store_true",
        help="Skip the warm-cache determinism run",
    )

    report_parser = subparsers.add_parser(
        "report",
        help="Render a public CI report from one case result",
    )
    report_parser.add_argument("--result", type=Path, required=True)
    report_parser.add_argument("--output", type=Path, required=True)
    report_parser.add_argument("--share-output", type=Path, required=True)
    report_parser.add_argument("--run-url")
    report_parser.add_argument("--upstream-pr-url")
    report_parser.add_argument("--campaign-title")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "report":
            write_report_files(
                args.result.resolve(),
                output_path=args.output.resolve(),
                share_output_path=args.share_output.resolve(),
                run_url=args.run_url,
                upstream_pr_url=args.upstream_pr_url,
                campaign_title=args.campaign_title,
            )
            return 0
        cases = load_cases(args.manifest)
        if args.command == "list":
            if args.json:
                print(json.dumps([asdict(case) for case in cases], indent=2))
            else:
                for case in cases:
                    languages = ",".join(case.languages)
                    print(
                        f"{case.id}\t{case.tier}\t{case.timeout_minutes}m\t"
                        f"{languages}\t{case.name}"
                    )
            return 0
        if args.command == "matrix":
            selected = select_cases(
                cases,
                args.selection,
                rotation_date=_parse_rotation_date(args.date),
            )
            print(json.dumps({"include": [case.matrix_entry() for case in selected]}))
            return 0
        if args.command == "run":
            selected = select_cases(cases, args.case)
            return run_case(
                selected[0],
                args.output_dir.resolve(),
                run_warm=not args.skip_warm,
            )
    except (CaseConfigurationError, CaseExecutionError) as exc:
        parser.error(str(exc))
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
