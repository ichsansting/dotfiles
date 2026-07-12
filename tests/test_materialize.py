"""Materialize core: preset -> bundle list, settings overlay, fragment
compose, file-write plan. See .scratch/ephemeral-shell/issues/11-core-materialize-module.md
and .scratch/ephemeral-shell/spec.md ("Fragment composition")."""
from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles.core import materialize as m
from conftest import write_bundle_file, write_fragment, write_preset


# -- bundle list resolution ---------------------------------------------------


def test_resolve_bundles_own_only(root: Path):
    write_preset(root, "personal", bundles=["vcs", "editor"], settings={})
    preset = m.load_preset(root, "personal")
    assert preset.bundles == ["vcs", "editor"]


def test_resolve_bundles_inherits_from_base(root: Path):
    write_preset(root, "default", bundles=["vcs", "editor"], settings={})
    write_preset(root, "work1", base="default", bundles=["work-tools"], settings={})
    preset = m.load_preset(root, "work1")
    assert preset.bundles == ["vcs", "editor", "work-tools"]


def test_resolve_bundles_dedupes_against_base(root: Path):
    write_preset(root, "default", bundles=["vcs"], settings={})
    write_preset(root, "work1", base="default", bundles=["vcs", "work-tools"], settings={})
    preset = m.load_preset(root, "work1")
    assert preset.bundles == ["vcs", "work-tools"]


# -- settings overlay resolution ----------------------------------------------


def test_settings_overlay_own_only(root: Path):
    write_preset(root, "personal", bundles=[], settings={"git": {"name": "Sting"}})
    preset = m.load_preset(root, "personal")
    assert preset.settings == {"git": {"name": "Sting"}}


def test_settings_overlay_child_overrides_base(root: Path):
    write_preset(
        root, "default", bundles=[],
        settings={"git": {"name": "Sting", "email": "a@example.com"}, "claude": {"account": "personal"}},
    )
    write_preset(root, "work1", base="default", bundles=[], settings={"claude": {"account": "work1"}})
    preset = m.load_preset(root, "work1")
    assert preset.settings == {
        "git": {"name": "Sting", "email": "a@example.com"},
        "claude": {"account": "work1"},
    }


# -- fragment filtering --------------------------------------------------------


def test_fragment_survives_if_owner_bundle_active(root: Path):
    write_preset(root, "personal", bundles=["vcs"], settings={})
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "vcs content\n")
    plan = {e.path: e for e in m.build_plan(root, "personal")}
    assert plan[".claude/CLAUDE.md"].content == b"vcs content\n"


def test_fragment_dropped_if_owner_bundle_inactive(root: Path):
    write_preset(root, "personal", bundles=["vcs"], settings={})
    write_fragment(root, ".claude/CLAUDE.md", "10", "work-tools", "work content\n")
    plan = {e.path: e for e in m.build_plan(root, "personal")}
    assert ".claude/CLAUDE.md" not in plan


def test_fragment_survives_if_owner_is_preset_itself(root: Path):
    write_preset(root, "personal", bundles=[], settings={})
    write_fragment(root, ".claude/CLAUDE.md", "10", "personal", "preset content\n")
    plan = {e.path: e for e in m.build_plan(root, "personal")}
    assert plan[".claude/CLAUDE.md"].content == b"preset content\n"


def test_exclude_fragments_suppresses_one_contributor(root: Path):
    write_preset(
        root, "personal", bundles=["vcs", "shell"],
        settings={"exclude_fragments": [".claude/CLAUDE.md.d/10-vcs.md"]},
    )
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "vcs\n")
    write_fragment(root, ".claude/CLAUDE.md", "20", "shell", "shell\n")
    plan = {e.path: e for e in m.build_plan(root, "personal")}
    assert plan[".claude/CLAUDE.md"].content == b"shell\n"


# -- fragment compose ----------------------------------------------------------


def test_compose_sorts_trims_joins_with_blank_line(root: Path):
    write_preset(root, "personal", bundles=["vcs", "shell"], settings={})
    write_fragment(root, ".claude/CLAUDE.md", "20", "shell", "second\n\n\n")
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "first")
    plan = {e.path: e for e in m.build_plan(root, "personal")}
    assert plan[".claude/CLAUDE.md"].content == b"first\n\nsecond\n"


