from __future__ import annotations

import json
from pathlib import Path

import pytest

from dotfiles.core import manifest as mf


@pytest.fixture
def module_dir(repo: Path) -> Path:
    return repo / "modules" / "git"


def test_roundtrip_sorted(module_dir: Path):
    specs = [
        mf.FileSpec(".ssh/id_ed25519", mf.MODE_SECRET),
        mf.FileSpec(".aws/config", mf.MODE_PLAIN),
    ]
    mf.save(module_dir, specs)
    loaded = mf.load(module_dir)
    assert [s.path for s in loaded] == [".aws/config", ".ssh/id_ed25519"]


def test_roundtrip_child_field(module_dir: Path):
    specs = [
        mf.FileSpec(".claude/CLAUDE.md", mf.MODE_PLAIN, child="ai"),
        mf.FileSpec(".gitconfig", mf.MODE_PLAIN),
    ]
    mf.save(module_dir, specs)
    loaded = {s.path: s for s in mf.load(module_dir)}
    assert loaded[".claude/CLAUDE.md"].child == "ai"
    assert loaded[".gitconfig"].child is None

    # entries without a child stay two-key: no "child": null noise in the JSON
    raw = json.loads(mf.manifest_path(module_dir).read_text())
    by_path = {e["path"]: e for e in raw["files"]}
    assert "child" not in by_path[".gitconfig"]
    assert by_path[".claude/CLAUDE.md"]["child"] == "ai"


def test_storage_path_modes(module_dir: Path):
    plain = mf.FileSpec(".aws/config", mf.MODE_PLAIN)
    secret = mf.FileSpec(".ssh/id_ed25519", mf.MODE_SECRET)
    assert mf.storage_path(module_dir, plain) == module_dir / "files/.aws/config"
    assert (
        mf.storage_path(module_dir, secret)
        == module_dir / "files/.ssh/id_ed25519.sops.yaml"
    )


def test_secret_key_name_is_home_basename(module_dir: Path):
    """The inner sops key comes from the $HOME path, NOT the storage filename."""
    spec = mf.FileSpec(".config/gh/hosts.yml", mf.MODE_SECRET)
    assert mf.secret_key_name(spec) == "hosts.yml"


def test_spec_validation():
    with pytest.raises(ValueError):
        mf.FileSpec("/etc/passwd", mf.MODE_PLAIN)
    with pytest.raises(ValueError):
        mf.FileSpec("../escape", mf.MODE_PLAIN)
    with pytest.raises(ValueError):
        mf.FileSpec(".aws/config", "encrypted")
    # order only makes sense on fragments
    with pytest.raises(ValueError, match="order"):
        mf.FileSpec(".aws/config", mf.MODE_PLAIN, order=10)


def test_roundtrip_fragment_fields(module_dir: Path):
    specs = [
        mf.FileSpec(".claude/CLAUDE.md", mf.MODE_PLAIN, fragment=True, order=10),
        mf.FileSpec(".gitconfig", mf.MODE_PLAIN),
        mf.FileSpec(".zshrc", mf.MODE_PLAIN, fragment=True),  # default order
    ]
    mf.save(module_dir, specs)
    loaded = {s.path: s for s in mf.load(module_dir)}
    assert loaded[".claude/CLAUDE.md"].fragment is True
    assert loaded[".claude/CLAUDE.md"].order == 10
    assert loaded[".gitconfig"].fragment is False
    assert loaded[".gitconfig"].order == mf.DEFAULT_ORDER
    assert loaded[".zshrc"].fragment is True
    assert loaded[".zshrc"].order == mf.DEFAULT_ORDER

    # defaults stay out of the JSON: existing manifests remain byte-identical
    raw = json.loads(mf.manifest_path(module_dir).read_text())
    by_path = {e["path"]: e for e in raw["files"]}
    assert "fragment" not in by_path[".gitconfig"]
    assert "order" not in by_path[".gitconfig"]
    assert by_path[".claude/CLAUDE.md"]["fragment"] is True
    assert by_path[".claude/CLAUDE.md"]["order"] == 10
    assert "order" not in by_path[".zshrc"]
