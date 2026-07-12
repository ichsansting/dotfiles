"""Bundle/preset/fragment CRUD for the editing TUI (ticket 17), plus the
per-preset preview dry-run (ticket 18).

Every CRUD function here performs one FS mutation against a real, persistent
`root` checkout and returns an `EditResult` (the repo-relative paths it
touched, and a generated commit message) — it never calls git itself. The
caller (the TUI's dashboard) commits+pushes every result through
`gitops.commit_and_push` as the single place "every edit auto-commits" is
guaranteed, rather than scattering git calls across every mutation. See
.scratch/ephemeral-shell/issues/17-editing-tui-crud.md.

Three actions register a manifest/filename entry but leave content-writing
to the caller: `add_bundle_item` (plain mode gets an empty file to open in
$EDITOR; secret mode gets nothing until the caller sops-encrypts into the
reserved path) and `create_fragment` (same split). This lets one $EDITOR or
encrypt round-trip happen between the metadata write and the commit,
without a second core function or a second commit.

`preview` is the one exception to the "mutates `root`, returns an
`EditResult`" shape above: it writes into a caller-supplied scratch
directory instead — never `root`, never committed — and returns a
`PreviewResult`. See .scratch/ephemeral-shell/issues/18-editing-tui-secrets-preview.md.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import materialize

MODE_PLAIN = materialize.MODE_PLAIN
MODE_SECRET = materialize.MODE_SECRET

_SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_ORDER_RE = re.compile(r"^\d+$")


@dataclass(frozen=True)
class EditResult:
    paths: list[str]
    message: str


@dataclass(frozen=True)
class FragmentInfo:
    rel_path: str
    owner: str
    secret: bool


@dataclass(frozen=True)
class PreviewResult:
    packages: list[str]
    settings: dict[str, Any]
    files: list[materialize.PlanEntry]
    secret_paths: list[str]  # secret entries, skipped from `files` — not decrypted for preview


def _validate_slug(kind: str, name: str) -> None:
    if not _SLUG_RE.match(name):
        raise ValueError(f"invalid {kind} name: {name!r} (use letters, digits, - or _)")


def _validate_rel_path(path: str) -> None:
    if not path or path.startswith("/") or path.endswith("/"):
        raise ValueError(f"invalid path: {path!r}")
    if any(part in ("", ".", "..") for part in path.split("/")):
        raise ValueError(f"invalid path: {path!r}")


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


# -- bundles -------------------------------------------------------------


def list_bundles(root: Path) -> list[str]:
    d = root / "bundles"
    return sorted(p.name for p in d.iterdir() if p.is_dir()) if d.exists() else []


def _load_bundle_manifest(root: Path, bundle: str) -> dict:
    bdir = root / "bundles" / bundle
    if not bdir.exists():
        raise FileNotFoundError(f"bundle '{bundle}' not found")
    p = bdir / "files.json"
    return json.loads(p.read_text()) if p.exists() else {"files": [], "packages": []}


def bundle_items(root: Path, bundle: str) -> list[dict]:
    return list(_load_bundle_manifest(root, bundle).get("files", []))


def create_bundle(root: Path, name: str) -> EditResult:
    _validate_slug("bundle", name)
    bdir = root / "bundles" / name
    if bdir.exists():
        raise FileExistsError(f"bundle '{name}' already exists")
    bdir.mkdir(parents=True)
    _save_json(bdir / "files.json", {"files": [], "packages": []})
    return EditResult([f"bundles/{name}/files.json"], f"bundle: create {name}")


def rename_bundle(root: Path, old: str, new: str) -> EditResult:
    _validate_slug("bundle", new)
    old_dir = root / "bundles" / old
    if not old_dir.exists():
        raise FileNotFoundError(f"bundle '{old}' not found")
    new_dir = root / "bundles" / new
    if new_dir.exists():
        raise FileExistsError(f"bundle '{new}' already exists")
    old_dir.rename(new_dir)
    touched = [f"bundles/{old}", f"bundles/{new}"]
    for preset in list_presets(root):
        data = preset_raw(root, preset)
        bundles = data.get("bundles", [])
        if old in bundles:
            data["bundles"] = [new if b == old else b for b in bundles]
            _save_preset_raw(root, preset, data)
            touched.append(f"presets/{preset}.json")
    return EditResult(touched, f"bundle: rename {old} -> {new}")


def delete_bundle(root: Path, name: str) -> EditResult:
    bdir = root / "bundles" / name
    if not bdir.exists():
        raise FileNotFoundError(f"bundle '{name}' not found")
    shutil.rmtree(bdir)
    touched = [f"bundles/{name}"]
    for preset in list_presets(root):
        data = preset_raw(root, preset)
        bundles = data.get("bundles", [])
        if name in bundles:
            data["bundles"] = [b for b in bundles if b != name]
            _save_preset_raw(root, preset, data)
            touched.append(f"presets/{preset}.json")
    return EditResult(touched, f"bundle: delete {name}")


def add_bundle_item(root: Path, bundle: str, path: str, mode: str) -> EditResult:
    """Registers the files.json entry. Plain mode gets an empty file at the
    reserved path for the caller to open in $EDITOR; secret mode leaves the
    path unwritten for the caller to sops-encrypt into. Either way, the
    caller commits `EditResult.paths` only after content lands."""
    _validate_rel_path(path)
    if mode not in (MODE_PLAIN, MODE_SECRET):
        raise ValueError(f"invalid mode: {mode!r}")
    manifest = _load_bundle_manifest(root, bundle)
    files = manifest.setdefault("files", [])
    if any(f["path"] == path for f in files):
        raise FileExistsError(f"{bundle} already tracks {path}")
    files.append({"path": path, "mode": mode})
    _save_json(root / "bundles" / bundle / "files.json", manifest)
    content_path = root / "bundles" / bundle / "files" / path
    content_path.parent.mkdir(parents=True, exist_ok=True)
    if mode == MODE_PLAIN:
        content_path.touch()
    return EditResult(
        [f"bundles/{bundle}/files.json", f"bundles/{bundle}/files/{path}"],
        f"bundle: add {path} to {bundle} ({mode})",
    )


def remove_bundle_item(root: Path, bundle: str, path: str) -> EditResult:
    manifest = _load_bundle_manifest(root, bundle)
    files = manifest.get("files", [])
    if not any(f["path"] == path for f in files):
        raise FileNotFoundError(f"{bundle} does not track {path}")
    manifest["files"] = [f for f in files if f["path"] != path]
    _save_json(root / "bundles" / bundle / "files.json", manifest)
    touched = [f"bundles/{bundle}/files.json"]
    content_path = root / "bundles" / bundle / "files" / path
    if content_path.exists():
        content_path.unlink()
        touched.append(f"bundles/{bundle}/files/{path}")
    return EditResult(touched, f"bundle: remove {path} from {bundle}")


# -- presets ---------------------------------------------------------------


def list_presets(root: Path) -> list[str]:
    d = root / "presets"
    return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []


def preset_raw(root: Path, name: str) -> dict:
    p = root / "presets" / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"preset '{name}' not found")
    return json.loads(p.read_text())


def _save_preset_raw(root: Path, name: str, data: dict) -> None:
    _save_json(root / "presets" / f"{name}.json", data)


def create_preset(root: Path, name: str, base: str | None = None) -> EditResult:
    _validate_slug("preset", name)
    p = root / "presets" / f"{name}.json"
    if p.exists():
        raise FileExistsError(f"preset '{name}' already exists")
    if base is not None and not (root / "presets" / f"{base}.json").exists():
        raise FileNotFoundError(f"base preset '{base}' not found")
    data = {"base": base, "bundles": [], "settings": {}} if base else {"bundles": [], "settings": {}}
    _save_preset_raw(root, name, data)
    suffix = f" (base {base})" if base else ""
    return EditResult([f"presets/{name}.json"], f"preset: create {name}{suffix}")


def delete_preset(root: Path, name: str) -> EditResult:
    p = root / "presets" / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"preset '{name}' not found")
    dependents = [
        o for o in list_presets(root) if o != name and preset_raw(root, o).get("base") == name
    ]
    if dependents:
        raise ValueError(
            f"preset '{name}' is the base of {', '.join(dependents)} — change their base first"
        )
    p.unlink()
    return EditResult([f"presets/{name}.json"], f"preset: delete {name}")


def toggle_bundle_in_preset(root: Path, preset: str, bundle: str) -> EditResult:
    if bundle not in list_bundles(root):
        raise FileNotFoundError(f"bundle '{bundle}' not found")
    data = preset_raw(root, preset)
    bundles = list(data.get("bundles", []))
    if bundle in bundles:
        bundles.remove(bundle)
        verb = "remove"
    else:
        bundles.append(bundle)
        verb = "add"
    data["bundles"] = bundles
    _save_preset_raw(root, preset, data)
    return EditResult([f"presets/{preset}.json"], f"preset: {verb} bundle {bundle} in {preset}")


def _base_chain_contains(root: Path, start: str, target: str) -> bool:
    seen: set[str] = set()
    current: str | None = start
    while current:
        if current == target:
            return True
        if current in seen:
            return False  # a pre-existing cycle elsewhere; not this call's problem
        seen.add(current)
        current = preset_raw(root, current).get("base")
    return False


def valid_bases(root: Path, preset: str) -> list[str]:
    """Presets `preset` could validly take as its base: not itself, and not
    any preset whose own base chain already runs through `preset` (which
    would create a cycle)."""
    return [
        p for p in list_presets(root) if p != preset and not _base_chain_contains(root, p, preset)
    ]


def set_preset_base(root: Path, preset: str, base: str | None) -> EditResult:
    data = preset_raw(root, preset)
    if base is not None:
        if base == preset:
            raise ValueError(f"preset '{preset}' cannot be its own base")
        if not (root / "presets" / f"{base}.json").exists():
            raise FileNotFoundError(f"base preset '{base}' not found")
        if _base_chain_contains(root, base, preset):
            raise ValueError(f"setting base to '{base}' would create a cycle")
        data["base"] = base
    else:
        data.pop("base", None)
    _save_preset_raw(root, preset, data)
    return EditResult([f"presets/{preset}.json"], f"preset: set {preset} base -> {base or '(none)'}")


def set_setting(root: Path, preset: str, key_path: str, value: object) -> EditResult:
    parts = key_path.split(".") if key_path else []
    if not parts or any(not part for part in parts):
        raise ValueError(f"invalid setting key: {key_path!r}")
    data = preset_raw(root, preset)
    settings = data.setdefault("settings", {})
    node = settings
    for part in parts[:-1]:
        nxt = node.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            node[part] = nxt
        node = nxt
    node[parts[-1]] = value
    _save_preset_raw(root, preset, data)
    return EditResult(
        [f"presets/{preset}.json"], f"preset: set {preset}.settings.{key_path} = {value!r}"
    )


def toggle_exclude_fragment(root: Path, preset: str, fragment_rel_path: str) -> EditResult:
    data = preset_raw(root, preset)
    settings = data.setdefault("settings", {})
    excludes = list(settings.get("exclude_fragments", []))
    if fragment_rel_path in excludes:
        excludes.remove(fragment_rel_path)
        verb = "include"
    else:
        excludes.append(fragment_rel_path)
        verb = "exclude"
    if excludes:
        settings["exclude_fragments"] = excludes
    else:
        settings.pop("exclude_fragments", None)
    _save_preset_raw(root, preset, data)
    return EditResult(
        [f"presets/{preset}.json"], f"preset: {verb} fragment {fragment_rel_path} in {preset}"
    )


# -- fragments ---------------------------------------------------------------


def fragment_targets(root: Path) -> dict[str, list[FragmentInfo]]:
    out: dict[str, list[FragmentInfo]] = {}
    for frag in materialize._discover_fragments(root):
        out.setdefault(frag.target, []).append(
            FragmentInfo(rel_path=frag.rel_path, owner=frag.owner, secret=frag.secret)
        )
    for lst in out.values():
        lst.sort(key=lambda f: f.rel_path)
    return out


def _next_order(root: Path, target: str) -> str:
    d = root / "fragments" / f"{target}.d"
    if not d.exists():
        return "10"
    highest = 0
    for f in d.iterdir():
        if materialize.FRAGMENT_NAME_RE.match(f.name):
            highest = max(highest, int(f.name.split("-", 1)[0]))
    return f"{highest + 10:02d}"


def create_fragment(root: Path, target: str, owner: str, secret: bool) -> EditResult:
    """Reserves `fragments/<target>.d/<NN>-<owner>[.secret].md` as an empty
    file (auto-numbered past the highest existing prefix) for the caller to
    fill — via $EDITOR for plain, via sops-encrypt for secret — before
    commit."""
    _validate_rel_path(target)
    _validate_slug("fragment owner", owner)
    order = _next_order(root, target)
    suffix = ".secret.md" if secret else ".md"
    rel_path = f"{target}.d/{order}-{owner}{suffix}"
    p = root / "fragments" / rel_path
    if p.exists():
        raise FileExistsError(f"fragment already exists: {rel_path}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.touch()
    return EditResult([f"fragments/{rel_path}"], f"fragment: create {rel_path}")


def reorder_fragment(root: Path, rel_path: str, new_order: str) -> EditResult:
    if not _ORDER_RE.match(new_order):
        raise ValueError(f"invalid order prefix: {new_order!r}")
    p = root / "fragments" / rel_path
    if not p.exists():
        raise FileNotFoundError(f"fragment not found: {rel_path}")
    match = materialize.FRAGMENT_NAME_RE.match(p.name)
    if not match:
        raise ValueError(f"not a fragment filename: {rel_path}")
    suffix = ".secret.md" if match.group("secret") else ".md"
    new_path = p.with_name(f"{new_order}-{match.group('owner')}{suffix}")
    if new_path.exists():
        raise FileExistsError(f"fragment already exists: {new_path.name}")
    p.rename(new_path)
    new_rel = f"{rel_path.rsplit('/', 1)[0]}/{new_path.name}"
    return EditResult(
        [f"fragments/{rel_path}", f"fragments/{new_rel}"],
        f"fragment: reorder {rel_path} -> {new_rel}",
    )


def delete_fragment(root: Path, rel_path: str) -> EditResult:
    p = root / "fragments" / rel_path
    if not p.exists():
        raise FileNotFoundError(f"fragment not found: {rel_path}")
    p.unlink()
    return EditResult([f"fragments/{rel_path}"], f"fragment: delete {rel_path}")


# -- preview (ticket 18) ------------------------------------------------------


def preview(root: Path, preset_name: str, scratch: Path) -> PreviewResult:
    """Per-preset materialize dry-run: writes the preset's file-write plan
    (ticket 11's `build_plan`, no decrypted secrets supplied) into `scratch`
    — never a real `$HOME`, never committed or pushed — and returns it
    alongside the resolved package list and settings overlay for the
    editing TUI's preview pane.

    Secret-dependent targets are skipped by `build_plan` itself (no
    plaintext to compose without a passphrase); their source keys are
    reported separately via `secret_paths` so the preview can note what it
    couldn't show, rather than silently omitting them.
    """
    preset = materialize.load_preset(root, preset_name)
    plan = materialize.build_plan(root, preset_name)
    for entry in plan:
        out = scratch / entry.path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(entry.content)
    secret_paths = sorted({s.key for s in materialize.required_secrets(root, preset_name)})
    return PreviewResult(
        packages=materialize.resolve_packages(root, preset_name),
        settings=preset.settings,
        files=plan,
        secret_paths=secret_paths,
    )
