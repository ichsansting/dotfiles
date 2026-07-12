"""Git auto-commit/push wiring for the editing TUI (ticket 17): every
mutating action stages exactly the paths it touched, commits with a
generated message, and pushes immediately — no manual git step, no
batching multiple edits into one commit. See
.scratch/ephemeral-shell/issues/17-editing-tui-crud.md.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    """A git subprocess invocation failed."""


def _run(root: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")


def commit_and_push(root: Path, message: str, paths: list[str]) -> None:
    """Stages `paths` (repo-relative; additions, edits, and deletions all
    handled by explicit `git add`), commits with `message`, and pushes.

    A no-op mutation (e.g. toggling a value back to what it already was)
    stages nothing, so no empty commit is made and nothing is pushed.
    """
    _run(root, "add", "--", *paths)
    staged = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--quiet"]
    )
    if staged.returncode == 0:
        return
    _run(root, "commit", "-m", message)
    try:
        _run(root, "push")
    except GitError as e:
        # The commit already landed locally at this point — say so, since a
        # bare push error reads as if nothing happened. The next successful
        # edit's push carries this commit along too.
        raise GitError(f"{e} (committed locally; will retry on the next edit)") from e
