"""Unified tracked-file operations (plain + secret) driven by files.json.

Every operation takes the manifest as the source of truth; the mode only
decides how bytes move:

  plain  : copy between $HOME and modules/<m>/files/<path>
  secret : sops-decrypt/encrypt between $HOME and files/<path>.sops.yaml
"""
from __future__ import annotations

import difflib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import manifest as mf
from .agekey import has_key
from .sops import decrypt_extract, encrypt

# Entry states
MISSING = "missing"      # $HOME copy absent
IN_SYNC = "in_sync"      # repo and $HOME identical
CHANGED = "changed"      # repo and $HOME differ
LOCKED = "locked"        # secret, but no age key available to compare


@dataclass(frozen=True)
class FileEntry:
    module: str
    spec: mf.FileSpec
    storage: Path  # encrypted yaml or plain file inside the repo
    state: str

    @property
    def home_path(self) -> Path:
        return Path.home() / self.spec.path

    @property
    def is_secret(self) -> bool:
        return self.spec.mode == mf.MODE_SECRET


def repo_bytes(spec: mf.FileSpec, storage: Path, sops_bin=None, age_key=None) -> bytes:
    if spec.mode == mf.MODE_SECRET:
        return decrypt_extract(storage, mf.secret_key_name(spec), sops_bin, age_key)
    return storage.read_bytes()


