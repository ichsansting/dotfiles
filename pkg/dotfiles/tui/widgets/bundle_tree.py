"""Panel 2: bundles, each expandable to its tracked items.

Node data: ("bundle", name) for a bundle root, or ("item", bundle, path,
mode) for a tracked item leaf.
"""
from __future__ import annotations

from textual.binding import Binding
from textual.message import Message

from ...core import edit
from .base_tree import PanelTree


class BundleTree(PanelTree):
    BINDINGS = PanelTree.BINDINGS + [
        Binding("n", "new_bundle", "New"),
        Binding("r", "rename_bundle", "Rename"),
        Binding("d", "delete", "Delete/Remove"),
        Binding("a", "add_item", "Add item"),
        Binding("e", "edit_item", "Edit secret"),
        Binding("enter", "preview", "Preview", show=False),
    ]

    class NewRequested(Message):
        pass

    class RenameRequested(Message):
        def __init__(self, bundle: str) -> None:
            super().__init__()
            self.bundle = bundle

    class DeleteRequested(Message):
        def __init__(self, bundle: str) -> None:
            super().__init__()
            self.bundle = bundle

    class AddItemRequested(Message):
        def __init__(self, bundle: str) -> None:
            super().__init__()
            self.bundle = bundle

    class RemoveItemRequested(Message):
        def __init__(self, bundle: str, path: str) -> None:
            super().__init__()
            self.bundle = bundle
            self.path = path

    class EditItemRequested(Message):
        def __init__(self, bundle: str, path: str) -> None:
            super().__init__()
            self.bundle = bundle
            self.path = path

    class PreviewRequested(Message):
        def __init__(self, bundle: str, path: str, mode: str) -> None:
            super().__init__()
            self.bundle = bundle
            self.path = path
            self.mode = mode

    def __init__(self, **kwargs) -> None:
        super().__init__("bundles", **kwargs)

    def build(self, root, bundles: list[str]) -> None:
        self.clear()
        self._node_map = {}
        for name in bundles:
            node = self.root.add(name, data=("bundle", name))
            self._node_map[("bundle", name)] = node
            for item in edit.bundle_items(root, name):
                glyph = "S" if item["mode"] == edit.MODE_SECRET else "P"
                leaf = node.add_leaf(
                    f"[magenta]{glyph}[/] {item['path']}"
                    if item["mode"] == edit.MODE_SECRET
                    else f"[cyan]{glyph}[/] {item['path']}",
                    data=("item", name, item["path"], item["mode"]),
                )
                self._node_map[("item", name, item["path"], item["mode"])] = leaf
        self.root.expand()
        if bundles:
            self.cursor_line = 0

    def action_new_bundle(self) -> None:
        self.post_message(self.NewRequested())

    def action_rename_bundle(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "bundle":
            self.post_message(self.RenameRequested(data[1]))

    def action_delete(self) -> None:
        data = self._cursor_data()
        if not data:
            return
        if data[0] == "bundle":
            self.post_message(self.DeleteRequested(data[1]))
        elif data[0] == "item":
            self.post_message(self.RemoveItemRequested(data[1], data[2]))

    def action_add_item(self) -> None:
        data = self._cursor_data()
        if data:
            self.post_message(self.AddItemRequested(data[1]))

    def action_edit_item(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "item" and data[3] == edit.MODE_SECRET:
            self.post_message(self.EditItemRequested(data[1], data[2]))

    def action_preview(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "item":
            self.post_message(self.PreviewRequested(data[1], data[2], data[3]))
