"""Deployed-state tracking + prune: the declarative undeploy lifecycle."""
from __future__ import annotations

from pathlib import Path

from dotfiles import activate
from dotfiles.core import files, state
from dotfiles.core import manifest as mf


def _track_plain(module_dir: Path, rel: str, content: str, child: str | None = None) -> None:
    storage = module_dir / "files" / rel
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text(content)
    specs = mf.load(module_dir) + [mf.FileSpec(rel, mf.MODE_PLAIN, child=child)]
    mf.save(module_dir, specs)


def test_state_roundtrip(home: Path):
    entries = {
        ".aws/config": state.DeployedEntry("work", mf.MODE_PLAIN, state.digest(b"x")),
        ".ssh/id_ed25519": state.DeployedEntry("vcs", mf.MODE_SECRET, state.digest(b"y")),
    }
    state.save(entries)
    assert state.load() == entries


def test_deploy_records_state(home: Path, repo: Path):
    module_dir = repo / "modules" / "git"
    _track_plain(module_dir, ".gitconfig", "cfg\n")
    # Pre-existing, already-in-sync file must be recorded too.
    _track_plain(module_dir, ".aws/config", "aws\n")
    (home / ".aws").mkdir()
    (home / ".aws/config").write_text("aws\n")

    files.deploy_module(module_dir)

    deployed = state.load()
    assert deployed[".gitconfig"].sha256 == state.digest(b"cfg\n")
    assert deployed[".aws/config"].module == "git"


def test_prune_removes_undesired_and_empty_dirs(home: Path, repo: Path):
    module_dir = repo / "modules" / "git"
    _track_plain(module_dir, ".config/gh/hosts.yml", "h\n")
    files.deploy_module(module_dir)
    assert (home / ".config/gh/hosts.yml").exists()

    files.prune(desired=set())

    assert not (home / ".config/gh/hosts.yml").exists()
    assert not (home / ".config").exists()  # empty parents cleaned up
    assert state.load() == {}


def test_prune_keeps_local_edits_unless_forced(home: Path, repo: Path, capsys):
    module_dir = repo / "modules" / "git"
    _track_plain(module_dir, ".gitconfig", "cfg\n")
    files.deploy_module(module_dir)
    (home / ".gitconfig").write_text("edited\n")

    files.prune(desired=set())
    assert (home / ".gitconfig").exists()
    assert ".gitconfig" in state.load()  # kept so the warning repeats
    assert "local changes" in capsys.readouterr().out

    files.prune(desired=set(), force=True)
    assert not (home / ".gitconfig").exists()
    assert state.load() == {}


def test_prune_drops_entry_for_already_missing_file(home: Path):
    state.save({".vanished": state.DeployedEntry("git", mf.MODE_PLAIN, state.digest(b""))})
    files.prune(desired=set())
    assert state.load() == {}


def test_clean_module_drops_state(home: Path, repo: Path):
    module_dir = repo / "modules" / "git"
    _track_plain(module_dir, ".gitconfig", "cfg\n")
    files.deploy_module(module_dir)

    files.clean_module(module_dir)

    assert not (home / ".gitconfig").exists()
    assert state.load() == {}


def test_sync_refreshes_hash(home: Path, repo: Path):
    module_dir = repo / "modules" / "git"
    _track_plain(module_dir, ".gitconfig", "cfg\n")
    files.deploy_module(module_dir)
    (home / ".gitconfig").write_text("edited\n")

    (entry,) = files.status(module_dir)
    files.sync(entry)

    assert state.load()[".gitconfig"].sha256 == state.digest(b"edited\n")
    # A synced file counts as cleanly deployed again → prunable.
    files.prune(desired=set())
    assert not (home / ".gitconfig").exists()


def test_deploy_all_disable_then_prune(home: Path, repo: Path):
    """End-to-end: enable deploys, dropping --enable prunes."""
    git = repo / "modules" / "git"
    shell = repo / "modules" / "shell"
    _track_plain(git, ".gitconfig", "cfg\n")
    _track_plain(shell, ".config/fish/config.fish", "fish\n")
    root = str(repo / "modules")

    assert activate.main(
        ["deploy-all", "--modules-root", root, "--enable", "git", "--enable", "shell"]
    ) == 0
    assert (home / ".gitconfig").exists()
    assert (home / ".config/fish/config.fish").exists()

    # Disable shell: its file goes away, git's stays.
    assert activate.main(["deploy-all", "--modules-root", root, "--enable", "git"]) == 0
    assert (home / ".gitconfig").exists()
    assert not (home / ".config/fish/config.fish").exists()

    # Disable everything.
    assert activate.main(["deploy-all", "--modules-root", root]) == 0
    assert not (home / ".gitconfig").exists()
    assert state.load() == {}


