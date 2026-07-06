"""Top status line: repo · preset (+overrides) · age key state."""
from __future__ import annotations

from textual.widgets import Static

from ...core import agekey
from ..state import AppState


class StatusBar(Static):
    def update_state(self, state: AppState) -> None:
        overrides = state.override_count()
        override_txt = f" [yellow]+{overrides} override{'s' if overrides != 1 else ''}[/]" \
            if overrides else ""
        key_txt = "[green]age key ✓[/]" if agekey.has_key() else "[red]age key ✗[/]"
        self.update(
            f" [b]dotfiles[/b] [dim]{state.repo}[/] · "
            f"preset: [b cyan]{state.machine.preset}[/]{override_txt} · {key_txt}"
        )
