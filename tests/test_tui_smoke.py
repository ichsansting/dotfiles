"""Headless smoke tests for the editing TUI (ticket 17): drives the real
dashboard with Textual's Pilot against a real git checkout (a local bare
"origin" stands in for a real remote), so every mutating action's
auto-commit/push actually happens rather than being mocked. See
.scratch/ephemeral-shell/issues/17-editing-tui-crud.md.

Actions that open $EDITOR (`app.suspend()`) are not exercised here —
Textual's headless Pilot doesn't support process suspension
(`SuspendNotSupported`), the same reason dotfiles-old's own TUI smoke tests
never drove its file-edit action either. Those code paths are covered by
manual verification and by core/edit.py's unit tests.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")

from dotfiles.tui.app import EditApp  # noqa: E402
from dotfiles.tui.screens.confirm import ConfirmModal  # noqa: E402
from dotfiles.tui.screens.dashboard import DashboardScreen  # noqa: E402
from dotfiles.tui.screens.form import FormModal  # noqa: E402
from dotfiles.tui.screens.picker import PickerModal  # noqa: E402
from dotfiles.tui.widgets.bundle_tree import BundleTree  # noqa: E402
from dotfiles.tui.widgets.fragment_tree import FragmentTree  # noqa: E402
from dotfiles.tui.widgets.main_pane import MainPane  # noqa: E402
from dotfiles.tui.widgets.preset_tree import PresetTree  # noqa: E402
from conftest import write_bundle_file, write_fragment, write_preset  # noqa: E402


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A fixture bundle/preset/fragment tree, checked into git with a local
    bare 'origin' — every dashboard action commits+pushes for real."""
    work = tmp_path / "work"
    write_bundle_file(work, "vcs", ".gitconfig", "plain", content="[user]\n")
    write_bundle_file(work, "terminal", ".config/starship.toml", "plain", content="")
    write_fragment(work, ".claude/CLAUDE.md", "10", "vcs", "vcs fragment")
    write_preset(work, "default", bundles=["vcs"], settings={"git": {"name": "Test"}})
    write_preset(work, "work1", base="default", bundles=[], settings={})

    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "--bare", "-q", "-b", "main")

    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "seed")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "main")
    return work


