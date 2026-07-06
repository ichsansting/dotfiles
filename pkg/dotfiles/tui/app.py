"""App shell: loads state, mounts the dashboard, runs first-time key setup."""
from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding

from ..core import agekey
from ..core.paths import repo_root
from .screens.age_key import AgeKeyScreen
from .screens.dashboard import DashboardScreen
from .state import AppState


def _repo() -> Path:
    try:
        return repo_root()
    except RuntimeError:
        return Path.cwd()


class DotfilesApp(App):
    TITLE = "dotfiles"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, repo: Path | None = None) -> None:
        super().__init__()
        self.state = AppState(repo=repo or _repo())
        self.state.reload()

    def on_mount(self) -> None:
        dashboard = DashboardScreen(self.state)
        self.push_screen(dashboard)
        if not agekey.has_key():

            def _after_setup(_result: bool | None) -> None:
                dashboard.refresh_all()

            self.push_screen(AgeKeyScreen(self.state.repo), _after_setup)


def main() -> None:
    DotfilesApp().run()


if __name__ == "__main__":
    main()
