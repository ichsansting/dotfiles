"""Composed files: one $HOME target assembled from fragments contributed by
multiple modules (files.partition_targets / compose / deploy_fragments)."""
from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles import activate
from dotfiles.core import files, state
from dotfiles.core import manifest as mf
from dotfiles.core.sops import encrypt


@pytest.fixture
def git(repo: Path) -> Path:
    return repo / "modules" / "git"


@pytest.fixture
def shell(repo: Path) -> Path:
    return repo / "modules" / "shell"


def _track(
    module_dir: Path,
    rel: str,
    content: str,
    *,
    fragment: bool = True,
    order: int = mf.DEFAULT_ORDER,
    child: str | None = None,
) -> None:
    storage = module_dir / "files" / rel
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text(content)
    specs = mf.load(module_dir) + [
        mf.FileSpec(rel, mf.MODE_PLAIN, child=child, fragment=fragment, order=order)
    ]
    mf.save(module_dir, specs)


def _targets(*modules: Path | tuple[Path, set[str]]) -> dict[str, list[files.Fragment]]:
    pairs = [(m, set()) if isinstance(m, Path) else m for m in modules]
    targets, errors = files.partition_targets(pairs)
    assert errors == []
    return targets


# -- partition_targets -------------------------------------------------------

def test_partition_groups_by_path(git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "from git\n")
    _track(shell, ".claude/CLAUDE.md", "from shell\n")
    _track(git, ".gitconfig", "cfg\n", fragment=False)

    targets = _targets(git, shell)
    assert set(targets) == {".claude/CLAUDE.md"}
    assert sorted(f.module for f in targets[".claude/CLAUDE.md"]) == ["git", "shell"]


def test_partition_rejects_whole_plus_fragment(git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "whole\n", fragment=False)
    _track(shell, ".claude/CLAUDE.md", "frag\n")
    _, errors = files.partition_targets([(git, set()), (shell, set())])
    assert len(errors) == 1
    assert "pick one style" in errors[0]


def test_partition_rejects_two_whole_owners(git: Path, shell: Path):
    _track(git, ".gitconfig", "a\n", fragment=False)
    _track(shell, ".gitconfig", "b\n", fragment=False)
    _, errors = files.partition_targets([(git, set()), (shell, set())])
    assert len(errors) == 1
    assert "multiple modules" in errors[0]


