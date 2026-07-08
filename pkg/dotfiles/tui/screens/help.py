"""Full key reference overlay."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label, Static

KEYS = """\
[b]Panels[/b]
  1 / 2 / 0        focus modules / files / main pane
  tab, shift+tab   cycle focus

[b]Modules panel[/b]
  j/k or ↑/↓       move · h/l fold
  space            toggle module or component (saved immediately)
  x                clear local override (back to preset value)
  c                clean — remove module's tracked files from $HOME
                   (edited files are kept unless you confirm a force clean)
  N                create a new module (enabled on this machine)

[b]Files panel[/b]
  enter            preview file in main pane
  d                diff repo vs $HOME
  s                sync ↑ ($HOME → repo, re-encrypts secrets)
  D                deploy ↓ (repo → $HOME, asks before overwriting edits)
  n                track a new file (plain or secret)
  m                move file to another module (repo-side, no re-encrypt)
  x                untrack ($HOME copy pruned on next apply) · delete orphan
  e                open $HOME copy in $EDITOR

  Orphan rows (mode O) are deployed files no module tracks anymore:
  † unchanged — removed on next apply · ! edited — track (n) or delete (x)

[b]Global[/b]
  a                apply — home-manager switch (live log in main pane)
  p                switch preset (work / personal / …)
  b                backup age key to identity.age
  G                garbage-collect nix store + old generations
  U                uninstall everything (confirmed)
  r                refresh · ? this help · q quit
"""


class HelpScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape,q,question_mark", "dismiss_help", "Close")]

    def compose(self) -> ComposeResult:
        with Container(id="help-container"):
            yield Label("Key reference", id="help-title")
            yield Static(KEYS, id="help-body")

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
