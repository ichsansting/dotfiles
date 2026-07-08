"""Shared application state: one load/refresh path for every widget."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..core import files, modules, profile
from ..core.modules import Module
from ..core.profile import MachineState, Resolved


@dataclass
class AppState:
    repo: Path
    modules: list[Module] = field(default_factory=list)
    machine: MachineState = field(default_factory=MachineState)
    preset: dict = field(default_factory=dict)
    resolved: Resolved | None = None
    entries: list[files.FileEntry] = field(default_factory=list)
    orphans: list[files.OrphanEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def reload(self) -> None:
        self.errors = []
        self.modules = modules.discover(self.repo)
        self.machine = profile.load_state()
        try:
            self.preset = profile.load_preset(self.repo, self.machine.preset)
        except FileNotFoundError as e:
            self.errors.append(str(e))
            self.machine.preset = profile.DEFAULT_PRESET
            self.preset = profile.load_preset(self.repo, self.machine.preset)
        self.resolve()
        self.refresh_files()

    def resolve(self) -> None:
        self.resolved = profile.resolve(self.preset, self.machine, self.modules)

    def refresh_files(self) -> None:
        self.entries = []
        for mod in self.modules:
            try:
                self.entries.extend(files.status(mod.path))
            except (FileNotFoundError, RuntimeError) as e:
                self.errors.append(str(e))
        self.orphans = files.orphans(self._desired_paths())

    def _desired_paths(self) -> set[str]:
        """Mirror of what deploy-all keeps at switch time (see activate.py)."""
        assert self.resolved is not None
        enabled: list[tuple[Path, set[str]]] = []
        for mod in self.modules:
            toggle = self.resolved.modules[mod.name]
            if not toggle.enabled:
                continue
            disabled = {c for c, on in toggle.children.items() if not on}
            enabled.append((mod.path, disabled))
        return files.desired_paths(enabled)

    def save(self) -> None:
        profile.save_state(self.machine)
        self.resolve()

    def set_preset(self, name: str, reset_overrides: bool) -> None:
        profile.set_preset(self.machine, name, reset_overrides=reset_overrides)
        self.preset = profile.load_preset(self.repo, name)
        self.save()

    def toggle(self, module: str, child: str | None) -> None:
        assert self.resolved is not None
        toggle = self.resolved.modules[module]
        if child is None:
            profile.set_module_enabled(
                self.machine, self.preset, module, not toggle.enabled
            )
        else:
            profile.set_child_enabled(
                self.machine, self.preset, module, child, not toggle.children[child]
            )
        self.save()

    def clear_override(self, module: str, child: str | None) -> None:
        profile.clear_override(self.machine, module, child)
        self.save()

    def override_count(self) -> int:
        return profile.override_count(self.machine)

    def module_dir(self, name: str) -> Path:
        return self.repo / "modules" / name
