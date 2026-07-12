"""Panel 1: presets, each expandable to its base, bundles (own vs
inherited), settings, and excluded fragments.

Node data:
  ("preset", name)
  ("bundle", preset, bundle, inherited: bool)
  ("setting", preset, key_path)
  ("exclude", preset, fragment_rel_path)
"""
from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ...core import edit, materialize

NodeData = tuple


def _flatten(d: dict, prefix: str = "", skip: frozenset[str] = frozenset()) -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    for k, v in d.items():
        if not prefix and k in skip:
            continue
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.extend(_flatten(v, path, skip))
        else:
            out.append((path, v))
    return out


class PresetTree(Tree[NodeData]):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("l", "expand_node", "Expand", show=False),
        Binding("h", "collapse_node", "Collapse", show=False),
        Binding("n", "new_preset", "New"),
        Binding("d", "delete", "Delete/Remove"),
        Binding("b", "set_base", "Base"),
        Binding("B", "add_bundle", "+Bundle"),
        Binding("s", "edit_setting", "Setting"),
        Binding("space", "toggle_bundle", "Toggle"),
    ]

    class NewRequested(Message):
        pass

    class DeleteRequested(Message):
        def __init__(self, preset: str) -> None:
            super().__init__()
            self.preset = preset

    class SetBaseRequested(Message):
        def __init__(self, preset: str) -> None:
            super().__init__()
            self.preset = preset

    class AddBundleRequested(Message):
        def __init__(self, preset: str) -> None:
            super().__init__()
            self.preset = preset

    class ToggleBundleRequested(Message):
        def __init__(self, preset: str, bundle: str) -> None:
            super().__init__()
            self.preset = preset
            self.bundle = bundle

    class EditSettingRequested(Message):
        def __init__(self, preset: str, key_path: str | None) -> None:
            super().__init__()
            self.preset = preset
            self.key_path = key_path

    class RemoveExcludeRequested(Message):
        def __init__(self, preset: str, fragment_rel_path: str) -> None:
            super().__init__()
            self.preset = preset
            self.fragment_rel_path = fragment_rel_path

    class Selected(Message):
        """Cursor moved onto a preset root — becomes the "current preset"
        the fragments panel's exclude toggle acts on."""

        def __init__(self, preset: str) -> None:
            super().__init__()
            self.preset = preset

    def __init__(self, **kwargs) -> None:
        super().__init__("presets", **kwargs)
        self.show_root = False
        self._node_map: dict[NodeData, TreeNode[NodeData]] = {}

    def build(self, root, presets: list[str]) -> None:
        self.clear()
        self._node_map = {}
        for name in presets:
            raw = edit.preset_raw(root, name)
            label = f"{name}  [dim](base: {raw['base']})[/]" if raw.get("base") else name
            data = ("preset", name)
            node = self.root.add(label, data=data)
            self._node_map[data] = node
            self._populate(root, node, name, raw)
        self.root.expand()
        if presets:
            self.cursor_line = 0

    def _populate(self, root, node: TreeNode[NodeData], name: str, raw: dict) -> None:
        own = list(raw.get("bundles", []))
        base = raw.get("base")
        inherited = materialize.load_preset(root, base).bundles if base else []
        for b in inherited:
            if b not in own:
                data = ("bundle", name, b, True)
                self._node_map[data] = node.add_leaf(f"◦ {b}  [dim](inherited)[/]", data=data)
        for b in own:
            data = ("bundle", name, b, False)
            self._node_map[data] = node.add_leaf(f"■ {b}", data=data)
        for key_path, value in _flatten(raw.get("settings", {}), skip=frozenset({"exclude_fragments"})):
            data = ("setting", name, key_path)
            self._node_map[data] = node.add_leaf(f"⚙ {key_path} = {value!r}", data=data)
        for frag in raw.get("settings", {}).get("exclude_fragments", []):
            data = ("exclude", name, frag)
            self._node_map[data] = node.add_leaf(f"⊘ {frag}", data=data)

    def _cursor_data(self) -> NodeData | None:
        node = self.cursor_node
        return node.data if node is not None else None

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[NodeData]) -> None:
        if event.node.data and event.node.data[0] == "preset":
            self.post_message(self.Selected(event.node.data[1]))

    def action_new_preset(self) -> None:
        self.post_message(self.NewRequested())

    def action_delete(self) -> None:
        data = self._cursor_data()
        if not data:
            return
        if data[0] == "preset":
            self.post_message(self.DeleteRequested(data[1]))
        elif data[0] == "bundle" and not data[3]:
            self.post_message(self.ToggleBundleRequested(data[1], data[2]))
        elif data[0] == "exclude":
            self.post_message(self.RemoveExcludeRequested(data[1], data[2]))

    def action_set_base(self) -> None:
        data = self._cursor_data()
        if data:
            self.post_message(self.SetBaseRequested(data[1]))

    def action_add_bundle(self) -> None:
        data = self._cursor_data()
        if data:
            self.post_message(self.AddBundleRequested(data[1]))

    def action_toggle_bundle(self) -> None:
        data = self._cursor_data()
        if data and data[0] == "bundle":
            self.post_message(self.ToggleBundleRequested(data[1], data[2]))

    def action_edit_setting(self) -> None:
        data = self._cursor_data()
        if not data:
            return
        if data[0] == "setting":
            self.post_message(self.EditSettingRequested(data[1], data[2]))
        else:
            self.post_message(self.EditSettingRequested(data[1], None))

    def action_expand_node(self) -> None:
        if self.cursor_node is not None and self.cursor_node.allow_expand:
            self.cursor_node.expand()

    def action_collapse_node(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        elif node.parent is not None and node.parent is not self.root:
            self.cursor_line = node.parent.line