def test_compose_drops_empty_blocks(root: Path):
    write_preset(root, "personal", bundles=["vcs", "shell"], settings={})
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "\n\n")
    write_fragment(root, ".claude/CLAUDE.md", "20", "shell", "content\n")
    plan = {e.path: e for e in m.build_plan(root, "personal")}
    assert plan[".claude/CLAUDE.md"].content == b"content\n"


def test_target_dropped_when_all_surviving_fragments_are_empty(root: Path):
    write_preset(root, "personal", bundles=["vcs"], settings={})
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "\n\n")
    plan = {e.path: e for e in m.build_plan(root, "personal")}
    assert ".claude/CLAUDE.md" not in plan


# -- whole-file vs fragment mixing error ---------------------------------------


def test_whole_file_and_fragment_same_target_raises(root: Path):
    write_preset(root, "personal", bundles=["vcs", "shell"], settings={})
    write_bundle_file(root, "vcs", ".gitconfig", "plain", "whole\n")
    write_fragment(root, ".gitconfig", "10", "shell", "frag\n")
    with pytest.raises(m.ConfigError):
        m.build_plan(root, "personal")


def test_two_whole_file_owners_same_target_raises(root: Path):
    write_preset(root, "personal", bundles=["vcs", "shell"], settings={})
    write_bundle_file(root, "vcs", ".gitconfig", "plain", "a\n")
    write_bundle_file(root, "shell", ".gitconfig", "plain", "b\n")
    with pytest.raises(m.ConfigError):
        m.build_plan(root, "personal")


# -- secret contributor unavailable --------------------------------------------


def test_fragment_target_skipped_when_secret_contributor_missing(root: Path):
    write_preset(root, "personal", bundles=["vcs", "secrets"], settings={})
    write_fragment(root, ".aws/config", "10", "vcs", "plain part\n")
    write_fragment(root, ".aws/config", "20", "secrets", "SECRET_PLACEHOLDER", secret=True)
    plan = {e.path: e for e in m.build_plan(root, "personal", decrypted_secrets={})}
    assert ".aws/config" not in plan


def test_fragment_target_written_when_secret_contributor_available(root: Path):
    write_preset(root, "personal", bundles=["vcs", "secrets"], settings={})
    write_fragment(root, ".aws/config", "10", "vcs", "plain part\n")
    write_fragment(root, ".aws/config", "20", "secrets", "SECRET_PLACEHOLDER", secret=True)
    secret_key = ".aws/config.d/20-secrets.secret.md"
    plan = {
        e.path: e
        for e in m.build_plan(root, "personal", decrypted_secrets={secret_key: b"decrypted\n"})
    }
    assert plan[".aws/config"].content == b"plain part\n\ndecrypted\n"
    assert plan[".aws/config"].mode == "secret"


def test_whole_file_secret_skipped_when_unavailable(root: Path):
    write_preset(root, "personal", bundles=["ssh"], settings={})
    write_bundle_file(root, "ssh", ".ssh/id_ed25519", "secret")
    plan = {e.path: e for e in m.build_plan(root, "personal", decrypted_secrets={})}
    assert ".ssh/id_ed25519" not in plan


def test_whole_file_missing_fixture_content_raises_with_context(root: Path):
    write_preset(root, "personal", bundles=["vcs"], settings={})
    write_bundle_file(root, "vcs", ".gitconfig", "plain", "cfg\n")
    (root / "bundles" / "vcs" / "files" / ".gitconfig").unlink()
    with pytest.raises(FileNotFoundError, match="vcs.*\\.gitconfig"):
        m.build_plan(root, "personal")


def test_whole_file_secret_written_when_available(root: Path):
    write_preset(root, "personal", bundles=["ssh"], settings={})
    write_bundle_file(root, "ssh", ".ssh/id_ed25519", "secret")
    plan = {
        e.path: e
        for e in m.build_plan(root, "personal", decrypted_secrets={".ssh/id_ed25519": b"KEY\n"})
    }
    assert plan[".ssh/id_ed25519"].content == b"KEY\n"
    assert plan[".ssh/id_ed25519"].mode == "secret"


# -- no external tool dependency -----------------------------------------------


def test_module_has_no_nix_sops_git_imports():
    import ast
    import inspect

    src = inspect.getsource(m)
    tree = ast.parse(src)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    banned = {"subprocess", "git", "sops"}
    assert not (names & banned)
