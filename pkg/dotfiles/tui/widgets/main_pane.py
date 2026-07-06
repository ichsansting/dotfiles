"""Pane 0: contextual right side — welcome, preview/diff text, or live log."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import ContentSwitcher, RichLog, Static

WELCOME = """\
[b]dotfiles[/b]

  [b]1[/b]/[b]2[/b]/[b]0[/b]  jump between panels
  [b]space[/b]  toggle module / component
  [b]d[/b]iff · [b]s[/b]ync ↑ · [b]D[/b]eploy ↓ on the selected file
  [b]a[/b]pply runs home-manager switch here
  [b]?[/b]  full key reference
"""


class MainPane(ContentSwitcher):
    BINDINGS = [
        Binding("escape", "show_welcome", "Back", show=False),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
    ]

    can_focus = True

    def __init__(self, **kwargs) -> None:
        super().__init__(initial="pane-welcome", **kwargs)

    def compose(self) -> ComposeResult:
        yield Static(WELCOME, id="pane-welcome")
        with VerticalScroll(id="pane-text"):
            yield Static("", id="pane-text-body")
        yield RichLog(id="pane-log", markup=True, highlight=True, wrap=True)

    def show_welcome(self) -> None:
        self.current = "pane-welcome"
        self.border_title = "0 ─ preview"

    def show_text(self, title: str, text: str) -> None:
        self.query_one("#pane-text-body", Static).update(text)
        self.query_one("#pane-text", VerticalScroll).scroll_home(animate=False)
        self.current = "pane-text"
        self.border_title = f"0 ─ {title}"

    def start_log(self, title: str) -> RichLog:
        log = self.query_one("#pane-log", RichLog)
        log.clear()
        self.current = "pane-log"
        self.border_title = f"0 ─ {title}"
        return log

    def log_line(self, text: str) -> None:
        self.query_one("#pane-log", RichLog).write(text)

    def action_show_welcome(self) -> None:
        self.show_welcome()

    def action_scroll_down(self) -> None:
        self._scroll_target().scroll_down()

    def action_scroll_up(self) -> None:
        self._scroll_target().scroll_up()

    def _scroll_target(self):
        if self.current == "pane-log":
            return self.query_one("#pane-log", RichLog)
        return self.query_one("#pane-text", VerticalScroll)
