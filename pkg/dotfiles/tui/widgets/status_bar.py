"""Top status line: repo · selected preset · bundle/preset counts."""
from __future__ import annotations

from textual.widgets import Static

from ..state import AppState


class StatusBar(Static):
    def update_state(self, state: AppState) -> None:
        preset_txt = (
            f"[b cyan]{state.selected_preset}[/]" if state.selected_preset else "[dim](none)[/]"
        )
        self.update(
            f" [b]dotfiles edit[/b] [dim]{state.repo}[/] · "
            f"preset: {preset_txt} · "
            f"{len(state.bundles)} bundle(s) · {len(state.presets)} preset(s)"
        )
