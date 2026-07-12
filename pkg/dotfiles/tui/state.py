"""Shared application state: one reload path for every panel, plus which
preset is currently selected (panel 1's cursor) — the fragment panel's
exclude-toggle action needs to know which preset's `exclude_fragments` it's
editing."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..core import edit


@dataclass
class AppState:
    repo: Path
    bundles: list[str] = field(default_factory=list)
    presets: list[str] = field(default_factory=list)
    fragment_targets: dict[str, list[edit.FragmentInfo]] = field(default_factory=dict)
    selected_preset: str | None = None

    def reload(self) -> None:
        self.bundles = edit.list_bundles(self.repo)
        self.presets = edit.list_presets(self.repo)
        self.fragment_targets = edit.fragment_targets(self.repo)
        if self.selected_preset not in self.presets:
            self.selected_preset = self.presets[0] if self.presets else None
