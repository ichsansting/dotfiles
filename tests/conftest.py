from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path


def write_preset(root: Path, name: str, **data) -> None:
    d = root / "presets"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(data))


def write_bundle_file(root: Path, bundle: str, path: str, mode: str, content: str | None = None) -> None:
    """Register a whole-file entry for a bundle; writes fixture content for plain mode."""
    bdir = root / "bundles" / bundle
    manifest_path = bdir / "files.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": []}
    data["files"].append({"path": path, "mode": mode})
    manifest_path.write_text(json.dumps(data))
    if mode == "plain":
        f = bdir / "files" / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content if content is not None else "")


def write_fragment(root: Path, target: str, order: str, owner: str, content: str, secret: bool = False) -> None:
    suffix = ".secret.md" if secret else ".md"
    d = root / "fragments" / f"{target}.d"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{order}-{owner}{suffix}").write_text(content)
