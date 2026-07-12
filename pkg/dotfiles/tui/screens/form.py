"""Generic text-entry modal — the shared shape behind every "type a
name/path/value" prompt in the editing TUI (new bundle name, rename,
preset name/base, item path, setting key/value, fragment target/owner,
reorder prefix). Dismisses with a dict of field key -> stripped value, or
None if cancelled."""
from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

FormValues = dict[str, str]
FormField = tuple[str, str, str]  # (key, label, initial value)


class FormModal(ModalScreen[FormValues | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        title: str,
        fields: list[FormField],
        confirm_label: str = "Confirm",
        validate: Callable[[FormValues], str | None] | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._fields = fields
        self._confirm_label = confirm_label
        self._validate = validate

    def compose(self) -> ComposeResult:
        with Container(id="form-container"):
            yield Label(self._title, id="form-title")
            for key, label, default in self._fields:
                yield Label(label, classes="field-label")
                yield Input(value=default, id=f"field-{key}")
            yield Label("", id="form-error")
            with Horizontal(id="form-buttons"):
                yield Button(self._confirm_label, id="confirm-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def _values(self) -> FormValues:
        return {
            key: self.query_one(f"#field-{key}", Input).value.strip() for key, _, _ in self._fields
        }

    def on_input_changed(self, event: Input.Changed) -> None:
        if not self._validate:
            return
        error = self._validate(self._values())
        self.query_one("#form-error", Label).update(f"[red]{error}[/]" if error else "")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._confirm()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        self._confirm()

    def _confirm(self) -> None:
        values = self._values()
        if self._validate:
            error = self._validate(values)
            if error:
                self.query_one("#form-error", Label).update(f"[red]{error}[/]")
                return
        self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(None)
