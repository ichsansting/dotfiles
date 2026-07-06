"""Preset picker: switch the active preset, optionally dropping local overrides.

Dismisses with (preset_name, reset_overrides) or None.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option

PresetChoice = tuple[str, bool] | None


class PresetModal(ModalScreen[PresetChoice]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, presets: list[str], current: str, override_count: int) -> None:
        super().__init__()
        self._presets = presets
        self._current = current
        self._override_count = override_count

    def compose(self) -> ComposeResult:
        with Container(id="preset-container"):
            yield Label("Switch preset", id="preset-title")
            note = (
                f"{self._override_count} local override(s) are kept unless you reset them."
                if self._override_count
                else "No local overrides on this machine."
            )
            yield Label(note, id="preset-note")
            yield OptionList(
                *[
                    Option(
                        f"{name}  [dim](current)[/]" if name == self._current else name,
                        id=name,
                    )
                    for name in self._presets
                ],
                id="preset-list",
            )
            with Horizontal(id="preset-buttons"):
                yield Button("Switch", id="switch-btn", variant="primary")
                yield Button("Switch + reset overrides", id="reset-btn", variant="warning")
                yield Button("Cancel", id="cancel-btn")

    def _selected(self) -> str | None:
        opts = self.query_one("#preset-list", OptionList)
        if opts.highlighted is None:
            return None
        return opts.get_option_at_index(opts.highlighted).id

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss((str(event.option.id), False))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        name = self._selected()
        if name is None:
            self.notify("Pick a preset first", severity="warning")
            return
        self.dismiss((name, event.button.id == "reset-btn"))

    def action_cancel(self) -> None:
        self.dismiss(None)
