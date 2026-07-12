"""Generic single-select modal over an OptionList — the shared shape
behind every "pick one of these" prompt (preset base, bundle to add,
plain/secret mode). Dismisses with the chosen option id, or None."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Label, OptionList
from textual.widgets.option_list import Option


class PickerModal(ModalScreen[str | None]):
    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self, title: str, options: list[str], note: str = "", confirm_label: str = "Select"
    ) -> None:
        super().__init__()
        self._title = title
        self._options = options
        self._note = note
        self._confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Container(id="picker-container"):
            yield Label(self._title, id="picker-title")
            if self._note:
                yield Label(self._note, id="picker-note")
            yield OptionList(*[Option(o, id=o) for o in self._options], id="picker-list")
            with Horizontal(id="picker-buttons"):
                yield Button(self._confirm_label, id="confirm-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn")

    def _selected(self) -> str | None:
        opts = self.query_one("#picker-list", OptionList)
        if opts.highlighted is None:
            return None
        return str(opts.get_option_at_index(opts.highlighted).id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.id))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        selected = self._selected()
        if selected is None:
            self.notify("Pick one first", severity="warning")
            return
        self.dismiss(selected)

    def action_cancel(self) -> None:
        self.dismiss(None)
