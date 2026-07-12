"""Bundle/preset/fragment CRUD. See
.scratch/ephemeral-shell/issues/17-editing-tui-crud.md.

No git here — gitops.py (tested separately in test_gitops.py) is the only
thing that touches git; these exercise the FS mutations edit.py performs
before a caller commits.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from dotfiles.core import edit
from conftest import write_bundle_file, write_fragment, write_preset

# -- bundles -----------------------------------------------------------------


def test_create_bundle_writes_empty_manifest(root: Path):
    result = edit.create_bundle(root, "newbundle")

    assert result.paths == ["bundles/newbundle/files.json"]
    assert "create newbundle" in result.message
    manifest = json.loads((root / "bundles/newbundle/files.json").read_text())
    assert manifest == {"files": [], "packages": []}


def test_create_bundle_rejects_duplicate(root: Path):
    edit.create_bundle(root, "dup")
    with pytest.raises(FileExistsError):
        edit.create_bundle(root, "dup")


def test_create_bundle_rejects_bad_name(root: Path):
    with pytest.raises(ValueError):
        edit.create_bundle(root, "has space")


def test_rename_bundle_updates_referencing_presets(root: Path):
    write_bundle_file(root, "vcs", ".gitconfig", "plain", content="[user]\n")
    write_preset(root, "default", bundles=["vcs", "terminal"], settings={})

    result = edit.rename_bundle(root, "vcs", "git")

    assert not (root / "bundles/vcs").exists()
    assert (root / "bundles/git/files/.gitconfig").read_text() == "[user]\n"
    data = json.loads((root / "presets/default.json").read_text())
    assert data["bundles"] == ["git", "terminal"]
    assert "presets/default.json" in result.paths


def test_rename_bundle_missing_source_raises(root: Path):
    with pytest.raises(FileNotFoundError):
        edit.rename_bundle(root, "nope", "new")


def test_delete_bundle_prunes_preset_references(root: Path):
    edit.create_bundle(root, "gone")
    write_preset(root, "default", bundles=["gone", "terminal"], settings={})

    edit.delete_bundle(root, "gone")

    assert not (root / "bundles/gone").exists()
    data = json.loads((root / "presets/default.json").read_text())
    assert data["bundles"] == ["terminal"]


def test_add_bundle_item_plain_touches_empty_file(root: Path):
    edit.create_bundle(root, "vcs")

    result = edit.add_bundle_item(root, "vcs", ".gitconfig", "plain")

    assert (root / "bundles/vcs/files/.gitconfig").exists()
    manifest = json.loads((root / "bundles/vcs/files.json").read_text())
    assert manifest["files"] == [{"path": ".gitconfig", "mode": "plain"}]
    assert result.paths == ["bundles/vcs/files.json", "bundles/vcs/files/.gitconfig"]


def test_add_bundle_item_secret_leaves_content_unwritten(root: Path):
    edit.create_bundle(root, "vcs")

    edit.add_bundle_item(root, "vcs", ".ssh/id_ed25519", "secret")

    assert not (root / "bundles/vcs/files/.ssh/id_ed25519").exists()
    manifest = json.loads((root / "bundles/vcs/files.json").read_text())
    assert manifest["files"] == [{"path": ".ssh/id_ed25519", "mode": "secret"}]


def test_add_bundle_item_rejects_duplicate_path(root: Path):
    edit.create_bundle(root, "vcs")
    edit.add_bundle_item(root, "vcs", ".gitconfig", "plain")
    with pytest.raises(FileExistsError):
        edit.add_bundle_item(root, "vcs", ".gitconfig", "plain")


def test_add_bundle_item_rejects_path_traversal(root: Path):
    edit.create_bundle(root, "vcs")
    with pytest.raises(ValueError):
        edit.add_bundle_item(root, "vcs", "../../etc/passwd", "plain")


def test_add_bundle_item_rejects_bad_mode(root: Path):
    edit.create_bundle(root, "vcs")
    with pytest.raises(ValueError):
        edit.add_bundle_item(root, "vcs", ".gitconfig", "bogus")


def test_remove_bundle_item_deletes_content(root: Path):
    write_bundle_file(root, "vcs", ".gitconfig", "plain", content="[user]\n")

    result = edit.remove_bundle_item(root, "vcs", ".gitconfig")

    manifest = json.loads((root / "bundles/vcs/files.json").read_text())
    assert manifest["files"] == []
    assert not (root / "bundles/vcs/files/.gitconfig").exists()
    assert "bundles/vcs/files/.gitconfig" in result.paths


def test_remove_bundle_item_missing_raises(root: Path):
    edit.create_bundle(root, "vcs")
    with pytest.raises(FileNotFoundError):
        edit.remove_bundle_item(root, "vcs", ".gitconfig")


# -- presets -------------------------------------------------------------------


def test_create_preset_with_base(root: Path):
    write_preset(root, "default", bundles=[], settings={})

    result = edit.create_preset(root, "work1", base="default")

    data = json.loads((root / "presets/work1.json").read_text())
    assert data == {"base": "default", "bundles": [], "settings": {}}
    assert result.paths == ["presets/work1.json"]


def test_create_preset_missing_base_raises(root: Path):
    with pytest.raises(FileNotFoundError):
        edit.create_preset(root, "work1", base="nope")


def test_delete_preset_blocked_when_used_as_base(root: Path):
    write_preset(root, "default", bundles=[], settings={})
    write_preset(root, "work1", base="default", bundles=[], settings={})

    with pytest.raises(ValueError, match="work1"):
        edit.delete_preset(root, "default")


def test_delete_preset_succeeds_when_unreferenced(root: Path):
    write_preset(root, "default", bundles=[], settings={})
    edit.delete_preset(root, "default")
    assert not (root / "presets/default.json").exists()


def test_toggle_bundle_in_preset_adds_then_removes(root: Path):
    edit.create_bundle(root, "vcs")
    write_preset(root, "default", bundles=[], settings={})

    added = edit.toggle_bundle_in_preset(root, "default", "vcs")
    assert json.loads((root / "presets/default.json").read_text())["bundles"] == ["vcs"]
    assert "add" in added.message

    removed = edit.toggle_bundle_in_preset(root, "default", "vcs")
    assert json.loads((root / "presets/default.json").read_text())["bundles"] == []
    assert "remove" in removed.message


def test_toggle_bundle_in_preset_unknown_bundle_raises(root: Path):
    write_preset(root, "default", bundles=[], settings={})
    with pytest.raises(FileNotFoundError):
        edit.toggle_bundle_in_preset(root, "default", "nope")


def test_set_preset_base_rejects_self(root: Path):
    write_preset(root, "default", bundles=[], settings={})
    with pytest.raises(ValueError):
        edit.set_preset_base(root, "default", "default")


def test_set_preset_base_rejects_cycle(root: Path):
    write_preset(root, "a", bundles=[], settings={})
    write_preset(root, "b", base="a", bundles=[], settings={})
    with pytest.raises(ValueError, match="cycle"):
        edit.set_preset_base(root, "a", "b")


def test_set_preset_base_clears_with_none(root: Path):
    write_preset(root, "default", bundles=[], settings={})
    write_preset(root, "work1", base="default", bundles=[], settings={})

    edit.set_preset_base(root, "work1", None)

    data = json.loads((root / "presets/work1.json").read_text())
    assert "base" not in data


def test_set_setting_nested_key(root: Path):
    write_preset(root, "default", bundles=[], settings={})

    edit.set_setting(root, "default", "git.name", "Ichsan")

    data = json.loads((root / "presets/default.json").read_text())
    assert data["settings"] == {"git": {"name": "Ichsan"}}


def test_set_setting_preserves_sibling_keys(root: Path):
    write_preset(root, "default", bundles=[], settings={"git": {"email": "a@b.c"}})

    edit.set_setting(root, "default", "git.name", "Ichsan")

    data = json.loads((root / "presets/default.json").read_text())
    assert data["settings"] == {"git": {"email": "a@b.c", "name": "Ichsan"}}


def test_toggle_exclude_fragment_round_trips(root: Path):
    write_preset(root, "default", bundles=[], settings={})

    excluded = edit.toggle_exclude_fragment(root, "default", ".claude/CLAUDE.md.d/10-vcs.md")
    data = json.loads((root / "presets/default.json").read_text())
    assert data["settings"]["exclude_fragments"] == [".claude/CLAUDE.md.d/10-vcs.md"]
    assert "exclude" in excluded.message

    included = edit.toggle_exclude_fragment(root, "default", ".claude/CLAUDE.md.d/10-vcs.md")
    data = json.loads((root / "presets/default.json").read_text())
    assert "exclude_fragments" not in data["settings"]
    assert "include" in included.message


# -- fragments -----------------------------------------------------------------


def test_create_fragment_auto_numbers_past_existing(root: Path):
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "existing")

    result = edit.create_fragment(root, ".claude/CLAUDE.md", "terminal", secret=False)

    assert result.paths == ["fragments/.claude/CLAUDE.md.d/20-terminal.md"]
    assert (root / "fragments/.claude/CLAUDE.md.d/20-terminal.md").exists()


def test_create_fragment_first_in_target_gets_10(root: Path):
    result = edit.create_fragment(root, ".config/mise/config.toml", "mise-rust", secret=False)
    assert result.paths == ["fragments/.config/mise/config.toml.d/10-mise-rust.md"]


def test_create_fragment_secret_suffix(root: Path):
    result = edit.create_fragment(root, ".claude/CLAUDE.md", "vcs", secret=True)
    assert result.paths == ["fragments/.claude/CLAUDE.md.d/10-vcs.secret.md"]


def test_fragment_targets_groups_and_sorts(root: Path):
    write_fragment(root, ".claude/CLAUDE.md", "20", "terminal", "b")
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "a")

    targets = edit.fragment_targets(root)

    assert list(f.owner for f in targets[".claude/CLAUDE.md"]) == ["vcs", "terminal"]


def test_reorder_fragment_renames_prefix(root: Path):
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "content")

    result = edit.reorder_fragment(root, ".claude/CLAUDE.md.d/10-vcs.md", "30")

    assert not (root / "fragments/.claude/CLAUDE.md.d/10-vcs.md").exists()
    new_path = root / "fragments/.claude/CLAUDE.md.d/30-vcs.md"
    assert new_path.exists()
    assert new_path.read_text() == "content"
    assert result.paths == [
        "fragments/.claude/CLAUDE.md.d/10-vcs.md",
        "fragments/.claude/CLAUDE.md.d/30-vcs.md",
    ]


def test_reorder_fragment_preserves_secret_suffix(root: Path):
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "secret", secret=True)

    edit.reorder_fragment(root, ".claude/CLAUDE.md.d/10-vcs.secret.md", "40")

    assert (root / "fragments/.claude/CLAUDE.md.d/40-vcs.secret.md").exists()


def test_reorder_fragment_rejects_bad_order(root: Path):
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "content")
    with pytest.raises(ValueError):
        edit.reorder_fragment(root, ".claude/CLAUDE.md.d/10-vcs.md", "not-a-number")


def test_delete_fragment_removes_file(root: Path):
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "content")

    edit.delete_fragment(root, ".claude/CLAUDE.md.d/10-vcs.md")

    assert not (root / "fragments/.claude/CLAUDE.md.d/10-vcs.md").exists()


def test_delete_fragment_missing_raises(root: Path):
    with pytest.raises(FileNotFoundError):
        edit.delete_fragment(root, ".claude/CLAUDE.md.d/10-vcs.md")
