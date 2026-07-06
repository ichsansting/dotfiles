"""Repo and home path helpers."""
from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Find the dotfiles repo root.

    Priority:
      1. DOTFILES_REPO env var (set by the nix run wrapper)
      2. Current working directory if it contains flake.nix
      3. ~/dotfiles fallback
    """
    env = os.environ.get("DOTFILES_REPO")
    if env:
        p = Path(env)
        if (p / "flake.nix").exists():
            return p

    cwd = Path.cwd()
    if (cwd / "flake.nix").exists():
        return cwd

    fallback = Path.home() / "dotfiles"
    if (fallback / "flake.nix").exists():
        return fallback

    raise RuntimeError(
        "Cannot find dotfiles repo root. "
        "Set DOTFILES_REPO or run from the repo directory."
    )


def state_dir() -> Path:
    return Path.home() / ".local" / "state" / "dotfiles"


def profile_path() -> Path:
    return state_dir() / "profile.json"
