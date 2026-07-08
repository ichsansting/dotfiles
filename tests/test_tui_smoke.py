"""Headless smoke tests for the Textual dashboard (textual Pilot)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

textual = pytest.importorskip("textual")

from dotfiles.core import profile  # noqa: E402
from dotfiles.tui.app import DotfilesApp  # noqa: E402
from dotfiles.tui.screens.dashboard import DashboardScreen  # noqa: E402
from dotfiles.tui.widgets.file_list import FileList  # noqa: E402
from dotfiles.tui.widgets.main_pane import MainPane  # noqa: E402
from dotfiles.tui.widgets.module_tree import ModuleTree  # noqa: E402


@pytest.fixture
def tui_repo(repo: Path, home: Path) -> Path:
    """Repo fixture plus a tracked plain file and an age key stub (so the
    first-run AgeKeyScreen doesn't cover the dashboard)."""
    key = home / ".config/sops/age/keys.txt"
    key.parent.mkdir(parents=True)
    key.write_text("# stub\n")

    storage = repo / "modules/git/files/.gitconfig"
    storage.parent.mkdir(parents=True)
    storage.write_text("[user]\n")
    (repo / "modules/git/files.json").write_text(
        json.dumps({"files": [{"path": ".gitconfig", "mode": "plain"}]})
    )
    return repo


async def test_dashboard_mounts_and_focuses(tui_repo: Path):
    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        assert isinstance(pilot.app.screen, DashboardScreen)
        assert isinstance(pilot.app.focused, ModuleTree)

        await pilot.press("2")
        assert isinstance(pilot.app.focused, FileList)
        await pilot.press("0")
        assert isinstance(pilot.app.focused, MainPane)
        await pilot.press("1")
        assert isinstance(pilot.app.focused, ModuleTree)


async def test_space_toggle_writes_override(tui_repo: Path, home: Path):
    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        # cursor starts on the first module (git, enabled in default preset)
        await pilot.press("space")
        await pilot.pause()

        saved = profile.load_state()
        assert saved.overrides == {"modules": {"git": {"enable": False}}}

        # toggling back prunes the override
        await pilot.press("space")
        await pilot.pause()
        assert profile.load_state().overrides == {}


async def test_child_toggle_and_clear(tui_repo: Path, home: Path):
    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        tree = pilot.app.screen.query_one(ModuleTree)
        # expand shell, then move to its "atuin" child
        tree._node_map[("shell", None)].expand()
        await pilot.pause()
        tree.cursor_line = tree._node_map[("shell", "atuin")].line
        await pilot.press("space")
        await pilot.pause()
        assert profile.load_state().overrides == {
            "modules": {"shell": {"children": {"atuin": False}}}
        }

        await pilot.press("x")  # clear override
        await pilot.pause()
        assert profile.load_state().overrides == {}


async def test_file_preview_and_diff(tui_repo: Path, home: Path):
    (home / ".gitconfig").write_text("[user]\n\tname = local\n")
    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("2")  # focus files panel
        await pilot.press("enter")  # preview
        pane = pilot.app.screen.query_one(MainPane)
        assert pane.current == "pane-text"

        await pilot.press("2", "d")  # diff
        await pilot.pause()
        assert pane.current == "pane-text"
        assert "diff .gitconfig" in str(pane.border_title)


async def test_new_module_key_creates_and_enables(tui_repo: Path, home: Path):
    from textual.widgets import Input

    from dotfiles.tui.screens.new_module import NewModuleModal

    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("N")
        assert isinstance(pilot.app.screen, NewModuleModal)

        pilot.app.screen.query_one("#newmod-name", Input).value = "personal"
        pilot.app.screen.query_one("#newmod-desc", Input).value = "my secrets"
        await pilot.app.screen.query_one("#newmod-name", Input).action_submit()
        await pilot.pause()

        assert isinstance(pilot.app.screen, DashboardScreen)
        d = tui_repo / "modules" / "personal"
        assert (d / "default.nix").exists() and (d / "module.json").exists()
        # enabled as a machine-local override, not in any preset
        assert profile.load_state().overrides == {
            "modules": {"personal": {"enable": True}}
        }
        tree = pilot.app.screen.query_one(ModuleTree)
        assert ("personal", None) in tree._node_map


async def test_new_module_key_into_preset(tui_repo: Path, home: Path):
    from textual.widgets import Input, RadioButton

    from dotfiles.tui.screens.new_module import NewModuleModal

    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("N")
        assert isinstance(pilot.app.screen, NewModuleModal)

        pilot.app.screen.query_one("#newmod-name", Input).value = "personal"
        pilot.app.screen.query_one("#scope-preset", RadioButton).toggle()
        await pilot.pause()
        await pilot.app.screen.query_one("#newmod-name", Input).action_submit()
        await pilot.pause()

        assert isinstance(pilot.app.screen, DashboardScreen)
        preset = json.loads((tui_repo / "presets/default.json").read_text())
        assert preset["modules"]["personal"] == {"enable": True}
        # the preset carries the enablement — no machine-local override
        assert profile.load_state().overrides == {}
        tree = pilot.app.screen.query_one(ModuleTree)
        assert ("personal", None) in tree._node_map


async def test_move_file_between_modules(tui_repo: Path, home: Path):
    from textual.widgets import OptionList

    from dotfiles.core import manifest as mf
    from dotfiles.tui.screens.move_file import MoveFileModal

    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("2", "m")  # focus files panel, move .gitconfig
        assert isinstance(pilot.app.screen, MoveFileModal)

        opts = pilot.app.screen.query_one("#move-list", OptionList)
        opts.highlighted = 0  # "shell", the only other module
        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(pilot.app.screen, DashboardScreen)
        assert mf.load(tui_repo / "modules/git") == []
        assert mf.load(tui_repo / "modules/shell") == [
            mf.FileSpec(".gitconfig", mf.MODE_PLAIN)
        ]
        assert (tui_repo / "modules/shell/files/.gitconfig").read_text() == "[user]\n"
        fl = pilot.app.screen.query_one(FileList)
        assert "shell:.gitconfig" in fl._entries


async def test_deploy_overwrite_asks_for_confirmation(tui_repo: Path, home: Path):
    from dotfiles.tui.screens.confirm import ConfirmModal

    (home / ".gitconfig").write_text("local edit\n")
    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("2", "D")  # deploy a CHANGED file
        assert isinstance(pilot.app.screen, ConfirmModal)

        await pilot.press("y")  # confirm the overwrite
        await pilot.pause()
        assert isinstance(pilot.app.screen, DashboardScreen)
        assert (home / ".gitconfig").read_text() == "[user]\n"


async def test_deploy_overwrite_cancel_keeps_edits(tui_repo: Path, home: Path):
    from dotfiles.tui.screens.confirm import ConfirmModal

    (home / ".gitconfig").write_text("local edit\n")
    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("2", "D")
        assert isinstance(pilot.app.screen, ConfirmModal)
        await pilot.press("escape")
        await pilot.pause()
        assert (home / ".gitconfig").read_text() == "local edit\n"


async def test_orphan_row_delete_with_confirmation(tui_repo: Path, home: Path):
    from dotfiles.core import state
    from dotfiles.tui.screens.confirm import ConfirmModal

    # An orphan: recorded as deployed, edited locally, tracked by no module.
    (home / ".orphaned").write_text("edited\n")
    state.save(
        {".orphaned": state.DeployedEntry("git", "plain", state.digest(b"original\n"))}
    )
    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        fl = pilot.app.screen.query_one(FileList)
        assert "orphan:.orphaned" in fl._orphans
        assert fl._orphans["orphan:.orphaned"].edited

        await pilot.press("2")
        fl.move_cursor(row=fl.get_row_index("orphan:.orphaned"))
        await pilot.press("x")
        assert isinstance(pilot.app.screen, ConfirmModal)

        await pilot.press("y")
        await pilot.pause()
        assert not (home / ".orphaned").exists()
        assert state.load() == {}
        assert "orphan:.orphaned" not in fl._orphans


async def test_help_overlay(tui_repo: Path):
    app = DotfilesApp(repo=tui_repo)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("question_mark")
        from dotfiles.tui.screens.help import HelpScreen

        assert isinstance(pilot.app.screen, HelpScreen)
        await pilot.press("escape")
        assert isinstance(pilot.app.screen, DashboardScreen)
