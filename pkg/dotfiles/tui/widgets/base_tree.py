"""Shared shape behind the three panel trees (PresetTree, BundleTree,
FragmentTree): a node-data map for deterministic lookup (used by every
tree's own build() and by tests to expand/navigate without simulating
keypresses), plus the cursor-data helper and h/l expand-collapse actions
every panel binds identically."""
from __future__ import annotations

from textual.binding import Binding
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

NodeData = tuple


class PanelTree(Tree[NodeData]):
    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("l", "expand_node", "Expand", show=False),
        Binding("h", "collapse_node", "Collapse", show=False),
    ]

    def __init__(self, root_label: str, **kwargs) -> None:
        super().__init__(root_label, **kwargs)
        self.show_root = False
        self._node_map: dict[NodeData, TreeNode[NodeData]] = {}

    def _cursor_data(self) -> NodeData | None:
        node = self.cursor_node
        return node.data if node is not None else None

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
