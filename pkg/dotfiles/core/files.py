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
from . import state
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
        if spec.fragment:
            continue  # composed targets are listed via fragment_entries()
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


def _record_deployed(entry: FileEntry, data: bytes) -> None:
    deployed = state.load()
    deployed[entry.spec.path] = state.DeployedEntry(
        entry.module, entry.spec.mode, state.digest(data)
    )
    state.save(deployed)


def _remove_empty_parents(directory: Path, stop: Path) -> None:
    """rmdir the directory and its parents while empty, up to (not incl.) stop."""
    d = directory
    while d != stop and d.is_relative_to(stop):
        try:
            d.rmdir()
        except OSError:
            return
        d = d.parent


def desired_paths(modules: list[tuple[Path, set[str]]]) -> set[str]:
    """The $HOME-relative paths that should exist: every tracked file of the
    given (module_dir, disabled_children) pairs. Single source of truth for
    both switch-time prune (activate.py deploy-all) and the TUI's orphan
    detection — anything deployed but not in this set is an orphan.

    Fragment specs contribute their target path like any other entry, so a
    composed file stays desired while at least one enabled module still
    contributes a non-disabled fragment.
    """
    desired: set[str] = set()
    for module_dir, disabled in modules:
        desired.update(
            s.path for s in mf.load(module_dir) if s.child not in disabled
        )
    return desired


@dataclass(frozen=True)
class Fragment:
    """One module's contribution to a composed target file."""

    module: str
    spec: mf.FileSpec
    storage: Path


def partition_targets(
    modules: list[tuple[Path, set[str]]],
) -> tuple[dict[str, list[Fragment]], list[str]]:
    """Group the enabled fragment specs by target path.

    Returns (targets, errors). A target path must be either whole-file
    (exactly one owner — today's behavior) or all-fragments; a path with
    both kinds of contributors, or with two whole-file owners, is a config
    error. Only the enabled, non-disabled-child set is considered — a
    disabled module's conflicting entry surfaces once it is enabled.
    """
    targets: dict[str, list[Fragment]] = {}
    whole_owners: dict[str, list[str]] = {}
    for module_dir, disabled in modules:
        for spec in mf.load(module_dir):
            if spec.child in disabled:
                continue
            if spec.fragment:
                targets.setdefault(spec.path, []).append(
                    Fragment(module_dir.name, spec, mf.storage_path(module_dir, spec))
                )
            else:
                whole_owners.setdefault(spec.path, []).append(module_dir.name)

    errors: list[str] = []
    for path, owners in sorted(whole_owners.items()):
        if path in targets:
            frag_mods = ", ".join(sorted(f.module for f in targets[path]))
            errors.append(
                f"{path}: tracked whole-file by {', '.join(owners)} but as a "
                f"fragment by {frag_mods} — pick one style"
            )
        elif len(owners) > 1:
            errors.append(f"{path}: tracked whole-file by multiple modules: "
                          f"{', '.join(owners)}")
    return targets, errors


