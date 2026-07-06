"""Machine profile: a committed preset plus local, uncommitted overrides.

Machine state lives in ~/.local/state/dotfiles/profile.json:

    {"preset": "work", "overrides": {"modules": {...}, "settings": {...}}}

Presets live in <repo>/presets/<name>.json:

    {
      "modules": {"shell": {"enable": true, "children": {"atuin": false}}},
      "settings": {"git": {"name": "...", "email": "..."}}
    }

default.json is the base; every other preset holds only its diff from the
default and is layered over it on load (load_preset).

Overrides hold only deltas from the preset; the mutators below prune any
entry that equals the preset value, so `overrides == {}` means "exactly the
preset". lib/profile.nix applies the same merge (lib.recursiveUpdate) on the
Nix side.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .modules import Module
from .paths import profile_path

DEFAULT_PRESET = "default"


@dataclass
class MachineState:
    preset: str = DEFAULT_PRESET
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModuleToggle:
    enabled: bool
    children: dict[str, bool]


@dataclass(frozen=True)
class Resolved:
    modules: dict[str, ModuleToggle]


# -- state file ---------------------------------------------------------------


def _write_json(p: Path, payload: dict[str, Any]) -> None:
    """Atomically write a JSON file (temp file + rename)."""
    p.parent.mkdir(parents=True, exist_ok=True)
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


def load_state(path: Path | None = None) -> MachineState:
    """Load machine state ({"preset": ..., "overrides": {...}})."""
    p = path or profile_path()
    if not p.exists():
        return MachineState()
    data = json.loads(p.read_text())
    return MachineState(
        preset=data.get("preset", DEFAULT_PRESET),
        overrides=data.get("overrides", {}),
    )


def save_state(state: MachineState, path: Path | None = None) -> None:
    """Atomically write machine state."""
    p = path or profile_path()
    _write_json(p, {"preset": state.preset, "overrides": state.overrides})


# -- presets ------------------------------------------------------------------


def presets_dir(repo: Path) -> Path:
    return repo / "presets"


def list_presets(repo: Path) -> list[str]:
    d = presets_dir(repo)
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def load_preset(repo: Path, name: str) -> dict[str, Any]:
    """Load a preset, layered over default.json.

    Non-default presets carry only their diff from the default; the merge
    uses the same recursiveUpdate semantics as lib/profile.nix.
    """
    p = presets_dir(repo) / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(f"preset '{name}' not found at {p}")
    data = json.loads(p.read_text())
    if name == DEFAULT_PRESET:
        return data
    return _deep_merge(load_preset(repo, DEFAULT_PRESET), data)


def add_module_to_preset(repo: Path, preset_name: str, module_name: str) -> None:
    """Commit a module enablement into a preset file.

    Presets are layered over default.json, so writing just the enable flag
    keeps the preset diff-only.
    """
    p = presets_dir(repo) / f"{preset_name}.json"
    if not p.exists():
        raise FileNotFoundError(f"preset '{preset_name}' not found at {p}")
    data = json.loads(p.read_text())
    data.setdefault("modules", {}).setdefault(module_name, {})["enable"] = True
    _write_json(p, data)


# -- resolution ---------------------------------------------------------------


def _deep_merge(base: dict, overlay: dict) -> dict:
    """lib.recursiveUpdate semantics: nested dicts merge, scalars replace."""
    out = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def preset_module_enabled(preset: dict, name: str) -> bool:
    return bool(preset.get("modules", {}).get(name, {}).get("enable", False))


def preset_child_enabled(preset: dict, name: str, child: str) -> bool:
    children = preset.get("modules", {}).get(name, {}).get("children", {})
    return bool(children.get(child, True))


def resolve(preset: dict, state: MachineState, modules: list[Module]) -> Resolved:
    """Effective toggles: preset merged with overrides, sanitized against the
    discovered module set (unknown modules/children in JSON are ignored)."""
    merged = _deep_merge(preset, state.overrides)
    mod_cfg = merged.get("modules", {})
    toggles: dict[str, ModuleToggle] = {}
    for mod in modules:
        raw = mod_cfg.get(mod.name, {})
        raw_children = raw.get("children", {})
        toggles[mod.name] = ModuleToggle(
            enabled=bool(raw.get("enable", False)),
            children={c: bool(raw_children.get(c, True)) for c in mod.children},
        )
    return Resolved(modules=toggles)


# -- mutators (all prune no-op overrides) --------------------------------------


def _prune_empty(d: dict) -> None:
    for k in [k for k, v in d.items() if isinstance(v, dict)]:
        _prune_empty(d[k])
        if not d[k]:
            del d[k]


def set_module_enabled(state: MachineState, preset: dict, name: str, value: bool) -> None:
    mods = state.overrides.setdefault("modules", {}).setdefault(name, {})
    if preset_module_enabled(preset, name) == value:
        mods.pop("enable", None)
    else:
        mods["enable"] = value
    _prune_empty(state.overrides)


def set_child_enabled(
    state: MachineState, preset: dict, name: str, child: str, value: bool
) -> None:
    children = (
        state.overrides.setdefault("modules", {})
        .setdefault(name, {})
        .setdefault("children", {})
    )
    if preset_child_enabled(preset, name, child) == value:
        children.pop(child, None)
    else:
        children[child] = value
    _prune_empty(state.overrides)


def clear_override(state: MachineState, name: str, child: str | None = None) -> None:
    """Revert a module (or one child) to its preset value."""
    mods = state.overrides.get("modules", {})
    entry = mods.get(name)
    if entry is None:
        return
    if child is None:
        mods.pop(name, None)
    else:
        entry.get("children", {}).pop(child, None)
    _prune_empty(state.overrides)


def set_preset(state: MachineState, name: str, reset_overrides: bool = False) -> None:
    state.preset = name
    if reset_overrides:
        state.overrides = {}


def is_module_overridden(state: MachineState, name: str) -> bool:
    return "enable" in state.overrides.get("modules", {}).get(name, {})


def is_child_overridden(state: MachineState, name: str, child: str) -> bool:
    return child in state.overrides.get("modules", {}).get(name, {}).get("children", {})


def override_count(state: MachineState) -> int:
    """Number of individual toggle/setting overrides (leaf values)."""

    def leaves(d: Any) -> int:
        if isinstance(d, dict):
            return sum(leaves(v) for v in d.values())
        return 1

    return leaves(state.overrides) if state.overrides else 0
