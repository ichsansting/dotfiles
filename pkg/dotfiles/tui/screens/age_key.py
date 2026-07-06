"""First-run age key setup: generate new or restore from identity.age."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog

from ...core import agekey


class AgeKeyScreen(ModalScreen[bool]):
    BINDINGS = [Binding("escape", "skip", "Skip")]

    def __init__(self, repo: Path) -> None:
        super().__init__()
        self._repo = repo
        self._identity = repo / "identity.age"

    def compose(self) -> ComposeResult:
        with Container(id="age-container"):
            yield Label("Age Key Setup Required", id="age-title")
            yield Label(
                "No age key found at ~/.config/sops/age/keys.txt.\n"
                "Secrets cannot be decrypted or encrypted without it.",
                id="age-desc",
            )
            if self._identity.exists():
                yield Button(
                    "Restore from identity.age (enter passphrase)",
                    id="restore-btn",
                    variant="primary",
                )
            yield Button("Generate new age key", id="generate-btn")
            yield Button("Skip for now", id="skip-btn")
            yield RichLog(id="age-log", markup=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        log = self.query_one("#age-log", RichLog)
        if event.button.id == "skip-btn":
            self.dismiss(False)
        elif event.button.id == "restore-btn":
            try:
                with self.app.suspend():
                    agekey.restore(self._identity)
                self.dismiss(True)
            except RuntimeError as e:
                log.write(f"[red]{e}[/red]")
        elif event.button.id == "generate-btn":
            try:
                pub = agekey.generate()
                agekey.patch_sops_yaml(self._repo / ".sops.yaml", pub)
                log.write("[green]✓ Generated new age key.[/green]")
                log.write(f"Public key: [bold]{pub}[/bold]")
                log.write(
                    "[yellow]Back up your key ([b]b[/b] on the dashboard), then "
                    "commit .sops.yaml and identity.age.[/yellow]"
                )
            except RuntimeError as e:
                log.write(f"[red]{e}[/red]")

    def action_skip(self) -> None:
        self.dismiss(False)