def test_deploy_all_disabled_child_pruned(home: Path, repo: Path):
    git = repo / "modules" / "git"
    _track_plain(git, ".gitconfig", "cfg\n", child="git")
    _track_plain(git, ".ssh/config", "ssh\n", child="ssh")
    root = str(repo / "modules")

    assert activate.main(["deploy-all", "--modules-root", root, "--enable", "git"]) == 0
    assert (home / ".ssh/config").exists()

    assert activate.main(
        ["deploy-all", "--modules-root", root, "--enable", "git",
         "--disable-child", "git:ssh"]
    ) == 0
    assert (home / ".gitconfig").exists()
    assert not (home / ".ssh/config").exists()


def test_deploy_all_untracked_file_pruned(home: Path, repo: Path):
    git = repo / "modules" / "git"
    _track_plain(git, ".gitconfig", "cfg\n")
    root = str(repo / "modules")
    assert activate.main(["deploy-all", "--modules-root", root, "--enable", "git"]) == 0

    (entry,) = files.status(git)
    files.remove(git, entry)  # untrack: $HOME copy left for prune

    assert activate.main(["deploy-all", "--modules-root", root, "--enable", "git"]) == 0
    assert not (home / ".gitconfig").exists()


def test_deploy_all_skipped_secret_not_pruned(home: Path, repo: Path):
    """No age key: an enabled module's secret is skipped but never pruned."""
    git = repo / "modules" / "git"
    storage = git / "files/.ssh/id_ed25519.sops.yaml"
    storage.parent.mkdir(parents=True)
    storage.write_text("id_ed25519: ENC[...]\n")
    mf.save(git, [mf.FileSpec(".ssh/id_ed25519", mf.MODE_SECRET)])
    # Deployed by an earlier generation that had the key.
    (home / ".ssh").mkdir()
    (home / ".ssh/id_ed25519").write_text("plaintext key")
    state.save(
        {".ssh/id_ed25519": state.DeployedEntry(
            "git", mf.MODE_SECRET, state.digest(b"plaintext key"))}
    )
    root = str(repo / "modules")

    assert activate.main(["deploy-all", "--modules-root", root, "--enable", "git"]) == 0
    assert (home / ".ssh/id_ed25519").exists()
    assert ".ssh/id_ed25519" in state.load()

    # Module disabled → pruned (hash match, no key needed).
    assert activate.main(["deploy-all", "--modules-root", root]) == 0
    assert not (home / ".ssh/id_ed25519").exists()


def test_desired_paths_respects_disabled_children(repo: Path):
    git = repo / "modules" / "git"
    _track_plain(git, ".gitconfig", "cfg\n", child="git")
    _track_plain(git, ".ssh/config", "ssh\n", child="ssh")

    assert files.desired_paths([(git, set())]) == {".gitconfig", ".ssh/config"}
    assert files.desired_paths([(git, {"ssh"})]) == {".gitconfig"}
    assert files.desired_paths([]) == set()


def test_orphans_classification(home: Path, repo: Path):
    git = repo / "modules" / "git"
    _track_plain(git, ".gitconfig", "cfg\n")
    _track_plain(git, ".config/gh/hosts.yml", "h\n")
    files.deploy_module(git)
    (home / ".config/gh/hosts.yml").write_text("edited\n")
    # a stale entry whose file is already gone must not show up
    deployed = state.load()
    deployed[".vanished"] = state.DeployedEntry("git", mf.MODE_PLAIN, state.digest(b""))
    state.save(deployed)

    got = {o.path: o for o in files.orphans(desired=set())}

    assert set(got) == {".gitconfig", ".config/gh/hosts.yml"}
    assert not got[".gitconfig"].edited
    assert got[".config/gh/hosts.yml"].edited
    assert got[".gitconfig"].module == "git"

    # desired paths are never orphans
    assert files.orphans(desired={".gitconfig", ".config/gh/hosts.yml"}) == []


def test_remove_orphan_deletes_file_state_and_empty_dirs(home: Path, repo: Path):
    git = repo / "modules" / "git"
    _track_plain(git, ".config/gh/hosts.yml", "h\n")
    files.deploy_module(git)
    (home / ".config/gh/hosts.yml").write_text("edited\n")

    files.remove_orphan(".config/gh/hosts.yml")

    assert not (home / ".config").exists()
    assert state.load() == {}


def test_deploy_all_conflict_still_prunes_and_fails(home: Path, repo: Path, capsys):
    git = repo / "modules" / "git"
    shell = repo / "modules" / "shell"
    _track_plain(git, ".gitconfig", "cfg\n")
    _track_plain(shell, ".config/fish/config.fish", "fish\n")
    root = str(repo / "modules")
    assert activate.main(
        ["deploy-all", "--modules-root", root, "--enable", "git", "--enable", "shell"]
    ) == 0

    (home / ".gitconfig").write_text("edited\n")  # conflict in git
    rc = activate.main(["deploy-all", "--modules-root", root, "--enable", "git"])

    assert rc == 1  # conflict surfaces in the exit code
    assert (home / ".gitconfig").read_text() == "edited\n"  # never clobbered
    assert not (home / ".config/fish/config.fish").exists()  # prune still ran
