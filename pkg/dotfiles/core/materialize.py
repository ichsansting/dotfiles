"""Materialize core: resolves a preset into a bundle list, settings overlay,
composed fragments, and a file-write plan.

Pure and stdlib-only — never invokes Nix, sops, or git, and never touches a
live filesystem session. All external state (decrypted secrets, the
bundle/preset/fragment definition tree) is passed in as data. See
.scratch/ephemeral-shell/spec.md ("Fragment composition") for the design.

Fixture/repo tree layout:

    presets/<name>.json         {"base": "<name>"?, "bundles": [...], "settings": {...}}
    bundles/<name>/files.json   {"files": [{"path": "<home-rel>", "mode": "plain"|"secret"}]}
    bundles/<name>/files/<path> plain whole-file content
    fragments/<target>.d/<NN>-<owner>.md          plain fragment
    fragments/<target>.d/<NN>-<owner>.secret.md   secret fragment

A preset's `settings.exclude_fragments` (a list of fragment paths relative to
fragments/, e.g. ".claude/CLAUDE.md.d/10-vcs.md") suppresses individual
contributors. Secret content — whole-file or fragment — is never read from
disk here; it comes from `decrypted_secrets`, keyed by the whole-file's
$HOME-relative path or the fragment's path relative to fragments/.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FRAGMENT_NAME_RE = re.compile(r"^\d+-(?P<owner>.+?)(?P<secret>\.secret)?\.md$")

MODE_PLAIN = "plain"
MODE_SECRET = "secret"


class ConfigError(Exception):
    """A target path is claimed by conflicting whole-file/fragment owners."""


@dataclass(frozen=True)
class Preset:
    name: str
    bundles: list[str]
    settings: dict[str, Any]


@dataclass(frozen=True)
class PlanEntry:
    path: str
    content: bytes
    mode: str  # MODE_PLAIN | MODE_SECRET


@dataclass(frozen=True)
class _FileSpec:
    path: str
    mode: str


@dataclass(frozen=True)
class _Fragment:
    target: str
    owner: str
    rel_path: str  # relative to fragments/, e.g. ".claude/CLAUDE.md.d/10-vcs.md"
    file: Path
    secret: bool


@dataclass(frozen=True)
class SecretSource:
    key: str  # the decrypted_secrets key this source decrypts into
    source: Path  # on-disk sops-encrypted file (binary format)


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_preset(root: Path, name: str) -> Preset:
    """Resolve a preset's bundle list and settings overlay, applying
    base-preset inheritance: inherited bundles come first, own bundles are
    appended (deduped); own settings values override the base's."""
    p = root / "presets" / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"preset '{name}' not found at {p}")
    data = json.loads(p.read_text())
    own_bundles = list(data.get("bundles", []))
    own_settings = dict(data.get("settings", {}))

    base_name = data.get("base")
    if not base_name:
        return Preset(name=name, bundles=own_bundles, settings=own_settings)

    base = load_preset(root, base_name)
    bundles = list(base.bundles)
    for b in own_bundles:
        if b not in bundles:
            bundles.append(b)
    return Preset(name=name, bundles=bundles, settings=_deep_merge(base.settings, own_settings))


def _bundle_files(root: Path, bundle: str) -> list[_FileSpec]:
    p = root / "bundles" / bundle / "files.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return [_FileSpec(path=e["path"], mode=e["mode"]) for e in data.get("files", [])]


def _bundle_packages(root: Path, bundle: str) -> list[str]:
    p = root / "bundles" / bundle / "files.json"
    if not p.exists():
        return []
    data = json.loads(p.read_text())
    return list(data.get("packages", []))


def resolve_packages(root: Path, preset_name: str) -> list[str]:
    """Resolved package list for a preset: each active bundle's `packages`
    array (in `files.json`, alongside its file list), unioned in bundle
    order and first-occurrence deduped. Informational only — `bin/assemble`
    resolves packages by handing bundle names to `nix shell` directly, never
    a flattened attribute-name list; this is for display (ticket 18's
    preview), not for driving the actual `nix shell` invocation."""
    preset = load_preset(root, preset_name)
    seen: set[str] = set()
    packages: list[str] = []
    for bundle in preset.bundles:
        for pkg in _bundle_packages(root, bundle):
            if pkg not in seen:
                seen.add(pkg)
                packages.append(pkg)
    return packages


def _read_bundle_file(root: Path, bundle: str, path: str) -> bytes:
    p = root / "bundles" / bundle / "files" / path
    if not p.exists():
        raise FileNotFoundError(f"{bundle}: files.json lists {path!r} but {p} is missing")
    return p.read_bytes()


def _resolve(secret: bool, secret_key: str, decrypted_secrets: dict[str, bytes], read_plain) -> bytes | None:
    """Shared shape for both whole-file and fragment content: a secret
    entry's bytes come only from `decrypted_secrets` (None if unavailable —
    the caller must skip, never write a partial result); a plain entry's
    bytes are read from disk via `read_plain`."""
    return decrypted_secrets.get(secret_key) if secret else read_plain()


