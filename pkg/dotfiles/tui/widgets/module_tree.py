"""Panel 1: module tree with checkbox glyphs.

Node data is (module, child|None). Glyphs:
  ■ on   □ off   ◪ module on but some children off   * overridden vs preset
"""
from __future__ import annotations

from textual.binding import Binding
from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from ...core import profile
from ..state import AppState

NodeData = tuple[str, str | None]


class ModuleTree(Tree[NodeData]):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("space", "toggle_enable", "Toggle"),
        Binding("x", "clear_override", "Clear override"),
        Binding("c", "clean_module", "Clean files"),
        Binding("N", "new_module", "New module"),
        Binding("l", "expand_node", "Expand", show=False),
        Binding("h", "collapse_node", "Collapse", show=False),
    ]

    class ToggleRequested(Message):
        def __init__(self, module: str, child: str | None) -> None:
            super().__init__()
            self.module = module
            self.child = child

    class ClearOverrideRequested(Message):
        def __init__(self, module: str, child: str | None) -> None:
            super().__init__()
            self.module = module
            self.child = child

    class CreateModuleRequested(Message):
        pass

    class CleanRequested(Message):
        def __init__(self, module: str) -> None:
            super().__init__()
            self.module = module

    def __init__(self, **kwargs) -> None:
        super().__init__("modules", **kwargs)
        self.show_root = False
        self.guide_depth = 3
        self._node_map: dict[NodeData, TreeNode[NodeData]] = {}

    def build(self, state: AppState) -> None:
        """(Re)build the tree; called once on mount and when modules change."""
        self.clear()
        self._node_map = {}
        for mod in state.modules:
            if mod.children:
                node = self.root.add(mod.name, data=(mod.name, None))
            else:
                node = self.root.add_leaf(mod.name, data=(mod.name, None))
            self._node_map[(mod.name, None)] = node
            for child in mod.children:
                leaf = node.add_leaf(child, data=(mod.name, child))
                self._node_map[(mod.name, child)] = leaf
        self.root.expand()
        if state.modules:
            self.cursor_line = 0
        self.update_labels(state)

    def update_labels(self, state: AppState) -> None:
        assert state.resolved is not None
        for (module, child), node in self._node_map.items():
            toggle = state.resolved.modules[module]
            if child is None:
                if not toggle.enabled:
                    glyph = "□"
                elif all(toggle.children.values()):
                    glyph = "■"
                else:
                    glyph = "◪"
                name = module
                overridden = profile.is_module_overridden(state.machine, module)
            else:
                glyph = "■" if toggle.enabled and toggle.children[child] else "□"
                name = child
                overridden = profile.is_child_overridden(state.machine, module, child)
            mark = " [b yellow]*[/]" if overridden else ""
            label = f"{glyph} {name}" if toggle.enabled else f"[dim]{glyph} {name}[/]"
            node.set_label(f"{label}{mark}")
        self.refresh()

    def _cursor_data(self) -> NodeData | None:
        node = self.cursor_node
        return node.data if node is not None else None

    def action_toggle_enable(self) -> None:
        data = self._cursor_data()
        if data:
            self.post_message(self.ToggleRequested(*data))

    def action_clear_override(self) -> None:
        data = self._cursor_data()
        if data:
            self.post_message(self.ClearOverrideRequested(*data))

    def action_new_module(self) -> None:
        self.post_message(self.CreateModuleRequested())

    def action_clean_module(self) -> None:
        data = self._cursor_data()
        if data:
            self.post_message(self.CleanRequested(data[0]))

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
