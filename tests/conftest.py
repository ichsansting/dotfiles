from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated $HOME so core functions never touch the real one."""
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    return h


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal fake dotfiles repo with two modules and two presets."""
    r = tmp_path / "repo"
    (r / "modules").mkdir(parents=True)
    (r / "flake.nix").write_text("{}\n")
    monkeypatch.setenv("DOTFILES_REPO", str(r))

    def module(name: str, children: dict[str, str]) -> None:
        d = r / "modules" / name
        d.mkdir()
        (d / "default.nix").write_text("{ }\n")
        (d / "module.json").write_text(
            json.dumps({"description": f"{name} module", "children": children}) + "\n"
        )

    module("shell", {"fish": "fish shell", "atuin": "history"})
    module("git", {"git": "git", "ssh": "ssh"})

    presets = r / "presets"
    presets.mkdir()
    (presets / "default.json").write_text(
        json.dumps(
            {
                "modules": {"shell": {"enable": True}, "git": {"enable": True}},
                "settings": {"git": {"name": "Test", "email": "t@example.com"}},
            }
        )
        + "\n"
    )
    (presets / "work.json").write_text(
        json.dumps(
            {
                "modules": {
                    "shell": {"enable": True, "children": {"atuin": False}},
                    "git": {"enable": False},
                }
            }
        )
        + "\n"
    )
    return r


@pytest.fixture
def sops_bin() -> str:
    """Real sops binary, or skip (unavailable in some sandboxes)."""
    bin_ = shutil.which("sops")
    if not bin_:
        pytest.skip("sops binary not available")
    return bin_


@pytest.fixture
def age_key(home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Throwaway age key installed at the conventional path, with .sops.yaml
    in a temp cwd so sops encrypt picks it up."""
    if not shutil.which("age-keygen"):
        pytest.skip("age-keygen not available")
    from dotfiles.core import agekey

    pub = agekey.generate()
    key = agekey.key_path()
    monkeypatch.setenv("SOPS_AGE_KEY_FILE", str(key))
    monkeypatch.setenv("SOPS_AGE_RECIPIENTS", pub)
    return key
