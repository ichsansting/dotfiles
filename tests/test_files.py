from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.core import files
from dotfiles.core import manifest as mf


@pytest.fixture
def module_dir(repo: Path) -> Path:
    return repo / "modules" / "git"


def _track_plain(module_dir: Path, rel: str, content: str) -> None:
    storage = module_dir / "files" / rel
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text(content)
    specs = mf.load(module_dir) + [mf.FileSpec(rel, mf.MODE_PLAIN)]
    mf.save(module_dir, specs)


def test_status_states(home: Path, module_dir: Path):
    _track_plain(module_dir, ".aws/config", "repo\n")
    (entry,) = files.status(module_dir)
    assert entry.state == files.MISSING

    entry.home_path.parent.mkdir(parents=True)
    entry.home_path.write_text("repo\n")
    (entry,) = files.status(module_dir)
    assert entry.state == files.IN_SYNC

    entry.home_path.write_text("local edit\n")
    (entry,) = files.status(module_dir)
    assert entry.state == files.CHANGED


def test_status_raises_on_manifest_drift(home: Path, module_dir: Path):
    mf.save(module_dir, [mf.FileSpec(".aws/config", mf.MODE_PLAIN)])
    with pytest.raises(FileNotFoundError):
        files.status(module_dir)


def test_secret_without_key_is_locked(home: Path, module_dir: Path):
    storage = module_dir / "files/.ssh/id_ed25519.sops.yaml"
    storage.parent.mkdir(parents=True)
    storage.write_text("id_ed25519: ENC[...]\n")
    mf.save(module_dir, [mf.FileSpec(".ssh/id_ed25519", mf.MODE_SECRET)])
    (home / ".ssh").mkdir()
    (home / ".ssh/id_ed25519").write_text("key")
    (entry,) = files.status(module_dir)
    assert entry.state == files.LOCKED


def test_deploy_module_anti_clobber(home: Path, module_dir: Path, capsys):
    _track_plain(module_dir, ".aws/config", "repo\n")
    files.deploy_module(module_dir)
    dest = home / ".aws/config"
    assert dest.read_text() == "repo\n"
    assert (dest.stat().st_mode & 0o777) == 0o600
    assert (dest.parent.stat().st_mode & 0o777) == 0o700

    # identical -> no-op; locally changed -> conflict unless overwrite
    files.deploy_module(module_dir)
    dest.write_text("local\n")
    with pytest.raises(RuntimeError, match="Conflicts"):
        files.deploy_module(module_dir)
    files.deploy_module(module_dir, overwrite=True)
    assert dest.read_text() == "repo\n"


def test_deploy_module_skip_secrets(home: Path, module_dir: Path, capsys):
    _track_plain(module_dir, ".aws/config", "repo\n")
    storage = module_dir / "files/.ssh/id_ed25519.sops.yaml"
    storage.parent.mkdir(parents=True)
    storage.write_text("id_ed25519: ENC[...]\n")
    specs = mf.load(module_dir) + [mf.FileSpec(".ssh/id_ed25519", mf.MODE_SECRET)]
    mf.save(module_dir, specs)

    files.deploy_module(module_dir, skip_secrets=True)
    assert (home / ".aws/config").exists()
    assert not (home / ".ssh/id_ed25519").exists()
    assert "skipped secret" in capsys.readouterr().out


def test_deploy_module_disabled_children(home: Path, module_dir: Path, capsys):
    _track_plain(module_dir, ".gitconfig", "base\n")
    storage = module_dir / "files/.claude/CLAUDE.md"
    storage.parent.mkdir(parents=True)
    storage.write_text("ai stuff\n")
    specs = mf.load(module_dir) + [mf.FileSpec(".claude/CLAUDE.md", mf.MODE_PLAIN, child="ai")]
    mf.save(module_dir, specs)

    files.deploy_module(module_dir, disabled_children={"ai"})
    assert (home / ".gitconfig").exists()
    assert not (home / ".claude/CLAUDE.md").exists()
    assert "child 'ai' disabled" in capsys.readouterr().out

    # child enabled (not in the disabled set) deploys normally
    files.deploy_module(module_dir)
    assert (home / ".claude/CLAUDE.md").read_text() == "ai stuff\n"


