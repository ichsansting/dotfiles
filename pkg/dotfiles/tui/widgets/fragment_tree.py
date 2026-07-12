"""Panel 3: fragments, grouped by composed target file.

Node data: ("target", target) for a target root, or ("fragment", target,
rel_path, owner, secret) for a fragment leaf.
"""
from __future__ import annotations

from textual.binding import Binding
from textual.message import Message

from .base_tree import PanelTree


class FragmentTree(PanelTree):
    BINDINGS = PanelTree.BINDINGS + [
        Binding("n", "new_fragment", "New"),
        Binding("e", "edit_content", "Edit"),
        Binding("R", "reorder", "Reorder"),
        Binding("d", "delete", "Delete"),
        Binding("x", "toggle_exclude", "Exclude"),
        Binding("enter", "preview", "Preview", show=False),
    ]

    class NewRequested(Message):
        def __init__(self, target_hint: str | None) -> None:
            super().__init__()
            self.target_hint = target_hint

    class EditContentRequested(Message):
        def __init__(self, rel_path: str, secret: bool) -> None:
            super().__init__()
            self.rel_path = rel_path
            self.secret = secret

    class ReorderRequested(Message):
        def __init__(self, rel_path: str) -> None:
            super().__init__()
            self.rel_path = rel_path

    class DeleteRequested(Message):
        def __init__(self, rel_path: str) -> None:
            super().__init__()
            self.rel_path = rel_path

    class ToggleExcludeRequested(Message):
        def __init__(self, rel_path: str) -> None:
            super().__init__()
            self.rel_path = rel_path

    class PreviewRequested(Message):
        def __init__(self, rel_path: str, secret: bool) -> None:
            super().__init__()
            self.rel_path = rel_path
            self.secret = secret

    def __init__(self, **kwargs) -> None:
        super().__init__("fragments", **kwargs)

    def build(self, targets: dict[str, list]) -> None:
        self.clear()
        self._node_map = {}
        for target in sorted(targets):
            node = self.root.add(target, data=("target", target))
            self._node_map[("target", target)] = node
            for frag in targets[target]:
                glyph = "S" if frag.secret else "P"
                style = "magenta" if frag.secret else "cyan"
                data = ("fragment", target, frag.rel_path, frag.owner, frag.secret)
                leaf = node.add_leaf(f"[{style}]{glyph}[/] {frag.rel_path.rsplit('/', 1)[-1]}", data=data)
                self._node_map[data] = leaf
        self.root.expand()
        if targets:
            self.cursor_line = 0

    def action_new_fragment(self) -> None:
        data = self._cursor_data()
        hint = data[1] if data else None
        self.post_message(self.NewRequested(hint))

    def action_edit_content(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "fragment":
            self.post_message(self.EditContentRequested(data[2], data[4]))

    def action_reorder(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "fragment":
            self.post_message(self.ReorderRequested(data[2]))

    def action_delete(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "fragment":
            self.post_message(self.DeleteRequested(data[2]))

    def action_toggle_exclude(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "fragment":
            self.post_message(self.ToggleExcludeRequested(data[2]))

    def action_preview(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "fragment":
            self.post_message(self.PreviewRequested(data[2], data[4]))