def compose(
    fragments: list[Fragment],
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> bytes:
    """Concatenate a target's fragments deterministically.

    Sorted by (order, module); each block trimmed to no trailing newline,
    empty blocks dropped, one blank line between blocks, single trailing
    newline.
    """
    parts = [
        repo_bytes(f.spec, f.storage, sops_bin, age_key).rstrip(b"\n")
        for f in sorted(fragments, key=lambda f: (f.spec.order, f.module))
    ]
    parts = [p for p in parts if p]
    return b"\n\n".join(parts) + b"\n" if parts else b""


def _composed_entry(fragments: list[Fragment], data: bytes) -> state.DeployedEntry:
    modules = "+".join(sorted({f.module for f in fragments}))
    mode = (
        mf.MODE_SECRET
        if any(f.spec.mode == mf.MODE_SECRET for f in fragments)
        else mf.MODE_PLAIN
    )
    return state.DeployedEntry(modules, mode, state.digest(data))


def deploy_fragments(
    targets: dict[str, list[Fragment]],
    overwrite: bool = False,
    sops_bin: str | None = None,
    age_key: Path | None = None,
    skip_secrets: bool = False,
) -> None:
    """Deploy every composed target (fragments from partition_targets).

    A target with any secret fragment is skipped whole while no age key is
    available — a partial composition is never written; the path stays in
    desired_paths so prune leaves the existing copy alone.

    Anti-clobber is hash-aware: a destination that still matches the hash
    recorded at deploy time is rewritten silently when the composition
    changes (fragment edited, contributor added/removed) — only a
    user-edited destination is a conflict. This also migrates a previously
    whole-file-deployed path to fragments without a false conflict.
    """
    home = Path.home()
    conflicts: list[str] = []
    deployed = state.load()

    for path in sorted(targets):
        frags = targets[path]
        for f in frags:
            if not f.storage.exists():
                raise FileNotFoundError(
                    f"{f.module}: manifest lists {f.spec.path} but {f.storage} is missing"
                )
        if skip_secrets and any(f.spec.mode == mf.MODE_SECRET for f in frags):
            locked = ", ".join(
                sorted(f.module for f in frags if f.spec.mode == mf.MODE_SECRET)
            )
            print(
                f"files: skipped composed {path} (secret fragment from {locked}, no age key)",
                flush=True,
            )
            continue

        data = compose(frags, sops_bin, age_key)
        dest = home / path
        entry = _composed_entry(frags, data)

        if dest.exists():
            current = dest.read_bytes()
            if current == data:
                deployed[path] = entry
                continue
            prev = deployed.get(path)
            edited = prev is None or state.digest(current) != prev.sha256
            if edited and not overwrite:
                print(f"Error: {path} has local changes.", flush=True)
                print("       Use the TUI to diff/sync first.", flush=True)
                conflicts.append(path)
                continue
            if edited:
                print(f"Warning: overwriting {path} (overwrite=True).", flush=True)

        _write_home(dest, data)
        deployed[path] = entry
        print(f"files: deployed {path} (composed from {entry.module})", flush=True)

    state.save(deployed)
    if conflicts:
        raise RuntimeError(f"Conflicts, sync first: {', '.join(conflicts)}")


def fragment_entries(
    modules: list[tuple[Path, set[str]]],
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> list[FileEntry]:
    """TUI rows for composed targets: one entry per (module, fragment).

    The state is computed per target — composed expectation vs the $HOME
    copy — so every contributing module's row shows the same state.
    """
    home = Path.home()
    targets, _ = partition_targets(modules)
    entries: list[FileEntry] = []
    for path in sorted(targets):
        frags = targets[path]
        for f in frags:
            if not f.storage.exists():
                raise FileNotFoundError(
                    f"{f.module}: manifest lists {f.spec.path} but {f.storage} is missing"
                )
        dest = home / path
        has_secret = any(f.spec.mode == mf.MODE_SECRET for f in frags)
        if not dest.exists():
            target_state = MISSING
        elif has_secret and not has_key(age_key):
            target_state = LOCKED
        else:
            expected = compose(frags, sops_bin, age_key)
            target_state = IN_SYNC if expected == dest.read_bytes() else CHANGED
        entries.extend(
            FileEntry(f.module, f.spec, f.storage, target_state) for f in frags
        )
    return entries


def diff_composed(
    path: str,
    fragments: list[Fragment],
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> str:
    """Unified diff: composed expectation vs the $HOME copy."""
    expected = compose(fragments, sops_bin, age_key).decode("utf-8", errors="replace")
    hp = Path.home() / path
    home_text = hp.read_text(errors="replace") if hp.exists() else ""
    lines = list(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            home_text.splitlines(keepends=True),
            fromfile=f"composed:{path}",
            tofile=f"home:{path}",
        )
    )
    return "".join(lines) if lines else "(no differences)"


@dataclass(frozen=True)
class OrphanEntry:
    """A deployed file that no longer belongs to any enabled module."""

    path: str  # $HOME-relative
    module: str  # last recorded owner (informational)
    mode: str
    edited: bool  # content differs from what was deployed

    @property
    def home_path(self) -> Path:
        return Path.home() / self.path


def orphans(desired: set[str] | frozenset[str]) -> list[OrphanEntry]:
    """Deployed-state entries outside the desired set whose file still exists.

    Non-edited orphans vanish on the next switch (prune removes them);
    edited ones need a user decision in the TUI: track (n) or delete (x).
    """
    home = Path.home()
    result: list[OrphanEntry] = []
    for rel, entry in state.load().items():
        if rel in desired:
            continue
        dest = home / rel
        if not dest.exists():
            continue  # prune drops the entry on the next switch
        edited = state.digest(dest.read_bytes()) != entry.sha256
        result.append(OrphanEntry(rel, entry.module, entry.mode, edited))
    return result


def remove_orphan(rel: str) -> None:
    """Delete an orphaned file from $HOME regardless of local edits.

    The force override for prune's anti-clobber — only call after the user
    confirmed (TUI dialog).
    """
    dest = Path.home() / rel
    if dest.exists():
        dest.unlink()
        _remove_empty_parents(dest.parent, Path.home())
    deployed = state.load()
    deployed.pop(rel, None)
    state.save(deployed)
    print(f"files: removed orphan {rel} from $HOME", flush=True)


def prune(desired: set[str] | frozenset[str], force: bool = False) -> None:
    """Remove previously deployed files that fell out of the desired set.

    `desired` holds $HOME-relative paths that should stay (every tracked
    file of every enabled module). Anything else recorded in the deployed
    state is deleted from $HOME — this is what makes disabling a module or
    untracking a file declarative.

    Anti-clobber: a file whose current content no longer matches the hash
    recorded at deploy time was edited by the user; it is kept (with a
    warning, repeated every switch) unless force=True. Comparison is pure
    hashing, so pruning secrets needs no sops/age key.
    """
    home = Path.home()
    deployed = state.load()

    for rel in [r for r in deployed if r not in desired]:
        dest = home / rel
        if not dest.exists():
            del deployed[rel]
            continue
        if not force and state.digest(dest.read_bytes()) != deployed[rel].sha256:
            print(f"Warning: {rel} has local changes; kept.", flush=True)
            print("         Resolve in the TUI: track it (n) or delete it (x).", flush=True)
            continue
        dest.unlink()
        _remove_empty_parents(dest.parent, home)
        del deployed[rel]
        print(f"files: pruned {rel} from $HOME", flush=True)

    state.save(deployed)


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

    Every file that ends up matching the repo (freshly written or already
    in sync) is recorded in the deployed state so prune() can later remove
    it declaratively. Skipped secrets and conflicts keep whatever state
    entry they already have.
    """
    home = Path.home()
    conflicts: list[str] = []
    deployed = state.load()

    for spec in mf.load(module_dir):
        storage = mf.storage_path(module_dir, spec)
        if not storage.exists():
            raise FileNotFoundError(
                f"{module_dir.name}: manifest lists {spec.path} but {storage} is missing"
            )
        if spec.fragment:
            print(
                f"files: skipped fragment {spec.path} (composed at deploy-all/apply time)",
                flush=True,
            )
            continue
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
        entry = state.DeployedEntry(module_dir.name, spec.mode, state.digest(data))

        if dest.exists():
            if data == dest.read_bytes():
                deployed[spec.path] = entry
                continue
            if not overwrite:
                print(f"Error: {spec.path} has local changes.", flush=True)
                print("       Use the TUI to diff/sync first.", flush=True)
                conflicts.append(spec.path)
                continue
            print(f"Warning: overwriting {spec.path} (overwrite=True).", flush=True)

        _write_home(dest, data)
        deployed[spec.path] = entry
        print(f"files: deployed {spec.path}", flush=True)

    state.save(deployed)
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
    secret) is skipped unless force=True. Removed files are also dropped
    from the deployed state.
    """
    home = Path.home()
    conflicts: list[str] = []
    deployed = state.load()

    for spec in mf.load(module_dir):
        storage = mf.storage_path(module_dir, spec)
        if not storage.exists():
            raise FileNotFoundError(
                f"{module_dir.name}: manifest lists {spec.path} but {storage} is missing"
            )
        if spec.fragment:
            # Other modules may contribute to the composed file; it is
            # pruned by deploy-all once no contributor remains.
            print(
                f"files: skipped fragment {spec.path} (composed file, see deploy-all)",
                flush=True,
            )
            continue
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
        deployed.pop(spec.path, None)
        print(f"files: removed {spec.path} from $HOME", flush=True)

    state.save(deployed)
    if conflicts:
        raise RuntimeError(f"Conflicts, local changes: {', '.join(conflicts)}")


def deploy_one(
    entry: FileEntry,
    overwrite: bool = False,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> None:
    """Deploy a single tracked file (repo → $HOME), same guard as deploy_module."""
    if entry.spec.fragment:
        raise ValueError(
            f"{entry.spec.path} is a fragment; deploy the composed file "
            "via deploy_fragments"
        )
    data = repo_bytes(entry.spec, entry.storage, sops_bin, age_key)
    dest = entry.home_path
    if dest.exists() and data != dest.read_bytes() and not overwrite:
        raise RuntimeError(f"{entry.spec.path} has local changes; diff/sync first")
    _write_home(dest, data)
    _record_deployed(entry, data)
    print(f"files: deployed {entry.spec.path}", flush=True)


def sync(
    entry: FileEntry,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> None:
    """Copy/re-encrypt the $HOME copy back into the repo ($HOME → repo).

    Also refreshes the deployed-state hash: after a sync the $HOME copy is
    the repo content again, so it must count as cleanly deployed (prunable).
    """
    if entry.spec.fragment:
        raise ValueError(
            f"{entry.spec.path} is composed from fragments; sync is ambiguous — "
            "edit the repo fragment and apply instead"
        )
    src = entry.home_path
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src}")
    data = src.read_bytes()
    if entry.is_secret:
        encrypt(data, entry.storage, mf.secret_key_name(entry.spec),
                sops_bin, age_key)
    else:
        entry.storage.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, entry.storage)
    _record_deployed(entry, data)
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