def _discover_fragments(root: Path) -> list[_Fragment]:
    frag_root = root / "fragments"
    if not frag_root.exists():
        return []
    fragments = []
    for d in sorted(p for p in frag_root.rglob("*.d") if p.is_dir()):
        target = d.relative_to(frag_root).as_posix().removesuffix(".d")
        for f in sorted(d.iterdir()):
            match = FRAGMENT_NAME_RE.match(f.name)
            if not match:
                continue
            fragments.append(
                _Fragment(
                    target=target,
                    owner=match.group("owner"),
                    rel_path=f.relative_to(frag_root).as_posix(),
                    file=f,
                    secret=bool(match.group("secret")),
                )
            )
    return fragments


def _active_fragments(root: Path, preset: Preset) -> dict[str, list[_Fragment]]:
    excluded = set(preset.settings.get("exclude_fragments", []))
    active_owners = set(preset.bundles) | {preset.name}
    targets: dict[str, list[_Fragment]] = {}
    for frag in _discover_fragments(root):
        if frag.owner not in active_owners or frag.rel_path in excluded:
            continue
        targets.setdefault(frag.target, []).append(frag)
    return targets


def _compose(fragments: list[_Fragment], decrypted_secrets: dict[str, bytes]) -> bytes | None:
    """None means a secret contributor's content is unavailable — the whole
    target must be skipped rather than partially written."""
    parts = []
    for frag in sorted(fragments, key=lambda f: f.rel_path):
        data = _resolve(frag.secret, frag.rel_path, decrypted_secrets, frag.file.read_bytes)
        if data is None:
            return None
        parts.append(data.rstrip(b"\n"))
    parts = [p for p in parts if p]
    return b"\n\n".join(parts) + b"\n" if parts else b""


def required_secrets(root: Path, preset_name: str) -> list[SecretSource]:
    """On-disk sops-encrypted sources (binary format) a preset's file-write
    plan depends on: whole-file secrets at the same `bundles/<b>/files/<path>`
    a plain file would use, and secret fragments at their existing
    `fragments/<target>.d/<NN>-<owner>.secret.md` location. A caller (the
    secrets bootstrap step) decrypts each and passes the result back into
    `build_plan`'s `decrypted_secrets`, rather than duplicating bundle/preset
    resolution."""
    preset = load_preset(root, preset_name)
    sources: list[SecretSource] = []
    for bundle in preset.bundles:
        for spec in _bundle_files(root, bundle):
            if spec.mode == MODE_SECRET:
                sources.append(SecretSource(key=spec.path, source=root / "bundles" / bundle / "files" / spec.path))
    for frags in _active_fragments(root, preset).values():
        for frag in frags:
            if frag.secret:
                sources.append(SecretSource(key=frag.rel_path, source=frag.file))
    return sources


def build_plan(
    root: Path, preset_name: str, decrypted_secrets: dict[str, bytes] | None = None
) -> list[PlanEntry]:
    """Resolve a preset into its final file-write plan.

    Raises ConfigError if any target path is claimed by both a whole-file
    owner and a fragment owner, or by more than one whole-file owner. A
    target whose content depends on an unavailable secret (whole-file or any
    fragment contributor) is skipped entirely, not partially written.
    """
    decrypted_secrets = decrypted_secrets or {}
    preset = load_preset(root, preset_name)

    whole: dict[str, list[tuple[str, _FileSpec]]] = {}
    for bundle in preset.bundles:
        for spec in _bundle_files(root, bundle):
            whole.setdefault(spec.path, []).append((bundle, spec))

    fragment_targets = _active_fragments(root, preset)

    errors = []
    for path, owners in whole.items():
        if path in fragment_targets:
            errors.append(f"{path}: whole-file owned by {owners[0][0]} but also fragment-composed")
        elif len(owners) > 1:
            names = ", ".join(o[0] for o in owners)
            errors.append(f"{path}: multiple whole-file owners: {names}")
    if errors:
        raise ConfigError("; ".join(errors))

    plan: list[PlanEntry] = []
    for path in sorted(whole):
        bundle, spec = whole[path][0]
        secret = spec.mode == MODE_SECRET
        data = _resolve(secret, path, decrypted_secrets, lambda b=bundle, p=path: _read_bundle_file(root, b, p))
        if data is None:
            continue
        plan.append(PlanEntry(path=path, content=data, mode=spec.mode))

    for path in sorted(fragment_targets):
        frags = fragment_targets[path]
        content = _compose(frags, decrypted_secrets)
        if content is None or content == b"":
            continue  # secret unavailable, or every surviving fragment was empty
        mode = MODE_SECRET if any(f.secret for f in frags) else MODE_PLAIN
        plan.append(PlanEntry(path=path, content=content, mode=mode))

    return plan
