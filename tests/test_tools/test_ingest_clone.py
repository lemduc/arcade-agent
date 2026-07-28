"""Tests for cleanup() correctness after cloning a remote repo.

Uses ``file://`` URLs against a local git fixture so `_clone_and_ingest` is
exercised for real (via `git clone`) without any network access. `ingest()`
routes to `_clone_and_ingest` whenever `Path(source).is_dir()` is False,
which a `file://` URL satisfies even though the underlying path exists.
"""

import subprocess
from pathlib import Path

from arcade_agent.tools.ingest import ingest


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


def _make_src_layout_repo(root: Path) -> Path:
    """A git repo with a Python `src/` package layout, so ingest narrows path."""
    repo = root / "origin"
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
    return repo


def test_clone_cleanup_removes_the_whole_clone_including_git(tmp_path: Path):
    """cleanup() must delete the entire clone, not just the narrowed `src/`.

    Before the fix, `_clone_and_ingest` set `is_temp=True` but never
    `temp_root`, so when `_build_ingested_repo` narrowed `.path` to the
    detected `src/` source root, `cleanup()` removed only that
    subdirectory and leaked the rest of the clone -- including `.git`.
    """
    origin = _make_src_layout_repo(tmp_path)

    repo = ingest(f"file://{origin}", language="python")
    assert repo.path.name == "src", "sanity: path must be narrowed to src/"
    assert repo.is_temp is True

    clone_root = repo.path.parent  # the cloned repo root, one level above src/
    assert (clone_root / ".git").exists(), "sanity: clone root has .git"

    repo.cleanup()

    assert not clone_root.exists(), "cleanup() leaked the clone outside src/"


def test_clone_cleanup_does_not_delete_a_caller_supplied_work_dir(tmp_path: Path):
    """A caller-supplied `work_dir` must survive cleanup(); only the clone
    inside it may be removed.

    Guards against the unsafe one-liner `temp_root=work_dir`, which would
    make cleanup() rmtree a directory the caller owns and may reuse or
    still have other content in.
    """
    origin = _make_src_layout_repo(tmp_path)

    work_dir = tmp_path / "caller_owned_work_dir"
    work_dir.mkdir()
    sentinel = work_dir / "sentinel.txt"
    sentinel.write_text("do not delete me\n")

    repo = ingest(f"file://{origin}", language="python", work_dir=str(work_dir))
    assert repo.is_temp is True

    clone_root = repo.path.parent  # src/ is narrowed, clone root is its parent
    assert clone_root.parent == work_dir, "sanity: clone landed inside work_dir"

    repo.cleanup()

    assert work_dir.exists(), "cleanup() deleted the caller-supplied work_dir"
    assert sentinel.exists(), "cleanup() deleted unrelated content in work_dir"
    assert not clone_root.exists(), "cleanup() left the clone behind"
