"""Deployed-files state (~/.local/state/dotfiles/deployed.json).

Records every file the tool has written into $HOME (path, owning module,
mode, sha256 of the deployed bytes). This is what makes undeploy
declarative: at switch time, files.prune() removes entries that fell out
of the desired set — and the stored hash lets it distinguish "still what
we deployed" (safe to delete) from "user edited it" (keep, warn).

Hashes are of the bytes on disk (plaintext for secrets), so pruning never
needs sops or an age key.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .paths import deployed_path

VERSION = 1


@dataclass(frozen=True)
class DeployedEntry:
    module: str
    mode: str  # manifest.MODE_PLAIN | manifest.MODE_SECRET
    sha256: str  # hex digest of the bytes written to $HOME


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path | None = None) -> dict[str, DeployedEntry]:
    """Deployed entries keyed by $HOME-relative path; empty if no state yet."""
    p = path or deployed_path()
    if not p.exists():
        return {}
    data = json.loads(p.read_text())
    return {
        rel: DeployedEntry(module=e["module"], mode=e["mode"], sha256=e["sha256"])
        for rel, e in data.get("files", {}).items()
    }


def save(entries: dict[str, DeployedEntry], path: Path | None = None) -> None:
    """Atomically write the state (sorted, stable output)."""
    p = path or deployed_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": VERSION,
        "files": {
            rel: {"module": e.module, "mode": e.mode, "sha256": e.sha256}
            for rel, e in sorted(entries.items())
        },
    }
    fd, tmp = tempfile.mkstemp(dir=p.parent, suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
        os.replace(tmp, p)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
