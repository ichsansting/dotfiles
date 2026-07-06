"""Create a new module: name, optional description, and where to enable it
(machine-local override or committed into the active preset).

Dismisses with (name, description, in_preset) or None.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet

from ...core import modules

NewModuleResult = tuple[str, str, bool] | None


class NewModuleModal(ModalScreen[NewModuleResult]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, repo: Path, preset: str) -> None:
        super().__init__()
        self._repo = repo
        self._preset = preset

    def compose(self) -> ComposeResult:
        with Container(id="newmod-container"):
            yield Label("New module", id="newmod-title")
            yield Label("Name", classes="field-label")
            yield Input(placeholder="e.g. personal", id="newmod-name")
            yield Label("Description (optional)", classes="field-label")
            yield Input(placeholder="what this module holds", id="newmod-desc")
            yield Label("Enable in", classes="field-label")
            with RadioSet(id="newmod-scope"):
                yield RadioButton(
                    "this machine only (local override)",
                    value=True,
                    id="scope-machine",
                )
                yield RadioButton(
                    f"preset '{self._preset}' (committed)",
                    id="scope-preset",
                )
            yield Label("", id="newmod-error")
            with Horizontal(id="newmod-buttons"):
                yield Button("Create", id="confirm-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def _validate(self) -> str | None:
        name = self.query_one("#newmod-name", Input).value.strip()
        return modules.validate_name(self._repo, name)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "newmod-name":
            return
        error = self._validate()
        self.query_one("#newmod-error", Label).update(
            f"[red]{error}[/red]" if error and event.value else ""
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        self._confirm()

    def _confirm(self) -> None:
        error = self._validate()
        if error:
            self.query_one("#newmod-error", Label).update(f"[red]{error}[/red]")
            return
        name = self.query_one("#newmod-name", Input).value.strip()
        desc = self.query_one("#newmod-desc", Input).value.strip()
        in_preset = self.query_one("#scope-preset", RadioButton).value
        self.dismiss((name, desc, in_preset))

    def action_cancel(self) -> None:
        self.dismiss(None)