def test_partition_respects_disabled_children(git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n", order=10)
    _track(shell, ".claude/CLAUDE.md", "extra\n", order=50, child="fish")

    targets = _targets(git, (shell, {"fish"}))
    assert [f.module for f in targets[".claude/CLAUDE.md"]] == ["git"]


# -- compose -----------------------------------------------------------------

def test_compose_orders_by_order_then_module(git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "second\n", order=50)
    _track(shell, ".claude/CLAUDE.md", "first\n", order=10)
    frags = _targets(git, shell)[".claude/CLAUDE.md"]
    assert files.compose(frags) == b"first\n\nsecond\n"

    # equal orders -> module name breaks the tie (git < shell)
    for m in (git, shell):
        mf.save(m, [])
    _track(git, ".claude/CLAUDE.md", "from git\n")
    _track(shell, ".claude/CLAUDE.md", "from shell\n")
    frags = _targets(git, shell)[".claude/CLAUDE.md"]
    assert files.compose(frags) == b"from git\n\nfrom shell\n"


def test_compose_normalizes_newlines_and_drops_empty(git: Path, shell: Path, repo: Path):
    third = repo / "modules" / "aaa"
    third.mkdir()
    (third / "default.nix").write_text("{ }\n")
    (third / "module.json").write_text('{"description": "x", "children": {}}\n')

    _track(git, ".claude/CLAUDE.md", "a\n\n\n", order=10)     # extra newlines trimmed
    _track(shell, ".claude/CLAUDE.md", "b", order=20)         # missing newline added
    _track(third, ".claude/CLAUDE.md", "", order=30)          # empty block dropped
    frags = _targets(git, shell, third)[".claude/CLAUDE.md"]
    assert files.compose(frags) == b"a\n\nb\n"


# -- deploy_fragments --------------------------------------------------------

def test_deploy_writes_composed_and_records_state(home: Path, git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n", order=10)
    _track(shell, ".claude/CLAUDE.md", "work\n", order=50)
    files.deploy_fragments(_targets(git, shell))

    dest = home / ".claude/CLAUDE.md"
    assert dest.read_text() == "base\n\nwork\n"
    entry = state.load()[".claude/CLAUDE.md"]
    assert entry.module == "git+shell"
    assert entry.mode == mf.MODE_PLAIN
    assert entry.sha256 == state.digest(b"base\n\nwork\n")


def test_deploy_anti_clobber_user_edit(home: Path, git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n")
    _track(shell, ".claude/CLAUDE.md", "work\n")
    targets = _targets(git, shell)
    files.deploy_fragments(targets)

    (home / ".claude/CLAUDE.md").write_text("my edits\n")
    (git / "files/.claude/CLAUDE.md").write_text("base v2\n")
    with pytest.raises(RuntimeError, match="Conflicts"):
        files.deploy_fragments(targets)
    assert (home / ".claude/CLAUDE.md").read_text() == "my edits\n"

    files.deploy_fragments(targets, overwrite=True)
    assert (home / ".claude/CLAUDE.md").read_text() == "base v2\n\nwork\n"


def test_deploy_rewrites_when_expectation_changes(home: Path, git: Path, shell: Path):
    """Contributor set shrinks: still exactly what we deployed -> silent rewrite."""
    _track(git, ".claude/CLAUDE.md", "base\n", order=10)
    _track(shell, ".claude/CLAUDE.md", "work\n", order=50)
    files.deploy_fragments(_targets(git, shell))

    # shell module disabled -> only git contributes now
    files.deploy_fragments(_targets(git))
    assert (home / ".claude/CLAUDE.md").read_text() == "base\n"
    assert state.load()[".claude/CLAUDE.md"].module == "git"

    # path is still desired while one contributor remains
    assert ".claude/CLAUDE.md" in files.desired_paths([(git, set())])


def test_prune_removes_composed_after_last_contributor(home: Path, git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n")
    files.deploy_fragments(_targets(git))
    assert (home / ".claude/CLAUDE.md").exists()

    files.prune(files.desired_paths([]))
    assert not (home / ".claude/CLAUDE.md").exists()
    assert ".claude/CLAUDE.md" not in state.load()


def test_whole_file_to_fragment_migration(home: Path, git: Path, shell: Path):
    """A path previously deployed whole-file converts without a false conflict."""
    _track(git, ".claude/CLAUDE.md", "base\n", fragment=False)
    files.deploy_module(git)
    assert (home / ".claude/CLAUDE.md").read_text() == "base\n"

    mf.save(git, [mf.FileSpec(".claude/CLAUDE.md", mf.MODE_PLAIN, fragment=True, order=10)])
    _track(shell, ".claude/CLAUDE.md", "work\n", order=50)
    files.deploy_fragments(_targets(git, shell))
    assert (home / ".claude/CLAUDE.md").read_text() == "base\n\nwork\n"


def test_secret_fragment_skips_whole_target(home: Path, git: Path, shell: Path, capsys):
    _track(git, ".config/env.fish", "plain block\n", order=10)
    storage = shell / "files/.config/env.fish.sops.yaml"
    storage.parent.mkdir(parents=True)
    storage.write_text("env.fish: ENC[...]\n")
    mf.save(shell, [mf.FileSpec(".config/env.fish", mf.MODE_SECRET, fragment=True, order=50)])

    files.deploy_fragments(_targets(git, shell), skip_secrets=True)
    assert not (home / ".config/env.fish").exists()  # never a partial composition
    assert "skipped composed .config/env.fish" in capsys.readouterr().out
    assert ".config/env.fish" not in state.load()


def test_mixed_plain_and_secret_fragments(
    home: Path, git: Path, shell: Path, sops_bin: str, age_key, monkeypatch
):
    monkeypatch.chdir(git.parent.parent)  # .sops.yaml written by the fixture's cwd
    monkeypatch.setenv("DOTFILES_SOPS_BIN", sops_bin)
    _track(git, ".config/env.fish", "set -x PLAIN 1\n", order=10)
    storage = shell / "files/.config/env.fish.sops.yaml"
    storage.parent.mkdir(parents=True)
    spec = mf.FileSpec(".config/env.fish", mf.MODE_SECRET, fragment=True, order=50)
    encrypt(b"set -x SECRET 2\n", storage, mf.secret_key_name(spec), sops_bin)
    mf.save(shell, [spec])

    files.deploy_fragments(_targets(git, shell), sops_bin=sops_bin)
    assert (home / ".config/env.fish").read_text() == "set -x PLAIN 1\n\nset -x SECRET 2\n"
    assert state.load()[".config/env.fish"].mode == mf.MODE_SECRET


# -- guards on whole-file operations ----------------------------------------

def test_deploy_and_clean_module_skip_fragments(home: Path, git: Path, capsys):
    _track(git, ".claude/CLAUDE.md", "frag\n")
    _track(git, ".gitconfig", "cfg\n", fragment=False)

    files.deploy_module(git)
    assert (home / ".gitconfig").exists()
    assert not (home / ".claude/CLAUDE.md").exists()
    assert "skipped fragment .claude/CLAUDE.md" in capsys.readouterr().out

    files.deploy_fragments(_targets(git))
    files.clean_module(git)
    assert not (home / ".gitconfig").exists()
    assert (home / ".claude/CLAUDE.md").exists()  # other modules may contribute


def test_sync_and_deploy_one_reject_fragments(home: Path, git: Path):
    _track(git, ".claude/CLAUDE.md", "frag\n")
    (frag,) = _targets(git)[".claude/CLAUDE.md"]
    entry = files.FileEntry(frag.module, frag.spec, frag.storage, files.MISSING)
    with pytest.raises(ValueError, match="fragment"):
        files.deploy_one(entry)
    with pytest.raises(ValueError, match="fragment"):
        files.sync(entry)


def test_status_skips_fragments(home: Path, git: Path):
    _track(git, ".claude/CLAUDE.md", "frag\n")
    _track(git, ".gitconfig", "cfg\n", fragment=False)
    assert [e.spec.path for e in files.status(git)] == [".gitconfig"]


# -- fragment_entries (TUI rows) ---------------------------------------------

def test_fragment_entries_states(home: Path, git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n", order=10)
    _track(shell, ".claude/CLAUDE.md", "work\n", order=50)
    pairs = [(git, set()), (shell, set())]

    entries = files.fragment_entries(pairs)
    assert [(e.module, e.state) for e in entries] == [
        ("git", files.MISSING),
        ("shell", files.MISSING),
    ]

    files.deploy_fragments(_targets(git, shell))
    entries = files.fragment_entries(pairs)
    assert {e.state for e in entries} == {files.IN_SYNC}

    (home / ".claude/CLAUDE.md").write_text("edited\n")
    entries = files.fragment_entries(pairs)
    assert {e.state for e in entries} == {files.CHANGED}


def test_diff_composed(home: Path, git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n", order=10)
    _track(shell, ".claude/CLAUDE.md", "work\n", order=50)
    frags = _targets(git, shell)[".claude/CLAUDE.md"]
    (home / ".claude").mkdir()
    (home / ".claude/CLAUDE.md").write_text("base\n\nother\n")

    out = files.diff_composed(".claude/CLAUDE.md", frags)
    assert "-work" in out and "+other" in out
    assert "composed:.claude/CLAUDE.md" in out


# -- activate.py deploy-all ---------------------------------------------------

def test_deploy_all_composes(home: Path, repo: Path, git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n", order=10)
    _track(shell, ".claude/CLAUDE.md", "work\n", order=50)
    root = str(repo / "modules")

    code = activate.main(
        ["deploy-all", "--modules-root", root, "--enable", "git", "--enable", "shell"]
    )
    assert code == 0
    assert (home / ".claude/CLAUDE.md").read_text() == "base\n\nwork\n"

    # one contributor left -> rewritten; none -> pruned
    assert activate.main(["deploy-all", "--modules-root", root, "--enable", "git"]) == 0
    assert (home / ".claude/CLAUDE.md").read_text() == "base\n"
    assert activate.main(["deploy-all", "--modules-root", root]) == 0
    assert not (home / ".claude/CLAUDE.md").exists()


def test_deploy_all_disable_child_excludes_fragment(home: Path, repo: Path, git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n", order=10)
    _track(shell, ".claude/CLAUDE.md", "work\n", order=50, child="fish")
    root = str(repo / "modules")

    code = activate.main(
        [
            "deploy-all", "--modules-root", root,
            "--enable", "git", "--enable", "shell",
            "--disable-child", "shell:fish",
        ]
    )
    assert code == 0
    assert (home / ".claude/CLAUDE.md").read_text() == "base\n"


def test_deploy_all_rejects_mixed_target(home: Path, repo: Path, git: Path, shell: Path, capsys):
    _track(git, ".claude/CLAUDE.md", "whole\n", fragment=False)
    _track(shell, ".claude/CLAUDE.md", "frag\n")
    root = str(repo / "modules")

    code = activate.main(
        ["deploy-all", "--modules-root", root, "--enable", "git", "--enable", "shell"]
    )
    assert code == 2
    assert not (home / ".claude/CLAUDE.md").exists()  # nothing deployed
    assert "pick one style" in capsys.readouterr().out


def test_deploy_all_composed_conflict_exit_code(home: Path, repo: Path, git: Path, shell: Path):
    _track(git, ".claude/CLAUDE.md", "base\n")
    root = str(repo / "modules")
    assert activate.main(["deploy-all", "--modules-root", root, "--enable", "git"]) == 0

    (home / ".claude/CLAUDE.md").write_text("edited\n")
    (git / "files/.claude/CLAUDE.md").write_text("base v2\n")
    code = activate.main(["deploy-all", "--modules-root", root, "--enable", "git"])
    assert code == 1
    assert (home / ".claude/CLAUDE.md").read_text() == "edited\n"