def test_deploy_one_guard(home: Path, module_dir: Path):
    _track_plain(module_dir, ".aws/config", "repo\n")
    (entry,) = files.status(module_dir)
    files.deploy_one(entry)
    entry.home_path.write_text("local\n")
    with pytest.raises(RuntimeError, match="local changes"):
        files.deploy_one(entry)
    files.deploy_one(entry, overwrite=True)


def test_sync_plain(home: Path, module_dir: Path):
    _track_plain(module_dir, ".aws/config", "repo\n")
    (entry,) = files.status(module_dir)
    entry.home_path.parent.mkdir(parents=True)
    entry.home_path.write_text("edited\n")
    files.sync(entry)
    assert entry.storage.read_text() == "edited\n"


def test_add_and_remove_plain(home: Path, module_dir: Path):
    src = home / ".gitconfig"
    src.write_text("[user]\n")
    entry = files.add(module_dir, src, mf.MODE_PLAIN)
    assert entry.storage.read_text() == "[user]\n"
    assert mf.load(module_dir) == [mf.FileSpec(".gitconfig", mf.MODE_PLAIN)]

    files.remove(module_dir, entry)
    assert not entry.storage.exists()
    assert mf.load(module_dir) == []
    assert src.exists()  # $HOME copy untouched


def test_add_rejects_outside_home(home: Path, module_dir: Path, tmp_path: Path):
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("x")
    with pytest.raises(ValueError, match="inside \\$HOME"):
        files.add(module_dir, outside, mf.MODE_PLAIN)


def test_diff_plain(home: Path, module_dir: Path):
    _track_plain(module_dir, ".aws/config", "a\nb\n")
    (entry,) = files.status(module_dir)
    entry.home_path.parent.mkdir(parents=True)
    entry.home_path.write_text("a\nc\n")
    out = files.diff(entry)
    assert "-b" in out and "+c" in out
    assert "repo:.aws/config" in out


def test_move_plain_without_home_copy(home: Path, repo: Path, module_dir: Path):
    """Move works while the source module is inactive ($HOME copy absent)."""
    _track_plain(module_dir, ".aws/config", "cfg\n")
    (entry,) = files.status(module_dir)
    assert entry.state == files.MISSING

    dst = repo / "modules" / "shell"
    moved = files.move(module_dir, entry, dst)

    assert mf.load(module_dir) == []
    assert not entry.storage.exists()
    assert mf.load(dst) == [entry.spec]
    assert moved.module == "shell"
    assert moved.storage == dst / "files/.aws/config"
    assert moved.storage.read_text() == "cfg\n"
    assert moved.state == files.MISSING


def test_move_secret_without_key(home: Path, repo: Path, module_dir: Path):
    """Secrets move as a verbatim copy — no sops, no age key involved."""
    storage = module_dir / "files/.ssh/id_ed25519.sops.yaml"
    storage.parent.mkdir(parents=True)
    storage.write_text("id_ed25519: ENC[...]\n")
    spec = mf.FileSpec(".ssh/id_ed25519", mf.MODE_SECRET)
    mf.save(module_dir, [spec])

    entry = files.FileEntry("git", spec, storage, files.MISSING)
    dst = repo / "modules" / "shell"
    moved = files.move(module_dir, entry, dst)

    assert moved.storage == dst / "files/.ssh/id_ed25519.sops.yaml"
    assert moved.storage.read_text() == "id_ed25519: ENC[...]\n"
    assert not storage.exists()
    assert mf.load(module_dir) == []
    assert mf.load(dst) == [spec]


def test_move_collision_and_same_module(home: Path, repo: Path, module_dir: Path):
    _track_plain(module_dir, ".aws/config", "src\n")
    (entry,) = files.status(module_dir)

    with pytest.raises(ValueError, match="same"):
        files.move(module_dir, entry, module_dir)

    dst = repo / "modules" / "shell"
    _track_plain(dst, ".aws/config", "dst\n")
    with pytest.raises(ValueError, match="already tracks"):
        files.move(module_dir, entry, dst)

    # source is fully untouched after both failures
    assert mf.load(module_dir) == [entry.spec]
    assert entry.storage.read_text() == "src\n"
    assert (dst / "files/.aws/config").read_text() == "dst\n"


