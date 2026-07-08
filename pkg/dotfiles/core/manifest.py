"""Per-module tracked-files manifest (modules/<name>/files.json).

Storage layout under modules/<name>/files/:
  plain  -> files/<home-rel-path>            (committed verbatim)
  secret -> files/<home-rel-path>.sops.yaml  (sops-encrypted YAML)
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MODE_PLAIN = "plain"
MODE_SECRET = "secret"
SECRET_SUFFIX = ".sops.yaml"
MANIFEST_NAME = "files.json"
FILES_DIR = "files"
DEFAULT_ORDER = 100


@dataclass(frozen=True)
class FileSpec:
    path: str  # $HOME-relative, POSIX separators, e.g. ".ssh/id_ed25519"
    mode: str  # MODE_PLAIN | MODE_SECRET
    child: str | None = None  # owning child toggle; None = whole module
    fragment: bool = False  # part of a composed target (same path in >1 module)
    order: int = DEFAULT_ORDER  # composition sort key; ties break on module name

    def __post_init__(self) -> None:
        if self.mode not in (MODE_PLAIN, MODE_SECRET):
            raise ValueError(f"invalid mode {self.mode!r} for {self.path!r}")
        if PurePosixPath(self.path).is_absolute() or ".." in PurePosixPath(self.path).parts:
            raise ValueError(f"path must be $HOME-relative: {self.path!r}")
        if self.order != DEFAULT_ORDER and not self.fragment:
            raise ValueError(f"order is only valid on fragments: {self.path!r}")


def manifest_path(module_dir: Path) -> Path:
    return module_dir / MANIFEST_NAME


def files_dir(module_dir: Path) -> Path:
    return module_dir / FILES_DIR


def load(module_dir: Path) -> list[FileSpec]:
    p = manifest_path(module_dir)
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [
        FileSpec(
            path=e["path"],
            mode=e["mode"],
            child=e.get("child"),
            fragment=e.get("fragment", False),
            order=e.get("order", DEFAULT_ORDER),
        )
        for e in data.get("files", [])
    ]


def save(module_dir: Path, specs: list[FileSpec]) -> None:
    """Atomically write the manifest (sorted, stable output for clean diffs)."""
    p = manifest_path(module_dir)
    payload = {
        "files": [
            {"path": s.path, "mode": s.mode}
            | ({"child": s.child} if s.child else {})
            | ({"fragment": True} if s.fragment else {})
            | ({"order": s.order} if s.order != DEFAULT_ORDER else {})
            for s in sorted(specs, key=lambda s: s.path)
        ]
    }
    fd, tmp = tempfile.mkstemp(dir=module_dir, suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        os.replace(tmp, p)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def storage_path(module_dir: Path, spec: FileSpec) -> Path:
    base = files_dir(module_dir) / spec.path
    return base.parent / (base.name + SECRET_SUFFIX) if spec.mode == MODE_SECRET else base


def secret_key_name(spec: FileSpec) -> str:
    """Inner YAML key of a secret: the $HOME-relative basename.

    Never derive this from the storage filename — the storage path carries
    the .sops.yaml suffix, but the key inside existing encrypted files is
    the original basename (e.g. 'id_ed25519', 'hosts.yml').
    """
    return PurePosixPath(spec.path).name
