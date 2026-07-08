"""The single main screen: modules + files panels, contextual main pane."""
from __future__ import annotations

import os
import subprocess
import threading
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer

from ...core import agekey, files, modules, profile
from ...core import manifest as mf
from ..state import AppState
from ..widgets.file_list import FileList
from ..widgets.main_pane import MainPane
from ..widgets.module_tree import ModuleTree
from ..widgets.status_bar import StatusBar
from .add_file import AddChoice, AddFileModal
from .confirm import ConfirmModal
from .help import HelpScreen
from .move_file import MoveFileModal
from .new_module import NewModuleModal
from .preset import PresetModal


class DashboardScreen(Screen):
    BINDINGS = [
        Binding("1", "focus_panel('modules')", "Modules", show=False),
        Binding("2", "focus_panel('files')", "Files", show=False),
        Binding("0", "focus_panel('main')", "Main", show=False),
        Binding("a", "apply", "Apply"),
        Binding("p", "preset", "Preset"),
        Binding("b", "backup_key", "Backup key", show=False),
        Binding("G", "collect_garbage", "GC", show=False),
        Binding("U", "uninstall", "Uninstall", show=False),
        Binding("r", "refresh", "Refresh"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        with Horizontal(id="body"):
            with Vertical(id="left-column"):
                yield ModuleTree(id="modules-panel")
                yield FileList(id="files-panel")
            yield MainPane(id="main-pane")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(ModuleTree).border_title = "1 ─ modules"
        self.query_one(FileList).border_title = "2 ─ files"
        self.query_one(MainPane).border_title = "0 ─ preview"
        self.query_one(ModuleTree).build(self.state)
        self.query_one(FileList).update_entries(self.state)
        self.query_one(StatusBar).update_state(self.state)
        self.query_one(ModuleTree).focus()
        self._report_state_errors()

    # -- refresh plumbing -------------------------------------------------

    def _report_state_errors(self) -> None:
        for err in self.state.errors:
            self.notify(err, severity="error", timeout=10)

    def refresh_toggles(self) -> None:
        self.query_one(ModuleTree).update_labels(self.state)
        self.query_one(StatusBar).update_state(self.state)

    def refresh_files(self) -> None:
        self.state.refresh_files()
        self.query_one(FileList).update_entries(self.state)
        self._report_state_errors()

    def refresh_all(self) -> None:
        self.state.reload()
        self.query_one(ModuleTree).build(self.state)
        self.query_one(FileList).update_entries(self.state)
        self.query_one(StatusBar).update_state(self.state)
        self._report_state_errors()

    # -- panel focus -------------------------------------------------------

    def action_focus_panel(self, which: str) -> None:
        target = {
            "modules": ModuleTree,
            "files": FileList,
            "main": MainPane,
        }[which]
        self.query_one(target).focus()

    # -- module toggles ----------------------------------------------------

    def on_module_tree_toggle_requested(self, msg: ModuleTree.ToggleRequested) -> None:
        try:
            self.state.toggle(msg.module, msg.child)
        except Exception as e:
            self.notify(f"Failed to save profile: {e}", severity="error")
            return
        self.refresh_toggles()

    def on_module_tree_clear_override_requested(
        self, msg: ModuleTree.ClearOverrideRequested
    ) -> None:
        try:
            self.state.clear_override(msg.module, msg.child)
        except Exception as e:
            self.notify(f"Failed to save profile: {e}", severity="error")
            return
        self.refresh_toggles()

    def on_module_tree_clean_requested(self, msg: ModuleTree.CleanRequested) -> None:
        def _on_force(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                files.clean_module(self.state.module_dir(msg.module), force=True)
            except RuntimeError as e:
                self.notify(str(e), severity="error")
                return
            self.refresh_files()
            self.notify(f"Cleaned {msg.module}'s files from $HOME (local changes discarded)")

        def _on_result(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                files.clean_module(self.state.module_dir(msg.module))
            except RuntimeError as e:
                self.refresh_files()  # unchanged files were still removed
                self.app.push_screen(
                    ConfirmModal(
                        "Force clean",
                        f"{e}.\nRemove these files anyway? Local edits are lost.",
                        confirm_label="Force clean",
                        danger=True,
                    ),
                    _on_force,
                )
                return
            self.refresh_files()
            self.notify(f"Cleaned {msg.module}'s files from $HOME")

        self.app.push_screen(
            ConfirmModal(
                "Clean module",
                f"Remove {msg.module}'s tracked files from $HOME?\n"
                "Repo copies are kept; files with local changes are skipped.",
                confirm_label="Clean",
                danger=True,
            ),
            _on_result,
        )

    def on_module_tree_create_module_requested(
        self, msg: ModuleTree.CreateModuleRequested
    ) -> None:
        def _on_result(result: tuple[str, str, bool] | None) -> None:
            if result is None:
                return
            name, desc, in_preset = result
            try:
                self._create_module(name, desc, in_preset)
            except (OSError, ValueError) as e:
                self.notify(str(e), severity="error")
                return
            self.refresh_all()
            self.notify(f"Created module {name} ({self._enabled_where(in_preset)})")

        self.app.push_screen(
            NewModuleModal(self.state.repo, self.state.machine.preset), _on_result
        )

    def _enabled_where(self, in_preset: bool) -> str:
        if in_preset:
            return f"enabled in preset '{self.state.machine.preset}' — commit it"
        return "enabled on this machine"

    def _create_module(self, name: str, description: str, in_preset: bool) -> None:
        """Scaffold a module and enable it where the user chose.

        Without an enablement the new module (default off) would silently
        never deploy anything. A local override keeps it off on machines
        that follow a preset; writing into the active preset commits the
        enablement for every machine using that preset.
        """
        modules.create(self.state.repo, name, description)
        if in_preset:
            profile.add_module_to_preset(
                self.state.repo, self.state.machine.preset, name
            )
        self.state.reload()
        if not in_preset:
            self.state.toggle(name, None)

    # -- file actions --------------------------------------------------------

    def on_file_list_action(self, msg: FileList.Action) -> None:
        if msg.action == "add":
            self._file_add()
            return
        if msg.orphan is not None:
            self._orphan_action(msg.action, msg.orphan)
            return
        entry = msg.entry
        if entry is None:
            self.notify("No file selected", severity="warning")
            return
        handler = {
            "preview": self._file_preview,
            "diff": self._file_diff,
            "sync": self._file_sync,
            "deploy": self._file_deploy,
            "move": self._file_move,
            "remove": self._file_remove,
            "edit": self._file_edit,
        }[msg.action]
        handler(entry)

    def _file_preview(self, entry: files.FileEntry) -> None:
        try:
            text = files.repo_bytes(entry.spec, entry.storage).decode(
                "utf-8", errors="replace"
            )
        except (OSError, RuntimeError) as e:
            self.notify(str(e), severity="error")
            return
        mode = "secret" if entry.is_secret else "plain"
        self.query_one(MainPane).show_text(f"{entry.spec.path} ({mode})", text)

    def _file_diff(self, entry: files.FileEntry) -> None:
        try:
            text = files.diff(entry)
        except (OSError, RuntimeError) as e:
            self.notify(str(e), severity="error")
            return
        self.query_one(MainPane).show_text(f"diff {entry.spec.path}", text)

    def _file_sync(self, entry: files.FileEntry) -> None:
        try:
            files.sync(entry)
        except (OSError, RuntimeError, ValueError) as e:
            self.notify(str(e), severity="error")
            return
        self.refresh_files()
        self.notify(f"Synced {entry.spec.path} into the repo")

    def _file_deploy(self, entry: files.FileEntry) -> None:
        if entry.state == files.CHANGED:
            def _on_result(confirmed: bool | None) -> None:
                if not confirmed:
                    return
                try:
                    files.deploy_one(entry, overwrite=True)
                except (OSError, RuntimeError) as e:
                    self.notify(str(e), severity="error")
                    return
                self.refresh_files()
                self.notify(f"Deployed {entry.spec.path} (local changes replaced)")

            self.app.push_screen(
                ConfirmModal(
                    "Overwrite local changes",
                    f"{entry.spec.path} was edited in $HOME.\n"
                    "Replace your edits with the repo copy?",
                    confirm_label="Overwrite",
                    danger=True,
                ),
                _on_result,
            )
            return
        try:
            files.deploy_one(entry)
        except (OSError, RuntimeError) as e:
            self.notify(str(e), severity="error")
            return
        self.refresh_files()
        self.notify(f"Deployed {entry.spec.path}")

    def _orphan_action(self, action: str, orphan: files.OrphanEntry) -> None:
        if action == "preview":
            try:
                text = orphan.home_path.read_text(errors="replace")
            except OSError as e:
                self.notify(str(e), severity="error")
                return
            self.query_one(MainPane).show_text(f"{orphan.path} (orphan)", text)
            return
        if action == "remove":
            detail = (
                "was edited locally after deployment"
                if orphan.edited
                else "is unchanged (the next apply removes it anyway)"
            )

            def _on_result(confirmed: bool | None) -> None:
                if not confirmed:
                    return
                files.remove_orphan(orphan.path)
                self.refresh_files()
                self.notify(f"Deleted {orphan.path} from $HOME")

            self.app.push_screen(
                ConfirmModal(
                    "Delete orphaned file",
                    f"{orphan.path} is no longer tracked by any enabled module\n"
                    f"and {detail}. Delete it from $HOME?",
                    confirm_label="Delete",
                    danger=True,
                ),
                _on_result,
            )
            return
        self.notify(
            "Orphaned file — track it into a module (n) or delete it (x)",
            severity="warning",
        )

    def _file_add(self) -> None:
        module_names = [m.name for m in self.state.modules]

        def _on_result(result: AddChoice | None) -> None:
            if not result:
                return
            created = result.new_module_description is not None
            try:
                if created:
                    self._create_module(
                        result.module,
                        result.new_module_description,
                        result.new_module_in_preset,
                    )
                files.add(
                    self.state.module_dir(result.module),
                    Path.home() / result.rel,
                    result.mode,
                )
            except (OSError, RuntimeError, ValueError) as e:
                self.notify(str(e), severity="error")
                if created:
                    self.refresh_all()  # the module may exist even if add failed
                return
            if created:
                self.refresh_all()
                self.notify(
                    f"Created module {result.module} "
                    f"({self._enabled_where(result.new_module_in_preset)}); "
                    f"tracking {result.rel} ({result.mode})"
                )
            else:
                self.refresh_files()
                self.notify(f"Tracking {result.rel} in {result.module} ({result.mode})")

        self.app.push_screen(
            AddFileModal(module_names, self.state.repo, self.state.machine.preset),
            _on_result,
        )

    def _file_move(self, entry: files.FileEntry) -> None:
        others = [m.name for m in self.state.modules if m.name != entry.module]
        if not others:
            self.notify("No other module to move to (create one with N)", severity="warning")
            return

        def _on_result(dst: str | None) -> None:
            if dst is None:
                return
            try:
                files.move(
                    self.state.module_dir(entry.module),
                    entry,
                    self.state.module_dir(dst),
                )
            except (OSError, ValueError) as e:
                self.notify(str(e), severity="error")
                return
            self.refresh_files()
            self.notify(f"Moved {entry.spec.path}: {entry.module} → {dst}")

        self.app.push_screen(
            MoveFileModal(entry.spec.path, entry.module, others), _on_result
        )

    def _file_remove(self, entry: files.FileEntry) -> None:
        def _on_result(confirmed: bool | None) -> None:
            if not confirmed:
                return
            files.remove(self.state.module_dir(entry.module), entry)
            self.refresh_files()
            self.notify(
                f"Untracked {entry.spec.path} "
                "($HOME copy is removed on next apply unless you edited it)"
            )

        self.app.push_screen(
            ConfirmModal(
                "Untrack file",
                f"Remove {entry.spec.path} from {entry.module}?\n"
                "The $HOME copy is pruned on the next apply (kept if edited).",
                confirm_label="Untrack",
                danger=True,
            ),
            _on_result,
        )

    def _file_edit(self, entry: files.FileEntry) -> None:
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if not editor:
            self.notify("$EDITOR is not set (enable the env module)", severity="warning")
            return
        try:
            with self.app.suspend():
                subprocess.run([editor, str(entry.home_path)], check=False)
        except FileNotFoundError:
            self.notify(f"Editor not found: {editor}", severity="error")
            return
        self.refresh_files()

    # -- global actions ------------------------------------------------------

    def action_help(self) -> None:
        self.app.push_screen(HelpScreen())

    def action_refresh(self) -> None:
        self.refresh_all()
        self.notify("Refreshed")

    def action_preset(self) -> None:
        presets = profile.list_presets(self.state.repo)
        if not presets:
            self.notify("No presets found in presets/", severity="warning")
            return

        def _on_result(result: tuple[str, bool] | None) -> None:
            if result is None:
                return
            name, reset = result
            self.state.set_preset(name, reset_overrides=reset)
            self.refresh_toggles()
            self.notify(f"Preset switched to {name}" + (" (overrides reset)" if reset else ""))

        self.app.push_screen(
            PresetModal(presets, self.state.machine.preset, self.state.override_count()),
            _on_result,
        )

    def action_backup_key(self) -> None:
        if not agekey.has_key():
            self.notify("No age key to back up", severity="warning")
            return
        identity = self.state.repo / "identity.age"
        try:
            with self.app.suspend():
                agekey.backup(identity)
        except RuntimeError as e:
            self.notify(str(e), severity="error")
            return
        self.notify(f"Age key backed up to {identity} — commit it.")

    # -- long-running workers (threads streaming into the main pane) ---------

    def _log(self, text: str) -> None:
        self.query_one(MainPane).log_line(text)

    def _stream(self, cmd: list[str]) -> int:
        """Run cmd, streaming combined output into the log. Returns exit code."""
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout
        for line in proc.stdout:
            self.app.call_from_thread(self._log, line.rstrip())
        return proc.wait()

    def action_apply(self) -> None:
        self.query_one(MainPane).start_log("home-manager switch")
        self.query_one(MainPane).focus()
        self._log("[bold]Running home-manager switch…[/bold]")

        def _worker() -> None:
            cmd = [
                "home-manager",
                "switch",
                "--flake",
                f"{self.state.repo}#default",
                "--impure",
                "--extra-experimental-features",
                "nix-command flakes",
            ]
            try:
                code = self._stream(cmd)
            except FileNotFoundError:
                self.app.call_from_thread(self._log, "[red]home-manager not found in PATH[/red]")
                return
            if code == 0:
                self.app.call_from_thread(self._log, "[green]✓ Applied successfully[/green]")
            else:
                self.app.call_from_thread(
                    self._log, f"[red]✗ Failed with exit code {code}[/red]"
                )
            self.app.call_from_thread(self.refresh_files)

        threading.Thread(target=_worker, daemon=True).start()

    def action_collect_garbage(self) -> None:
        def _on_result(confirmed: bool | None) -> None:
            if not confirmed:
                return
            self.query_one(MainPane).start_log("garbage collection")
            self._log("[bold]Collecting garbage…[/bold]")

            def _worker() -> None:
                for cmd in (
                    ["home-manager", "expire-generations", "-30 days"],
                    ["nix-collect-garbage", "-d"],
                ):
                    try:
                        self._stream(cmd)
                    except FileNotFoundError:
                        self.app.call_from_thread(
                            self._log, f"skipped (not found): {' '.join(cmd)}"
                        )
                self.app.call_from_thread(self._log, "[green]✓ Done[/green]")

            threading.Thread(target=_worker, daemon=True).start()

        self.app.push_screen(
            ConfirmModal(
                "Garbage collection",
                "Expire home-manager generations older than 30 days and run\n"
                "nix-collect-garbage -d?",
                confirm_label="Collect",
            ),
            _on_result,
        )

    def action_uninstall(self) -> None:
        def _on_result(confirmed: bool | None) -> None:
            if not confirmed:
                return
            self.query_one(MainPane).start_log("uninstall")
            self._log("[bold red]Uninstalling…[/bold red]")
            threading.Thread(target=self._uninstall_worker, daemon=True).start()

        self.app.push_screen(
            ConfirmModal(
                "Uninstall everything",
                "This removes mise tools, all home-manager generations, the nix\n"
                "store, decrypted secrets, and the age key from this machine.",
                confirm_label="Uninstall",
                danger=True,
            ),
            _on_result,
        )

    def _uninstall_worker(self) -> None:
        log = lambda text: self.app.call_from_thread(self._log, text)  # noqa: E731

        # 1. mise tools
        for cmd in (["mise", "uninstall", "--all"],):
            try:
                self._stream(cmd)
            except FileNotFoundError:
                log(f"skipped (not found): {' '.join(cmd)}")

        # 2. expire generations + GC
        for cmd in (
            ["home-manager", "expire-generations", "-0 days"],
            ["nix-collect-garbage", "-d"],
        ):
            try:
                self._stream(cmd)
            except FileNotFoundError:
                log(f"skipped (not found): {' '.join(cmd)}")

        # 3. remove decrypted secrets (from manifests) + derived key files
        home = Path.home()
        for mod in self.state.modules:
            for spec in mf.load(mod.path):
                if spec.mode != mf.MODE_SECRET:
                    continue
                dest = home / spec.path
                if dest.exists():
                    dest.unlink()
                    log(f"removed: {dest}")
        for p in (
            home / ".ssh" / "id_ed25519.pub",
            home / ".ssh" / "allowed_signers",
            agekey.key_path(),
        ):
            if p.exists():
                p.unlink()
                log(f"removed: {p}")

        # 4. uninstall Nix itself
        nix_installer = Path("/nix/nix-installer")
        if nix_installer.exists():
            try:
                self._stream([str(nix_installer), "uninstall"])
            except (OSError, RuntimeError) as e:
                log(f"[red]{e}[/red]")
        else:
            log("[yellow]Nix installer not found — uninstall Nix manually.[/yellow]")

        log("[green]✓ Uninstall complete.[/green]")