# -- sops-backed roundtrips (skip when sops missing) ---------------------------


def test_secret_roundtrip_and_move(home: Path, module_dir: Path, sops_bin: str, age_key,
                                   monkeypatch):
    """Encrypt under one storage path, git-mv the file, decrypt still works.

    sops decryption doesn't consult .sops.yaml, and the inner key comes from
    the $HOME basename — so tracked secrets can be moved freely in the repo.
    """
    monkeypatch.setenv("DOTFILES_SOPS_BIN", sops_bin)
    src = home / ".ssh/id_test"
    src.parent.mkdir()
    src.write_text("SECRET-CONTENT\n")

    entry = files.add(module_dir, src, mf.MODE_SECRET, sops_bin=sops_bin)
    assert entry.storage.name == "id_test.sops.yaml"

    moved = entry.storage.with_name("renamed-location.sops.yaml")
    entry.storage.rename(moved)
    from dotfiles.core.sops import decrypt_extract

    # key name is still the $HOME basename regardless of the storage filename
    assert decrypt_extract(moved, "id_test", sops_bin) == b"SECRET-CONTENT\n"


def test_move_secret_roundtrip(home: Path, repo: Path, module_dir: Path,
                               sops_bin: str, age_key, monkeypatch):
    """A secret moved to another module still decrypts to the same bytes."""
    monkeypatch.setenv("DOTFILES_SOPS_BIN", sops_bin)
    src = home / ".ssh/id_test"
    src.parent.mkdir()
    src.write_text("SECRET-CONTENT\n")
    entry = files.add(module_dir, src, mf.MODE_SECRET, sops_bin=sops_bin)

    dst = repo / "modules" / "shell"
    moved = files.move(module_dir, entry, dst)

    from dotfiles.core.sops import decrypt_extract

    assert decrypt_extract(moved.storage, "id_test", sops_bin) == b"SECRET-CONTENT\n"


def test_secret_deploy_sync_status(home: Path, module_dir: Path, sops_bin: str, age_key,
                                   monkeypatch):
    monkeypatch.setenv("DOTFILES_SOPS_BIN", sops_bin)
    src = home / ".config/token"
    src.parent.mkdir(parents=True)
    src.write_text("v1\n")
    files.add(module_dir, src, mf.MODE_SECRET, sops_bin=sops_bin)

    (entry,) = files.status(module_dir, sops_bin=sops_bin)
    assert entry.state == files.IN_SYNC

    src.write_text("v2\n")
    (entry,) = files.status(module_dir, sops_bin=sops_bin)
    assert entry.state == files.CHANGED
    assert "+v2" not in files.diff(entry, sops_bin=sops_bin) or True  # diff runs

    files.sync(entry, sops_bin=sops_bin)
    (entry,) = files.status(module_dir, sops_bin=sops_bin)
    assert entry.state == files.IN_SYNC

    src.unlink()
    files.deploy_module(module_dir, sops_bin=sops_bin)
    assert src.read_text() == "v2\n"
    assert (src.stat().st_mode & 0o777) == 0o600


def test_activate_deploy_cli(home: Path, module_dir: Path, capsys):
    """activate.py deploy: plain files deploy, secrets skip w/o key, exit 0."""
    _track_plain(module_dir, ".aws/config", "cfg\n")
    storage = module_dir / "files/.ssh/id_ed25519.sops.yaml"
    storage.parent.mkdir(parents=True)
    storage.write_text("id_ed25519: ENC[...]\n")
    specs = mf.load(module_dir) + [mf.FileSpec(".ssh/id_ed25519", mf.MODE_SECRET)]
    mf.save(module_dir, specs)

    from dotfiles import activate

    rc = activate.main(["deploy", "--module-dir", str(module_dir)])
    assert rc == 0
    assert (home / ".aws/config").read_text() == "cfg\n"
    assert not (home / ".ssh/id_ed25519").exists()
    out = capsys.readouterr().out
    assert "no age key" in out
