"""Pane 0: contextual right side — welcome or a read-only content preview."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import ContentSwitcher, Static

WELCOME = """\
[b]dotfiles edit[/b]

  [b]1[/b]/[b]2[/b]/[b]3[/b]/[b]0[/b]  jump between panels
  presets: [b]n[/b]ew · [b]d[/b]elete · [b]b[/b]ase · [b]B[/b] add bundle · \
[b]s[/b]etting · [b]space[/b] toggle bundle
  bundles: [b]n[/b]ew · [b]r[/b]ename · [b]d[/b]elete/remove · [b]a[/b]dd item
  fragments: [b]n[/b]ew · [b]e[/b]dit · [b]R[/b]eorder · [b]d[/b]elete · \
e[b]x[/b]clude (for panel 1's preset)
  [b]enter[/b] previews the selected item here
  Every edit auto-commits and pushes immediately.
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

    def show_welcome(self) -> None:
        self.current = "pane-welcome"
        self.border_title = "0 — preview"

    def show_text(self, title: str, text: str) -> None:
        self.query_one("#pane-text-body", Static).update(text)
        self.query_one("#pane-text", VerticalScroll).scroll_home(animate=False)
        self.current = "pane-text"
        self.border_title = f"0 — {title}"

    def action_show_welcome(self) -> None:
        self.show_welcome()

    def action_scroll_down(self) -> None:
        self.query_one("#pane-text", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#pane-text", VerticalScroll).scroll_up()