async def test_dashboard_mounts_and_focuses(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        assert isinstance(pilot.app.screen, DashboardScreen)
        assert isinstance(pilot.app.focused, PresetTree)

        await pilot.press("2")
        assert isinstance(pilot.app.focused, BundleTree)
        await pilot.press("3")
        assert isinstance(pilot.app.focused, FragmentTree)
        await pilot.press("0")
        assert isinstance(pilot.app.focused, MainPane)
        await pilot.press("1")
        assert isinstance(pilot.app.focused, PresetTree)


async def test_create_bundle_commits_and_pushes(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("2", "n")
        await pilot.pause()
        assert isinstance(pilot.app.screen, FormModal)
        pilot.app.screen.query_one("#field-name").value = "newbundle"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(pilot.app.screen, DashboardScreen)
        assert (repo / "bundles/newbundle/files.json").exists()
        assert json.loads((repo / "bundles/newbundle/files.json").read_text()) == {
            "files": [],
            "packages": [],
        }
        assert _git(repo, "log", "-1", "--format=%s").stdout.strip() == "bundle: create newbundle"
        assert (
            _git(repo, "log", "-1", "--format=%s", "origin/main").stdout.strip()
            == "bundle: create newbundle"
        )


async def test_new_preset_with_base_then_clear_base(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("1", "n")
        await pilot.pause()
        assert isinstance(pilot.app.screen, FormModal)
        pilot.app.screen.query_one("#field-name").value = "work2"
        pilot.app.screen.query_one("#field-base").value = "default"
        await pilot.press("enter")
        await pilot.pause()

        assert json.loads((repo / "presets/work2.json").read_text())["base"] == "default"

        tree = pilot.app.screen.query_one(PresetTree)
        tree.cursor_line = tree._node_map[("preset", "work2")].line
        await pilot.press("b")
        await pilot.pause()
        assert isinstance(pilot.app.screen, PickerModal)
        opts = pilot.app.screen.query_one("#picker-list")
        opts.highlighted = 0  # "(none)" sorts first
        await pilot.press("enter")
        await pilot.pause()

        assert "base" not in json.loads((repo / "presets/work2.json").read_text())


async def test_add_bundle_to_preset_then_toggle_off(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        tree = pilot.app.screen.query_one(PresetTree)
        tree.cursor_line = tree._node_map[("preset", "work1")].line
        await pilot.press("1", "B")
        await pilot.pause()
        assert isinstance(pilot.app.screen, PickerModal)
        opts = pilot.app.screen.query_one("#picker-list")
        opts.highlighted = 0
        chosen = str(opts.get_option_at_index(0).id)
        await pilot.press("enter")
        await pilot.pause()

        data = json.loads((repo / "presets/work1.json").read_text())
        assert data["bundles"] == [chosen]

        tree = pilot.app.screen.query_one(PresetTree)
        tree._node_map[("preset", "work1")].expand()
        await pilot.pause()
        key = ("bundle", "work1", chosen, False)
        tree.cursor_line = tree._node_map[key].line
        await pilot.press("space")
        await pilot.pause()

        assert json.loads((repo / "presets/work1.json").read_text())["bundles"] == []


async def test_toggle_inherited_bundle_warns_without_mutating(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("1")
        tree = pilot.app.screen.query_one(PresetTree)
        tree._node_map[("preset", "work1")].expand()
        await pilot.pause()
        # "vcs" is inherited from work1's base ("default"), not own — never
        # explicitly listed in work1.json.
        key = ("bundle", "work1", "vcs", True)
        tree.cursor_line = tree._node_map[key].line
        await pilot.press("space")
        await pilot.pause()

        assert json.loads((repo / "presets/work1.json").read_text())["bundles"] == []


async def test_new_fragment_owner_is_picked_not_typed(repo: Path, monkeypatch: pytest.MonkeyPatch):
    # No real $EDITOR here: Textual's headless Pilot can't drive app.suspend()
    # (see module docstring). Unset explicitly so an ambient $EDITOR in the
    # dev environment can't make this test flaky.
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.delenv("VISUAL", raising=False)
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("3", "n")
        await pilot.pause()
        assert isinstance(pilot.app.screen, FormModal)
        pilot.app.screen.query_one("#field-target").value = ".config/atuin/config.toml"
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(pilot.app.screen, PickerModal)
        opts = pilot.app.screen.query_one("#picker-list")
        shown = [str(opts.get_option_at_index(i).id) for i in range(opts.option_count)]
        assert shown == sorted({"vcs", "terminal", "default", "work1"})
        opts.highlighted = shown.index("terminal")
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(pilot.app.screen, PickerModal)  # secret picker
        opts = pilot.app.screen.query_one("#picker-list")
        opts.highlighted = 0  # "plain"
        await pilot.press("enter")
        await pilot.pause()

        new_frag = repo / "fragments/.config/atuin/config.toml.d/10-terminal.md"
        assert new_frag.exists()


async def test_delete_preset_blocked_when_used_as_base(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        tree = pilot.app.screen.query_one(PresetTree)
        tree.cursor_line = tree._node_map[("preset", "default")].line
        await pilot.press("1", "d")
        await pilot.pause()
        assert isinstance(pilot.app.screen, ConfirmModal)
        await pilot.press("y")
        await pilot.pause()

        assert isinstance(pilot.app.screen, DashboardScreen)
        assert (repo / "presets/default.json").exists()


async def test_remove_bundle_item(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("2")
        tree = pilot.app.screen.query_one(BundleTree)
        tree._node_map[("bundle", "vcs")].expand()
        await pilot.pause()
        key = ("item", "vcs", ".gitconfig", "plain")
        tree.cursor_line = tree._node_map[key].line
        await pilot.press("d")
        await pilot.pause()
        assert isinstance(pilot.app.screen, ConfirmModal)
        await pilot.press("y")
        await pilot.pause()

        assert not (repo / "bundles/vcs/files/.gitconfig").exists()
        manifest = json.loads((repo / "bundles/vcs/files.json").read_text())
        assert manifest["files"] == []


async def test_fragment_preview_and_reorder(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        await pilot.press("3")
        tree = pilot.app.screen.query_one(FragmentTree)
        tree._node_map[("target", ".claude/CLAUDE.md")].expand()
        await pilot.pause()
        frag_key = ("fragment", ".claude/CLAUDE.md", ".claude/CLAUDE.md.d/10-vcs.md", "vcs", False)
        tree.cursor_line = tree._node_map[frag_key].line

        await pilot.press("enter")
        await pilot.pause()
        pane = pilot.app.screen.query_one(MainPane)
        assert pane.current == "pane-text"

        await pilot.press("R")
        await pilot.pause()
        assert isinstance(pilot.app.screen, FormModal)
        pilot.app.screen.query_one("#field-order").value = "50"
        await pilot.press("enter")
        await pilot.pause()

        assert (repo / "fragments/.claude/CLAUDE.md.d/50-vcs.md").exists()
        assert not (repo / "fragments/.claude/CLAUDE.md.d/10-vcs.md").exists()


async def test_toggle_exclude_fragment_for_selected_preset(repo: Path):
    app = EditApp(repo)
    async with app.run_test(size=(140, 45)) as pilot:
        assert app.state.selected_preset == "default"

        await pilot.press("3")
        tree = pilot.app.screen.query_one(FragmentTree)
        tree._node_map[("target", ".claude/CLAUDE.md")].expand()
        await pilot.pause()
        frag_key = ("fragment", ".claude/CLAUDE.md", ".claude/CLAUDE.md.d/10-vcs.md", "vcs", False)
        tree.cursor_line = tree._node_map[frag_key].line
        await pilot.press("x")
        await pilot.pause()

        settings = json.loads((repo / "presets/default.json").read_text())["settings"]
        assert settings["exclude_fragments"] == [".claude/CLAUDE.md.d/10-vcs.md"]
