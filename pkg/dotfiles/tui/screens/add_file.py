"""Track a new file: browse $HOME, pick module and mode (plain/secret).

The module Select carries a trailing "new module…" choice that opens
NewModuleModal; the actual module creation happens in the dashboard handler.

Dismisses with AddChoice or None.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Label, RadioButton, RadioSet, Select

from ...core import agekey
from ...core.manifest import MODE_PLAIN, MODE_SECRET
from .new_module import NewModuleModal

# Sentinel Select value; module names can never start with "_" (modules.NAME_RE).
NEW_MODULE = "__new_module__"


@dataclass(frozen=True)
class AddChoice:
    rel: str
    module: str
    mode: str
    new_module_description: str | None = None  # not None => create module first
    new_module_in_preset: bool = False  # enable the new module in the preset


AddResult = AddChoice | None


class AddFileModal(ModalScreen[AddResult]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, module_names: list[str], repo: Path, preset: str) -> None:
        super().__init__()
        self._modules = module_names
        self._repo = repo
        self._preset = preset
        self._selected_rel: str | None = None
        # (name, description, in_preset) from NewModuleModal
        self._pending_new: tuple[str, str, bool] | None = None

    def compose(self) -> ComposeResult:
        with Container(id="add-container"):
            yield Label("Track a file — browse $HOME and select it", id="add-title")
            yield DirectoryTree(str(Path.home()), id="file-tree")
            yield Label("No file selected", id="picked-path")
            with Horizontal(id="add-fields"):
                with Container(id="add-module-field"):
                    yield Label("Module", classes="field-label")
                    yield Select(
                        self._select_options(),
                        id="module-select",
                        allow_blank=True,
                    )
                with Container(id="add-mode-field"):
                    yield Label("Mode", classes="field-label")
                    with RadioSet(id="mode-set"):
                        yield RadioButton("plain (committed as-is)", value=True, id="mode-plain")
                        yield RadioButton(
                            "secret (sops-encrypted)",
                            id="mode-secret",
                            disabled=not agekey.has_key(),
                        )
            with Horizontal(id="add-buttons"):
                yield Button("Add", id="confirm-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def _select_options(self) -> list[tuple[str, str]]:
        options = [(name, name) for name in self._modules]
        if self._pending_new is not None:
            name = self._pending_new[0]
            options.append((f"{name} (new)", name))
        options.append(("＋ new module…", NEW_MODULE))
        return options

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        home = Path.home()
        try:
            rel = event.path.resolve().relative_to(home).as_posix()
        except ValueError:
            self.query_one("#picked-path", Label).update("[red]File must be inside $HOME[/red]")
            self._selected_rel = None
            return
        self._selected_rel = rel
        self.query_one("#picked-path", Label).update(f"Selected: {rel}")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "module-select" or event.value != NEW_MODULE:
            return

        def _on_result(result: tuple[str, str, bool] | None) -> None:
            select = self.query_one("#module-select", Select)
            if result is None:
                select.value = Select.BLANK
                return
            self._pending_new = result
            select.set_options(self._select_options())
            select.value = result[0]  # set_options resets the value

        self.app.push_screen(NewModuleModal(self._repo, self._preset), _on_result)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        picked = self.query_one("#picked-path", Label)
        if not self._selected_rel:
            picked.update("[red]Pick a file first[/red]")
            return
        module_select = self.query_one("#module-select", Select)
        if module_select.value is Select.BLANK or module_select.value == NEW_MODULE:
            picked.update("[red]Choose a module[/red]")
            return
        module = str(module_select.value)
        mode = (
            MODE_SECRET
            if self.query_one("#mode-secret", RadioButton).value
            else MODE_PLAIN
        )
        new_desc = None
        in_preset = False
        if self._pending_new is not None and module == self._pending_new[0]:
            new_desc = self._pending_new[1]
            in_preset = self._pending_new[2]
        self.dismiss(AddChoice(self._selected_rel, module, mode, new_desc, in_preset))

    def action_cancel(self) -> None:
        self.dismiss(None)