def status(
    module_dir: Path,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> list[FileEntry]:
    """All tracked files of a module with their sync state.

    Raises if the manifest references storage that does not exist — that is
    repo corruption, not a user state.
    """
    home = Path.home()
    entries: list[FileEntry] = []
    for spec in mf.load(module_dir):
        storage = mf.storage_path(module_dir, spec)
        if not storage.exists():
            raise FileNotFoundError(
                f"{module_dir.name}: manifest lists {spec.path} but {storage} is missing"
            )
        dest = home / spec.path
        if not dest.exists():
            state = MISSING
        elif spec.mode == mf.MODE_SECRET and not has_key(age_key):
            state = LOCKED
        elif spec.mode == mf.MODE_SECRET:
            repo = repo_bytes(spec, storage, sops_bin, age_key)
            state = IN_SYNC if repo == dest.read_bytes() else CHANGED
        else:
            state = IN_SYNC if storage.read_bytes() == dest.read_bytes() else CHANGED
        entries.append(FileEntry(module_dir.name, spec, storage, state))
    return entries


def diff(
    entry: FileEntry,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> str:
    """Unified diff: repo copy (decrypted if secret) vs $HOME copy."""
    repo_text = repo_bytes(entry.spec, entry.storage, sops_bin, age_key).decode(
        "utf-8", errors="replace"
    )
    hp = entry.home_path
    home_text = hp.read_text(errors="replace") if hp.exists() else ""
    rel = entry.spec.path
    lines = list(
        difflib.unified_diff(
            repo_text.splitlines(keepends=True),
            home_text.splitlines(keepends=True),
            fromfile=f"repo:{rel}",
            tofile=f"home:{rel}",
        )
    )
    return "".join(lines) if lines else "(no differences)"


def _write_home(dest: Path, data: bytes) -> None:
    home = Path.home()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.parent != home:
        os.chmod(dest.parent, 0o700)
    dest.write_bytes(data)
    os.chmod(dest, 0o600)


def deploy_module(
    module_dir: Path,
    overwrite: bool = False,
    sops_bin: str | None = None,
    age_key: Path | None = None,
    skip_secrets: bool = False,
    disabled_children: frozenset[str] | set[str] = frozenset(),
) -> None:
    """Deploy every tracked file of a module into $HOME (repo → $HOME).

    Anti-clobber: a destination that exists with different content is a
    conflict unless overwrite=True. Used by activate.py at switch time;
    activation passes skip_secrets=True when no age key is present and
    disabled_children for child toggles that are off, so their files are
    not deployed.
    """
    home = Path.home()
    conflicts: list[str] = []

    for spec in mf.load(module_dir):
        storage = mf.storage_path(module_dir, spec)
        if not storage.exists():
            raise FileNotFoundError(
                f"{module_dir.name}: manifest lists {spec.path} but {storage} is missing"
            )
        if spec.child in disabled_children:
            print(
                f"files: skipped {spec.path} (child '{spec.child}' disabled)",
                flush=True,
            )
            continue
        if spec.mode == mf.MODE_SECRET and skip_secrets:
            print(f"files: skipped secret {spec.path} (no age key)", flush=True)
            continue

        data = repo_bytes(spec, storage, sops_bin, age_key)
        dest = home / spec.path

        if dest.exists():
            if data == dest.read_bytes():
                continue
            if not overwrite:
                print(f"Error: {spec.path} has local changes.", flush=True)
                print("       Use the TUI to diff/sync first.", flush=True)
                conflicts.append(spec.path)
                continue
            print(f"Warning: overwriting {spec.path} (overwrite=True).", flush=True)

        _write_home(dest, data)
        print(f"files: deployed {spec.path}", flush=True)

    if conflicts:
        raise RuntimeError(f"Conflicts, sync first: {', '.join(conflicts)}")


def clean_module(
    module_dir: Path,
    force: bool = False,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> None:
    """Remove $HOME copies of every tracked file (opposite of deploy_module).

    Anti-clobber: a $HOME file that differs from the repo copy (or a locked
    secret) is skipped unless force=True.
    """
    home = Path.home()
    conflicts: list[str] = []

    for spec in mf.load(module_dir):
        storage = mf.storage_path(module_dir, spec)
        if not storage.exists():
            raise FileNotFoundError(
                f"{module_dir.name}: manifest lists {spec.path} but {storage} is missing"
            )
        dest = home / spec.path
        if not dest.exists():
            continue

        if not force:
            if spec.mode == mf.MODE_SECRET and not has_key(age_key):
                print(f"Warning: {spec.path} is a locked secret.", flush=True)
                print("         Use --force to remove anyway.", flush=True)
                conflicts.append(spec.path)
                continue
            data = repo_bytes(spec, storage, sops_bin, age_key)
            if data != dest.read_bytes():
                print(f"Error: {spec.path} has local changes.", flush=True)
                print("       Use --force to remove anyway.", flush=True)
                conflicts.append(spec.path)
                continue

        dest.unlink()
        print(f"files: removed {spec.path} from $HOME", flush=True)

    if conflicts:
        raise RuntimeError(f"Conflicts, use --force: {', '.join(conflicts)}")


def deploy_one(
    entry: FileEntry,
    overwrite: bool = False,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> None:
    """Deploy a single tracked file (repo → $HOME), same guard as deploy_module."""
    data = repo_bytes(entry.spec, entry.storage, sops_bin, age_key)
    dest = entry.home_path
    if dest.exists() and data != dest.read_bytes() and not overwrite:
        raise RuntimeError(f"{entry.spec.path} has local changes; diff/sync first")
    _write_home(dest, data)
    print(f"files: deployed {entry.spec.path}", flush=True)


def sync(
    entry: FileEntry,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> None:
    """Copy/re-encrypt the $HOME copy back into the repo ($HOME → repo)."""
    src = entry.home_path
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src}")
    if entry.is_secret:
        encrypt(src.read_bytes(), entry.storage, mf.secret_key_name(entry.spec),
                sops_bin, age_key)
    else:
        entry.storage.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, entry.storage)
    print(f"files: synced {entry.spec.path}", flush=True)


def add(
    module_dir: Path,
    home_path: Path,
    mode: str,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> FileEntry:
    """Track a new $HOME file: copy/encrypt into files/ and append to the manifest."""
    src = home_path.resolve()
    home = Path.home()
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src}")
    if not src.is_relative_to(home) or src == home:
        raise ValueError(f"File must be inside $HOME ({home}): {src}")

    spec = mf.FileSpec(path=src.relative_to(home).as_posix(), mode=mode)
    storage = mf.storage_path(module_dir, spec)
    storage.parent.mkdir(parents=True, exist_ok=True)

    if mode == mf.MODE_SECRET:
        encrypt(src.read_bytes(), storage, mf.secret_key_name(spec), sops_bin, age_key)
    else:
        shutil.copy2(src, storage)

    specs = [s for s in mf.load(module_dir) if s.path != spec.path]
    specs.append(spec)
    mf.save(module_dir, specs)
    print(f"files: added {spec.path} ({mode})", flush=True)
    return FileEntry(module_dir.name, spec, storage, IN_SYNC)


def move(src_module_dir: Path, entry: FileEntry, dst_module_dir: Path) -> FileEntry:
    """Move a tracked file's storage + manifest entry to another module.

    Repo → repo only: never touches $HOME (works while the source module is
    inactive) and never decrypts — a secret's .sops.yaml is copied verbatim
    because its inner key is the $HOME basename, which is module-independent.
    The mode is preserved; changing plain↔secret needs plaintext access, so
    untrack + re-add instead.
    """
    if src_module_dir.resolve() == dst_module_dir.resolve():
        raise ValueError("source and destination module are the same")
    if any(s.path == entry.spec.path for s in mf.load(dst_module_dir)):
        raise ValueError(f"{dst_module_dir.name} already tracks {entry.spec.path}")
    if not entry.storage.exists():
        raise FileNotFoundError(
            f"{src_module_dir.name}: manifest lists {entry.spec.path} "
            f"but {entry.storage} is missing"
        )

    # Copy first, remove last: a crash mid-move leaves the file tracked in
    # both modules (both valid, untrack one) rather than lost.
    dst_storage = mf.storage_path(dst_module_dir, entry.spec)
    dst_storage.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(entry.storage, dst_storage)
    mf.save(dst_module_dir, mf.load(dst_module_dir) + [entry.spec])
    mf.save(
        src_module_dir,
        [s for s in mf.load(src_module_dir) if s.path != entry.spec.path],
    )
    entry.storage.unlink(missing_ok=True)
    print(
        f"files: moved {entry.spec.path} "
        f"{src_module_dir.name} -> {dst_module_dir.name}",
        flush=True,
    )
    return FileEntry(dst_module_dir.name, entry.spec, dst_storage, entry.state)


def remove(module_dir: Path, entry: FileEntry) -> None:
    """Untrack a file: delete its repo storage and manifest entry.

    The $HOME copy is left alone.
    """
    entry.storage.unlink(missing_ok=True)
    mf.save(module_dir, [s for s in mf.load(module_dir) if s.path != entry.spec.path])
    print(f"files: removed {entry.spec.path}", flush=True)
