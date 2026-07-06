"""Move a tracked file to another module (repo-side, mode preserved).

Dismisses with the destination module name or None.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option


class MoveFileModal(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, path: str, src_module: str, destinations: list[str]) -> None:
        super().__init__()
        self._path = path
        self._src = src_module
        self._destinations = destinations

    def compose(self) -> ComposeResult:
        with Container(id="move-container"):
            yield Label("Move file", id="move-title")
            yield Label(f"{self._path}  ({self._src} → …)", id="move-note")
            yield OptionList(
                *[Option(name, id=name) for name in self._destinations],
                id="move-list",
            )
            with Horizontal(id="move-buttons"):
                yield Button("Move", id="confirm-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        opts = self.query_one("#move-list", OptionList)
        if opts.highlighted is None:
            self.notify("Pick a module first", severity="warning")
            return
        self.dismiss(opts.get_option_at_index(opts.highlighted).id)

    def action_cancel(self) -> None:
        self.dismiss(None)
