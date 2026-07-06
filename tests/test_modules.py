from __future__ import annotations

import json
from pathlib import Path

import pytest

from dotfiles.core import modules


def test_discover_reads_module_json(repo: Path):
    found = modules.discover(repo)
    assert [m.name for m in found] == ["git", "shell"]
    shell = next(m for m in found if m.name == "shell")
    assert shell.children == {"fish": "fish shell", "atuin": "history"}
    assert shell.description == "shell module"


def test_discover_rejects_partial_module(repo: Path):
    broken = repo / "modules" / "broken"
    broken.mkdir()
    (broken / "default.nix").write_text("{ }\n")
    with pytest.raises(RuntimeError, match="missing module.json"):
        modules.discover(repo)


def test_discover_ignores_plain_dirs(repo: Path):
    (repo / "modules" / "not-a-module").mkdir()
    assert [m.name for m in modules.discover(repo)] == ["git", "shell"]


def test_parity_with_presets(repo: Path):
    """Every module referenced by a committed preset must exist."""
    names = {m.name for m in modules.discover(repo)}
    for preset_file in (repo / "presets").glob("*.json"):
        data = json.loads(preset_file.read_text())
        assert set(data.get("modules", {})) <= names


def test_create_scaffolds_module(repo: Path):
    mod = modules.create(repo, "personal", "personal secrets")
    d = repo / "modules" / "personal"
    assert mod.path == d
    assert not (d / "files.json").exists()  # created lazily by files.add

    meta = json.loads((d / "module.json").read_text())
    assert meta == {"description": "personal secrets", "children": {}}

    nix = (d / "default.nix").read_text()
    assert "options.dotfiles.personal" in nix
    assert "config.dotfiles.personal" in nix

    found = {m.name: m for m in modules.discover(repo)}
    assert found["personal"].description == "personal secrets"
    assert found["personal"].children == {}


@pytest.mark.parametrize(
    "name", ["", "9x", "Has Space", "UPPER", "a.b", "../evil", "_x", "git"]
)
def test_create_rejects_bad_names(repo: Path, name: str):
    before = sorted(p.name for p in (repo / "modules").iterdir())
    with pytest.raises(ValueError):
        modules.create(repo, name)
    assert sorted(p.name for p in (repo / "modules").iterdir()) == before


def test_create_cleanup_on_failure(repo: Path, monkeypatch: pytest.MonkeyPatch):
    """A failed scaffold must not leave a half-module that breaks discover()."""
    orig = Path.write_text

    def boom(self: Path, *args, **kwargs):
        if self.name == "default.nix":
            raise OSError("disk full")
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(OSError, match="disk full"):
        modules.create(repo, "personal")
    assert not (repo / "modules" / "personal").exists()
    assert [m.name for m in modules.discover(repo)] == ["git", "shell"]


def test_create_then_add_file(home: Path, repo: Path):
    from dotfiles.core import files
    from dotfiles.core import manifest as mf

    mod = modules.create(repo, "personal")
    src = home / ".config/token"
    src.parent.mkdir(parents=True)
    src.write_text("t\n")
    files.add(mod.path, src, mf.MODE_PLAIN)
    assert (mod.path / "files.json").exists()
    (entry,) = files.status(mod.path)
    assert entry.state == files.IN_SYNC
