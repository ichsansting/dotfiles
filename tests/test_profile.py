from __future__ import annotations

import json
from pathlib import Path

import pytest

from dotfiles.core import modules, profile


def _mods(repo: Path):
    return modules.discover(repo)


def test_load_state_missing_file(home: Path):
    st = profile.load_state()
    assert st.preset == "default"
    assert st.overrides == {}


def test_save_state_atomic_roundtrip(home: Path):
    st = profile.MachineState(preset="work", overrides={"modules": {"git": {"enable": True}}})
    profile.save_state(st)
    loaded = profile.load_state()
    assert loaded == st
    # no temp file litter
    leftovers = [
        f for f in (home / ".local/state/dotfiles").iterdir() if f.name != "profile.json"
    ]
    assert leftovers == []


def test_resolve_preset_defaults(repo: Path, home: Path):
    preset = profile.load_preset(repo, "default")
    res = profile.resolve(preset, profile.MachineState(), _mods(repo))
    assert res.modules["shell"].enabled is True
    assert res.modules["shell"].children == {"fish": True, "atuin": True}


def test_resolve_work_preset_child_off(repo: Path, home: Path):
    preset = profile.load_preset(repo, "work")
    st = profile.MachineState(preset="work")
    res = profile.resolve(preset, st, _mods(repo))
    assert res.modules["shell"].children["atuin"] is False
    assert res.modules["git"].enabled is False


def test_load_preset_layers_over_default(repo: Path):
    (repo / "presets/personal.json").write_text(
        json.dumps({"modules": {"git": {"enable": False}}}) + "\n"
    )
    preset = profile.load_preset(repo, "personal")
    assert preset["modules"]["shell"]["enable"] is True  # inherited from default
    assert preset["modules"]["git"]["enable"] is False  # the preset's own diff
    assert preset["settings"]["git"]["name"] == "Test"  # settings inherited too


def test_resolve_ignores_unknown_keys(repo: Path, home: Path):
    preset = profile.load_preset(repo, "default")
    st = profile.MachineState(
        overrides={"modules": {"nope": {"enable": True}, "shell": {"children": {"zzz": False}}}}
    )
    res = profile.resolve(preset, st, _mods(repo))
    assert "nope" not in res.modules
    assert set(res.modules["shell"].children) == {"fish", "atuin"}


def test_mutators_prune_noop_overrides(repo: Path, home: Path):
    preset = profile.load_preset(repo, "default")  # shell on, atuin default-on
    st = profile.MachineState()

    profile.set_child_enabled(st, preset, "shell", "atuin", False)
    assert st.overrides == {"modules": {"shell": {"children": {"atuin": False}}}}
    assert profile.is_child_overridden(st, "shell", "atuin")
    assert profile.override_count(st) == 1

    # setting back to the preset value removes the override entirely
    profile.set_child_enabled(st, preset, "shell", "atuin", True)
    assert st.overrides == {}
    assert profile.override_count(st) == 0


def test_module_toggle_and_clear(repo: Path, home: Path):
    preset = profile.load_preset(repo, "default")
    st = profile.MachineState()
    profile.set_module_enabled(st, preset, "git", False)
    assert st.overrides == {"modules": {"git": {"enable": False}}}
    profile.clear_override(st, "git")
    assert st.overrides == {}


def test_set_preset_optionally_resets(repo: Path, home: Path):
    st = profile.MachineState(overrides={"modules": {"git": {"enable": False}}})
    profile.set_preset(st, "work")
    assert st.preset == "work" and st.overrides
    profile.set_preset(st, "default", reset_overrides=True)
    assert st.overrides == {}


def test_list_presets(repo: Path):
    assert profile.list_presets(repo) == ["default", "work"]


def test_add_module_to_preset(repo: Path):
    profile.add_module_to_preset(repo, "work", "newmod")
    data = json.loads((repo / "presets/work.json").read_text())
    assert data["modules"]["newmod"] == {"enable": True}
    # existing preset content is untouched
    assert data["modules"]["shell"]["children"]["atuin"] is False

    with pytest.raises(FileNotFoundError):
        profile.add_module_to_preset(repo, "nope", "newmod")
