"""Tests for ingesting a specific git ref."""

import subprocess
import tempfile
from pathlib import Path

import pytest

from arcade_agent.tools.ingest import ingest


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def two_tag_repo(tmp_path: Path) -> Path:
    """A git repo with v1 and v2 tags and different content at each."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("git", "init", "-q", cwd=repo)
    _run("git", "config", "user.email", "t@example.com", cwd=repo)
    _run("git", "config", "user.name", "Test", cwd=repo)

    (repo / "first.py").write_text("class First:\n    pass\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-q", "-m", "first", cwd=repo)
    _run("git", "tag", "v1", cwd=repo)

    (repo / "second.py").write_text("class Second:\n    pass\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-q", "-m", "second", cwd=repo)
    _run("git", "tag", "v2", cwd=repo)
    return repo


def test_ingest_at_ref_sees_only_that_refs_files(two_tag_repo: Path):
    repo = ingest(str(two_tag_repo), language="python", ref="v1")
    names = {p.name for p in repo.source_files}
    assert "first.py" in names
    assert "second.py" not in names
    repo.cleanup()


def test_ingest_at_ref_records_the_ref_as_version(two_tag_repo: Path):
    repo = ingest(str(two_tag_repo), language="python", ref="v1")
    assert repo.version == "v1"
    assert repo.is_temp is True
    repo.cleanup()


def test_ingest_at_ref_does_not_touch_the_working_tree(two_tag_repo: Path):
    before = (two_tag_repo / "second.py").read_text()
    repo = ingest(str(two_tag_repo), language="python", ref="v1")
    repo.cleanup()
    assert (two_tag_repo / "second.py").read_text() == before
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=two_tag_repo, capture_output=True, text=True, check=True,
    )
    assert status.stdout == ""


def test_unknown_ref_raises_with_available_tags(two_tag_repo: Path):
    with pytest.raises(ValueError, match="nope"):
        ingest(str(two_tag_repo), language="python", ref="nope")


def test_ref_on_non_git_directory_raises(tmp_path: Path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("x = 1\n")
    with pytest.raises(ValueError, match="not a git repository"):
        ingest(str(plain), language="python", ref="v1")


def test_ingest_at_ref_cleans_up_extracted_dir_when_local_ingest_fails(
    two_tag_repo: Path,
):
    """A failure after git archive extraction must not strand the temp tree.

    ``ref="v1"`` resolves and extracts fine; the unsupported ``language``
    then makes the downstream local-ingest call raise. The extracted
    directory must be gone afterwards, not just unreferenced.
    """
    tmp_root = Path(tempfile.gettempdir())
    before = set(tmp_root.glob("arcade_agent_ref_*"))

    with pytest.raises(ValueError):
        ingest(str(two_tag_repo), language="bogus-lang", ref="v1")

    after = set(tmp_root.glob("arcade_agent_ref_*"))
    assert after == before, f"leaked temp dirs: {after - before}"


@pytest.fixture
def src_layout_repo(tmp_path: Path) -> Path:
    """A git repo with a Python `src/` package layout, tagged v1."""
    repo = tmp_path / "src_repo"
    repo.mkdir()
    _run("git", "init", "-q", cwd=repo)
    _run("git", "config", "user.email", "t@example.com", cwd=repo)
    _run("git", "config", "user.name", "Test", cwd=repo)

    pkg_dir = repo / "src" / "pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "mod.py").write_text("class Widget:\n    pass\n")
    _run("git", "add", "-A", cwd=repo)
    _run("git", "commit", "-q", "-m", "init", cwd=repo)
    _run("git", "tag", "v1", cwd=repo)
    return repo


def test_ingest_at_ref_keeps_the_narrowed_source_root(src_layout_repo: Path):
    """`path` must stay narrowed to `src/`, not the raw extraction root.

    Narrowing is what lets the Python parser derive `pkg.mod` instead of
    `src.pkg.mod` — the same result a plain (non-ref) ingest of the same
    commit would produce. Overwriting `path` with the extraction root would
    silently break that for every ref-ingested repo with a `src/` layout.
    """
    repo = ingest(str(src_layout_repo), language="python", ref="v1")
    assert repo.path.name == "src"
    repo.cleanup()


def test_ingest_at_ref_produces_the_same_entity_fqns_as_a_plain_ingest(
    src_layout_repo: Path,
):
    """The defect this pins: a ref-ingest must parse to the same FQNs a
    plain ingest of the identical commit would, so that comparing a stored
    baseline (plain ingest) against a ref-ingest doesn't manufacture a
    removed-and-re-added diff for every entity.
    """
    from arcade_agent.tools.parse import parse

    ref_repo = ingest(str(src_layout_repo), language="python", ref="v1")
    ref_graph = parse(
        source_path=str(ref_repo.path),
        language="python",
        files=[str(p) for p in ref_repo.source_files],
        use_cache=False,
    )

    plain_repo = ingest(str(src_layout_repo), language="python")
    plain_graph = parse(
        source_path=str(plain_repo.path),
        language="python",
        files=[str(p) for p in plain_repo.source_files],
        use_cache=False,
    )

    ref_repo.cleanup()
    plain_repo.cleanup()

    ref_fqns = set(ref_graph.entities.keys())
    plain_fqns = set(plain_graph.entities.keys())
    assert ref_fqns == plain_fqns
    assert ref_fqns, "expected at least one parsed entity"
    assert "pkg.mod.Widget" in ref_fqns


def test_ingest_at_ref_cleanup_removes_the_whole_extracted_tree(
    src_layout_repo: Path,
):
    """`cleanup()` must delete the full extraction, not just the narrowed
    `src/` subdirectory `path` points at.
    """
    repo = ingest(str(src_layout_repo), language="python", ref="v1")
    assert repo.temp_root is not None
    assert repo.temp_root != repo.path
    extraction_root = repo.temp_root

    repo.cleanup()

    assert not extraction_root.exists()
