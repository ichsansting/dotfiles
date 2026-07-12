"""The single main screen: preset/bundle/fragment panels + contextual main
pane. Every mutating message handler below funnels through `_commit`, the
one place `gitops.commit_and_push` is called — the guarantee that every
edit auto-commits and auto-pushes immediately lives here, not scattered
across each action. See
.scratch/ephemeral-shell/issues/17-editing-tui-crud.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer

from ...core import edit, gitops, materialize, secrets
from ..state import AppState
from ..widgets.bundle_tree import BundleTree
from ..widgets.fragment_tree import FragmentTree
from ..widgets.main_pane import MainPane
from ..widgets.preset_tree import PresetTree
from ..widgets.status_bar import StatusBar
from .confirm import ConfirmModal
from .form import FormModal
from .picker import PickerModal

_SECRET_PREVIEW = "[dim](secret — encrypted content is not previewed here)[/]"


class DashboardScreen(Screen):
    BINDINGS = [
        Binding("1", "focus_panel('presets')", "Presets", show=False),
        Binding("2", "focus_panel('bundles')", "Bundles", show=False),
        Binding("3", "focus_panel('fragments')", "Fragments", show=False),
        Binding("0", "focus_panel('main')", "Main", show=False),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        yield StatusBar(id="status-bar")
        with Horizontal(id="body"):
            with Vertical(id="left-column"):
                yield PresetTree(id="presets-panel")
                yield BundleTree(id="bundles-panel")
                yield FragmentTree(id="fragments-panel")
            yield MainPane(id="main-pane")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(PresetTree).border_title = "1 — presets"
        self.query_one(BundleTree).border_title = "2 — bundles"
        self.query_one(FragmentTree).border_title = "3 — fragments"
        self.query_one(MainPane).border_title = "0 — preview"
        self._refresh()
        self.query_one(PresetTree).focus()

    # -- shared plumbing -----------------------------------------------------

    def _refresh(self) -> None:
        self.state.reload()
        self.query_one(PresetTree).build(self.state.repo, self.state.presets)
        self.query_one(BundleTree).build(self.state.repo, self.state.bundles)
        self.query_one(FragmentTree).build(self.state.fragment_targets)
        self.query_one(StatusBar).update_state(self.state)

    def _commit(self, result: edit.EditResult) -> bool:
        try:
            gitops.commit_and_push(self.state.repo, result.message, result.paths)
        except gitops.GitError as e:
            self.notify(str(e), severity="error")
            return False
        return True

    def _open_editor(self, path: Path) -> bool:
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if not editor:
            self.notify("$EDITOR is not set", severity="warning")
            return False
        try:
            with self.app.suspend():
                subprocess.run([editor, str(path)], check=False)
        except FileNotFoundError:
            self.notify(f"Editor not found: {editor}", severity="error")
            return False
        return True

    def _edit_and_encrypt(self, out_path: Path) -> bool:
        """New-secret-item flow: $EDITOR on a private tmp plaintext file,
        sops-encrypt into out_path, shred the tmp file. Only needs the
        repo's public age recipient — unlike editing an *existing* secret's
        content, which needs the private key (ticket 18)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_file = Path(tmp) / out_path.name
            tmp_file.touch()
            if not self._open_editor(tmp_file):
                return False
            try:
                encrypted = secrets.encrypt_secret(self.state.repo, tmp_file.read_bytes())
            except (OSError, RuntimeError) as e:
                self.notify(str(e), severity="error")
                return False
            finally:
                secrets.shred_file(tmp_file)
        out_path.write_bytes(encrypted)
        return True

    def _decrypt_edit_reencrypt(self, path: Path) -> bool:
        """Existing-secret edit flow (ticket 18): age-decrypts the repo's
        identity (interactive passphrase prompt, needs a real terminal —
        same as $EDITOR) into a scratch dir, sops-decrypts `path` with it,
        opens $EDITOR on the plaintext, then sops-encrypts the result back
        over `path`. Unlike `_edit_and_encrypt` (new secret items, public
        recipient only), this needs the private key/passphrase, so the age
        decrypt and $EDITOR both run under one `app.suspend()`.

        The scratch age key and tmp plaintext are shredded either way,
        saved edit or cancelled."""
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if not editor:
            self.notify("$EDITOR is not set", severity="warning")
            return False
        identity_file = self.state.repo / "identity.age"
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp)
            tmp_file = scratch / path.name
            key_path: Path | None = None
            try:
                with self.app.suspend():
                    key_path = secrets.decrypt_identity(identity_file, scratch)
                    tmp_file.write_bytes(secrets.decrypt_secret_file(path, key_path))
                    subprocess.run([editor, str(tmp_file)], check=False)
                encrypted = secrets.encrypt_secret(self.state.repo, tmp_file.read_bytes())
            except (OSError, RuntimeError) as e:
                self.notify(str(e), severity="error")
                return False
            finally:
                secrets.shred_file(tmp_file)
                if key_path is not None:
                    secrets.shred_file(key_path)
        path.write_bytes(encrypted)
        return True

    def action_focus_panel(self, which: str) -> None:
        target = {
            "presets": PresetTree,
            "bundles": BundleTree,
            "fragments": FragmentTree,
            "main": MainPane,
        }[which]
        self.query_one(target).focus()

    def action_refresh(self) -> None:
        self._refresh()
        self.notify("Refreshed")

    # -- presets ---------------------------------------------------------------

    def on_preset_tree_selected(self, msg: PresetTree.Selected) -> None:
        self.state.selected_preset = msg.preset
        self.query_one(StatusBar).update_state(self.state)

    def on_preset_tree_new_requested(self, msg: PresetTree.NewRequested) -> None:
        def _on_result(values: dict | None) -> None:
            if values is None:
                return
            name, base = values["name"], values["base"] or None
            if not name:
                self.notify("Name is required", severity="warning")
                return
            try:
                result = edit.create_preset(self.state.repo, name, base)
            except (ValueError, FileExistsError, FileNotFoundError) as e:
                self.notify(str(e), severity="error")
                return
            if self._commit(result):
                self._refresh()
                self.notify(f"Created preset {name}")

        self.app.push_screen(
            FormModal("New preset", [("name", "Name", ""), ("base", "Base preset (optional)", "")]),
            _on_result,
        )

    def on_preset_tree_delete_requested(self, msg: PresetTree.DeleteRequested) -> None:
        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                result = edit.delete_preset(self.state.repo, msg.preset)
            except (FileNotFoundError, ValueError) as e:
                self.notify(str(e), severity="error")
                return
            if self._commit(result):
                self._refresh()
                self.notify(f"Deleted preset {msg.preset}")

        self.app.push_screen(
            ConfirmModal(
                "Delete preset", f"Delete preset '{msg.preset}'?", confirm_label="Delete", danger=True
            ),
            _on_confirm,
        )

    def on_preset_tree_set_base_requested(self, msg: PresetTree.SetBaseRequested) -> None:
        options = ["(none)"] + edit.valid_bases(self.state.repo, msg.preset)

        def _on_result(choice: str | None) -> None:
            if choice is None:
                return
            base = None if choice == "(none)" else choice
            try:
                result = edit.set_preset_base(self.state.repo, msg.preset, base)
            except (ValueError, FileNotFoundError) as e:
                self.notify(str(e), severity="error")
                return
            if self._commit(result):
                self._refresh()
                self.notify(f"{msg.preset} base -> {base or '(none)'}")

        self.app.push_screen(PickerModal(f"Set base for {msg.preset}", options), _on_result)

    def on_preset_tree_add_bundle_requested(self, msg: PresetTree.AddBundleRequested) -> None:
        raw = edit.preset_raw(self.state.repo, msg.preset)
        own = set(raw.get("bundles", []))
        base = raw.get("base")
        inherited = set(materialize.load_preset(self.state.repo, base).bundles) if base else set()
        available = [b for b in self.state.bundles if b not in own and b not in inherited]
        if not available:
            self.notify("No more bundles to add", severity="warning")
            return

        def _on_result(choice: str | None) -> None:
            if choice is None:
                return
            result = edit.toggle_bundle_in_preset(self.state.repo, msg.preset, choice)
            if self._commit(result):
                self._refresh()
                self.notify(f"Added {choice} to {msg.preset}")

        self.app.push_screen(PickerModal(f"Add bundle to {msg.preset}", available), _on_result)

    def on_preset_tree_toggle_bundle_requested(self, msg: PresetTree.ToggleBundleRequested) -> None:
        if msg.inherited:
            # There's no exclude-inherited-bundle mechanism (only exclude_fragments
            # exists) — toggling would just add a redundant explicit own entry.
            self.notify(
                f"{msg.bundle} is inherited from the base preset — change the base "
                "(b) to drop it",
                severity="warning",
            )
            return
        result = edit.toggle_bundle_in_preset(self.state.repo, msg.preset, msg.bundle)
        if self._commit(result):
            self._refresh()
            self.notify(result.message)

    def on_preset_tree_edit_setting_requested(self, msg: PresetTree.EditSettingRequested) -> None:
        default_value = ""
        if msg.key_path:
            node = edit.preset_raw(self.state.repo, msg.preset).get("settings", {})
            for part in msg.key_path.split("."):
                node = node.get(part, {}) if isinstance(node, dict) else {}
            default_value = "" if isinstance(node, dict) else str(node)

        def _on_result(values: dict | None) -> None:
            if values is None:
                return
            key, value = values["key"], values["value"]
            if not key:
                self.notify("Key is required", severity="warning")
                return
            try:
                result = edit.set_setting(self.state.repo, msg.preset, key, value)
            except ValueError as e:
                self.notify(str(e), severity="error")
                return
            if self._commit(result):
                self._refresh()
                self.notify(f"Set {msg.preset}.settings.{key}")

        self.app.push_screen(
            FormModal(
                f"Setting for {msg.preset}",
                [("key", "Key (dot path)", msg.key_path or ""), ("value", "Value", default_value)],
            ),
            _on_result,
        )

    def on_preset_tree_remove_exclude_requested(self, msg: PresetTree.RemoveExcludeRequested) -> None:
        result = edit.toggle_exclude_fragment(self.state.repo, msg.preset, msg.fragment_rel_path)
        if self._commit(result):
            self._refresh()
            self.notify(result.message)

    def on_preset_tree_preview_requested(self, msg: PresetTree.PreviewRequested) -> None:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result = edit.preview(self.state.repo, msg.preset, Path(tmp))
        except (materialize.ConfigError, OSError) as e:
            self.notify(str(e), severity="error")
            return
        lines = [f"packages ({len(result.packages)}): {', '.join(result.packages) or '(none)'}", ""]
        lines += ["settings:", json.dumps(result.settings, indent=2), ""]
        for entry in sorted(result.files, key=lambda e: e.path):
            lines.append(f"[cyan]== {entry.path} ==[/]")
            lines.append(entry.content.decode(errors="replace"))
        if result.secret_paths:
            lines.append(_SECRET_PREVIEW)
            lines.extend(f"  {p}" for p in result.secret_paths)
        self.query_one(MainPane).show_text(f"preview: {msg.preset}", "\n".join(lines))

    # -- bundles -----------------------------------------------------------------

    def on_bundle_tree_new_requested(self, msg: BundleTree.NewRequested) -> None:
        def _on_result(values: dict | None) -> None:
            if values is None:
                return
            name = values["name"]
            try:
                result = edit.create_bundle(self.state.repo, name)
            except (ValueError, FileExistsError) as e:
                self.notify(str(e), severity="error")
                return
            if self._commit(result):
                self._refresh()
                self.notify(f"Created bundle {name}")

        self.app.push_screen(FormModal("New bundle", [("name", "Name", "")]), _on_result)

    def on_bundle_tree_rename_requested(self, msg: BundleTree.RenameRequested) -> None:
        def _on_result(values: dict | None) -> None:
            if values is None:
                return
            new = values["name"]
            try:
                result = edit.rename_bundle(self.state.repo, msg.bundle, new)
            except (ValueError, FileExistsError, FileNotFoundError) as e:
                self.notify(str(e), severity="error")
                return
            if self._commit(result):
                self._refresh()
                self.notify(f"Renamed {msg.bundle} -> {new}")

        self.app.push_screen(
            FormModal(f"Rename {msg.bundle}", [("name", "New name", msg.bundle)]), _on_result
        )

    def on_bundle_tree_delete_requested(self, msg: BundleTree.DeleteRequested) -> None:
        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            result = edit.delete_bundle(self.state.repo, msg.bundle)
            if self._commit(result):
                self._refresh()
                self.notify(f"Deleted bundle {msg.bundle}")

        self.app.push_screen(
            ConfirmModal(
                "Delete bundle",
                f"Delete bundle '{msg.bundle}' and all its items?",
                confirm_label="Delete",
                danger=True,
            ),
            _on_confirm,
        )

    def on_bundle_tree_remove_item_requested(self, msg: BundleTree.RemoveItemRequested) -> None:
        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            result = edit.remove_bundle_item(self.state.repo, msg.bundle, msg.path)
            if self._commit(result):
                self._refresh()
                self.notify(f"Removed {msg.path} from {msg.bundle}")

        self.app.push_screen(
            ConfirmModal(
                "Remove item", f"Remove {msg.path} from {msg.bundle}?", confirm_label="Remove", danger=True
            ),
            _on_confirm,
        )

    def on_bundle_tree_add_item_requested(self, msg: BundleTree.AddItemRequested) -> None:
        def _on_path(values: dict | None) -> None:
            if values is None:
                return
            path = values["path"]
            if not path:
                self.notify("Path is required", severity="warning")
                return

            def _on_mode(mode: str | None) -> None:
                if mode is None:
                    return
                try:
                    result = edit.add_bundle_item(self.state.repo, msg.bundle, path, mode)
                except (ValueError, FileExistsError, FileNotFoundError) as e:
                    self.notify(str(e), severity="error")
                    return
                content_path = self.state.repo / "bundles" / msg.bundle / "files" / path
                filled = (
                    self._open_editor(content_path)
                    if mode == edit.MODE_PLAIN
                    else self._edit_and_encrypt(content_path)
                )
                if not filled:
                    self.notify("Item registered with no content yet", severity="warning")
                if self._commit(result):
                    self._refresh()
                    self.notify(f"Added {path} to {msg.bundle} ({mode})")

            self.app.push_screen(PickerModal("Mode", [edit.MODE_PLAIN, edit.MODE_SECRET]), _on_mode)

        self.app.push_screen(
            FormModal(f"Add item to {msg.bundle}", [("path", "Path (~-relative)", "")]), _on_path
        )

    def on_bundle_tree_edit_item_requested(self, msg: BundleTree.EditItemRequested) -> None:
        p = self.state.repo / "bundles" / msg.bundle / "files" / msg.path
        if not self._decrypt_edit_reencrypt(p):
            return
        result = edit.EditResult(
            [f"bundles/{msg.bundle}/files/{msg.path}"], f"bundle: edit {msg.path} in {msg.bundle}"
        )
        if self._commit(result):
            self._refresh()
            self.notify(f"Edited {msg.path}")

    def on_bundle_tree_preview_requested(self, msg: BundleTree.PreviewRequested) -> None:
        if msg.mode == edit.MODE_SECRET:
            self.query_one(MainPane).show_text(f"{msg.path} (secret)", _SECRET_PREVIEW)
            return
        p = self.state.repo / "bundles" / msg.bundle / "files" / msg.path
        try:
            text = p.read_text(errors="replace")
        except OSError as e:
            self.notify(str(e), severity="error")
            return
        self.query_one(MainPane).show_text(msg.path, text)

    # -- fragments ---------------------------------------------------------------

    def on_fragment_tree_new_requested(self, msg: FragmentTree.NewRequested) -> None:
        # Owner must be a real bundle or preset name — materialize.py only
        # activates a fragment whose owner is in a resolved preset's bundle
        # list or is the preset's own name, so a free-typed owner could
        # silently create a fragment that never composes into anything.
        owners = sorted(set(self.state.bundles) | set(self.state.presets))
        if not owners:
            self.notify("No bundles or presets to own a new fragment", severity="warning")
            return

        def _on_target(values: dict | None) -> None:
            if values is None:
                return
            target = values["target"]
            if not target:
                self.notify("Target is required", severity="warning")
                return

            def _on_owner(owner: str | None) -> None:
                if owner is None:
                    return

                def _on_secret(choice: str | None) -> None:
                    if choice is None:
                        return
                    secret = choice == "secret"
                    try:
                        result = edit.create_fragment(self.state.repo, target, owner, secret)
                    except (ValueError, FileExistsError) as e:
                        self.notify(str(e), severity="error")
                        return
                    content_path = (
                        self.state.repo / "fragments" / result.paths[0].removeprefix("fragments/")
                    )
                    filled = (
                        self._edit_and_encrypt(content_path)
                        if secret
                        else self._open_editor(content_path)
                    )
                    if not filled:
                        self.notify("Fragment created with no content yet", severity="warning")
                    if self._commit(result):
                        self._refresh()
                        self.notify(f"Created fragment {result.paths[0]}")

                self.app.push_screen(PickerModal("Secret?", ["plain", "secret"]), _on_secret)

            self.app.push_screen(PickerModal("Owner (bundle or preset)", owners), _on_owner)

        self.app.push_screen(
            FormModal("New fragment", [("target", "Target file (~-relative)", msg.target_hint or "")]),
            _on_target,
        )

    def on_fragment_tree_edit_content_requested(self, msg: FragmentTree.EditContentRequested) -> None:
        p = self.state.repo / "fragments" / msg.rel_path
        filled = self._decrypt_edit_reencrypt(p) if msg.secret else self._open_editor(p)
        if not filled:
            return
        result = edit.EditResult([f"fragments/{msg.rel_path}"], f"fragment: edit {msg.rel_path}")
        if self._commit(result):
            self._refresh()
            self.notify(f"Edited {msg.rel_path}")

    def on_fragment_tree_reorder_requested(self, msg: FragmentTree.ReorderRequested) -> None:
        def _on_result(values: dict | None) -> None:
            if values is None:
                return
            try:
                result = edit.reorder_fragment(self.state.repo, msg.rel_path, values["order"])
            except (ValueError, FileExistsError, FileNotFoundError) as e:
                self.notify(str(e), severity="error")
                return
            if self._commit(result):
                self._refresh()
                self.notify(f"Reordered to {result.paths[-1]}")

        self.app.push_screen(
            FormModal(f"Reorder {msg.rel_path}", [("order", "New prefix (e.g. 20)", "")]), _on_result
        )

    def on_fragment_tree_delete_requested(self, msg: FragmentTree.DeleteRequested) -> None:
        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            result = edit.delete_fragment(self.state.repo, msg.rel_path)
            if self._commit(result):
                self._refresh()
                self.notify(f"Deleted {msg.rel_path}")

        self.app.push_screen(
            ConfirmModal("Delete fragment", f"Delete {msg.rel_path}?", confirm_label="Delete", danger=True),
            _on_confirm,
        )

    def on_fragment_tree_toggle_exclude_requested(self, msg: FragmentTree.ToggleExcludeRequested) -> None:
        if not self.state.selected_preset:
            self.notify("Select a preset first (panel 1)", severity="warning")
            return
        result = edit.toggle_exclude_fragment(self.state.repo, self.state.selected_preset, msg.rel_path)
        if self._commit(result):
            self._refresh()
            self.notify(result.message)

    def on_fragment_tree_preview_requested(self, msg: FragmentTree.PreviewRequested) -> None:
        if msg.secret:
            self.query_one(MainPane).show_text(f"{msg.rel_path} (secret)", _SECRET_PREVIEW)
            return
        p = self.state.repo / "fragments" / msg.rel_path
        try:
            text = p.read_text(errors="replace")
        except OSError as e:
            self.notify(str(e), severity="error")
            return
        self.query_one(MainPane).show_text(msg.rel_path, text)
