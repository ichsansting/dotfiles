"""Git auto-commit/push wiring. See
.scratch/ephemeral-shell/issues/17-editing-tui-crud.md.

Exercises the real `git` binary against a local working checkout cloned
from a local bare "origin" — the thing worth testing is the stage/commit/
push sequence and its no-op-stays-silent behavior, not git itself.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from dotfiles.core import gitops


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A working checkout with a local bare 'origin' remote, so push has
    somewhere real to land."""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare", "-q", "-b", "main")

    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    (work / "seed.txt").write_text("seed\n")
    _git(work, "add", "seed.txt")
    _git(work, "commit", "-q", "-m", "seed")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


def test_commit_and_push_lands_on_origin(repo: Path):
    (repo / "new.txt").write_text("hello\n")

    gitops.commit_and_push(repo, "test: add new.txt", ["new.txt"])

    log = _git(repo, "log", "-1", "--format=%s").stdout.strip()
    assert log == "test: add new.txt"
    remote_log = _git(repo, "log", "-1", "--format=%s", "origin/main").stdout.strip()
    assert remote_log == "test: add new.txt"


def test_commit_and_push_handles_deletion(repo: Path):
    (repo / "seed.txt").unlink()

    gitops.commit_and_push(repo, "test: remove seed.txt", ["seed.txt"])

    assert not (repo / "seed.txt").exists()
    tracked = _git(repo, "ls-files").stdout
    assert "seed.txt" not in tracked
    remote_tracked = _git(repo, "ls-tree", "-r", "--name-only", "origin/main").stdout
    assert "seed.txt" not in remote_tracked


def test_commit_and_push_noop_stages_nothing(repo: Path):
    before = _git(repo, "log", "-1", "--format=%H").stdout.strip()

    gitops.commit_and_push(repo, "test: noop", ["seed.txt"])  # unchanged content

    after = _git(repo, "log", "-1", "--format=%H").stdout.strip()
    assert before == after


def test_commit_and_push_raises_on_push_failure(repo: Path, tmp_path: Path):
    # Point origin at a nonexistent path so push fails after a real commit.
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "no-such-remote"))
    (repo / "new.txt").write_text("hello\n")

    with pytest.raises(gitops.GitError):
        gitops.commit_and_push(repo, "test: add new.txt", ["new.txt"])

    # The local commit still happened — only the push failed.
    log = _git(repo, "log", "-1", "--format=%s").stdout.strip()
    assert log == "test: add new.txt"
