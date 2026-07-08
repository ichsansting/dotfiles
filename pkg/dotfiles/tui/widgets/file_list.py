"""Panel 2: tracked files across all modules (plain + secret unified).

Also lists orphans — files recorded in the deployed state that no enabled
module tracks anymore. Clean orphans just announce that the next apply
removes them; edited ones wait for a decision (track with n, delete with x).
"""
from __future__ import annotations

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.widgets import DataTable

from ...core import files
from ..state import AppState

_STATE_STYLE = {
    files.IN_SYNC: ("✓", "green"),
    files.CHANGED: ("!", "yellow"),
    files.MISSING: ("✗", "red"),
    files.LOCKED: ("~", "dim"),
}


class FileList(DataTable):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "file_action('preview')", "Preview", show=False),
        Binding("d", "file_action('diff')", "Diff"),
        Binding("s", "file_action('sync')", "Sync ↑"),
        Binding("D", "file_action('deploy')", "Deploy ↓"),
        Binding("n", "file_action('add')", "Add"),
        Binding("m", "file_action('move')", "Move"),
        Binding("x", "file_action('remove')", "Untrack"),
        Binding("e", "file_action('edit')", "Edit"),
    ]

    class Action(Message):
        def __init__(
            self,
            action: str,
            entry: files.FileEntry | None,
            orphan: files.OrphanEntry | None = None,
        ) -> None:
            super().__init__()
            self.action = action
            self.entry = entry
            self.orphan = orphan

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self._entries: dict[str, files.FileEntry] = {}
        self._orphans: dict[str, files.OrphanEntry] = {}

    def on_mount(self) -> None:
        self.add_column("mod", key="module")
        self.add_column("", key="mode")
        self.add_column("path", key="path")
        self.add_column("", key="state")

    def update_entries(self, state: AppState) -> None:
        prev_key = None
        if self.row_count and self.cursor_row >= 0:
            prev_key = self.coordinate_to_cell_key((self.cursor_row, 0)).row_key.value
        self.clear()
        self._entries = {}
        self._orphans = {}
        for entry in state.entries:
            key = f"{entry.module}:{entry.spec.path}"
            self._entries[key] = entry
            glyph, style = _STATE_STYLE[entry.state]
            mode = Text("S", style="magenta") if entry.is_secret else Text("P", style="cyan")
            self.add_row(
                Text(entry.module, style="dim"),
                mode,
                entry.spec.path,
                Text(glyph, style=style),
                key=key,
            )
        for orphan in state.orphans:
            key = f"orphan:{orphan.path}"
            self._orphans[key] = orphan
            # Edited orphans need a decision; clean ones go on next apply.
            glyph, style = ("!", "yellow") if orphan.edited else ("†", "dim")
            self.add_row(
                Text(f"({orphan.module})", style="dim strike"),
                Text("O", style="dim"),
                Text(orphan.path, style="" if orphan.edited else "dim"),
                Text(glyph, style=style),
                key=key,
            )
        if prev_key is not None and (prev_key in self._entries or prev_key in self._orphans):
            self.move_cursor(row=self.get_row_index(prev_key))

    def _current_key(self) -> str | None:
        if not self.row_count or self.cursor_row < 0:
            return None
        return self.coordinate_to_cell_key((self.cursor_row, 0)).row_key.value

    def current_entry(self) -> files.FileEntry | None:
        key = self._current_key()
        return self._entries.get(key) if key else None

    def current_orphan(self) -> files.OrphanEntry | None:
        key = self._current_key()
        return self._orphans.get(key) if key else None

    def action_file_action(self, action: str) -> None:
        self.post_message(self.Action(action, self.current_entry(), self.current_orphan()))
