"""App shell (ticket 17): loads state, mounts the dashboard.

Runs only against a real, persistent git checkout — the repo root comes
from $DOTFILES_REPO (set by the flake's `edit` app wrapper) or the current
directory, never an ephemeral session's throwaway $HOME.
"""
from __future__ import annotations

import os
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from .screens.dashboard import DashboardScreen
from .state import AppState


class EditApp(App):
    TITLE = "dotfiles edit"
    CSS_PATH = "styles.tcss"

    BINDINGS = [Binding("q", "quit", "Quit")]

    def __init__(self, repo: Path) -> None:
        super().__init__()
        self.state = AppState(repo=repo)
        self.state.reload()

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen(self.state))


def main() -> None:
    repo = Path(os.environ.get("DOTFILES_REPO", ".")).resolve()
    EditApp(repo).run()


if __name__ == "__main__":
    main()
