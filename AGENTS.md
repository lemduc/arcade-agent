# AGENTS.md

## Cursor Cloud specific instructions

`arcade-agent` is a single Python 3.12+ library/CLI product (no long-running services, DB, or web server). The project root is `/workspace` itself — ignore the `cd arcade-agent` line in `CLAUDE.md`, there is no such subdirectory.

### Environment
- Dependencies are installed into a virtualenv at `/workspace/.venv` by the startup update script. Activate it before running anything: `source .venv/bin/activate`. Standard commands (`pytest`, `ruff`, `mypy`, `make ...`) only resolve once the venv is active.
- Creating a venv on this base image requires the `python3.12-venv` system package. It is already installed in the snapshot; the update script only refreshes Python deps.

### Lint / Test / Type-check / Run
Canonical commands live in the `Makefile` and `pyproject.toml`. Notes:
- CI (`.github/workflows/ci.yml`) gates only `ruff check src/ tests/` and `pytest --tb=short`. It installs the full extras: `pip install -e ".[dev,languages,mcp]"`. Install those extras to run the whole suite — without the `[languages]` extra, ~10 language-parser tests are skipped.
- `mypy src/` (`make typecheck`) is NOT gated by CI and currently reports many pre-existing strict-mode errors. Do not treat those as regressions from your changes.
- End-to-end pipeline demo: `python examples/basic_analysis.py <path> --language python -o report.html` (ingest → parse → recover → detect_smells → compute_metrics → visualize). Analyzing `src/arcade_agent` itself is a good smoke test.
- `--use-llm` features need the authenticated `claude` CLI (not installed). Set `ARCADE_MOCK=1` to skip LLM calls when exercising those paths.

### Known flaky test
`tests/test_cache.py::test_cache_key_changes_with_file_modification` fails on this VM because the workspace is on `overlayfs`, whose `st_mtime_ns` granularity is too coarse to distinguish two rapid writes (the cache key hashes `st_mtime_ns`). This is an environment/filesystem limitation, not a code defect — the rest of the suite passes.
