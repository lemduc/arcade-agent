"""Tests for ingesting a specific git ref."""

import subprocess
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
