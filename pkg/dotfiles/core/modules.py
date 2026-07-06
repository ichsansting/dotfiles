"""Module discovery from modules/*/module.json.

module.json is the single source of truth for the module set and each
module's toggleable children. It is read by BOTH this package and the Nix
side (lib/modules.nix), so the two can never disagree on enumeration.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# Strict subset of Nix unquoted attribute identifiers, so a generated
# `options.dotfiles.<name>` always parses.
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

# Minimal childless module, mirroring modules/env/default.nix. The name is
# the only substitution — the description stays in module.json, never here.
_DEFAULT_NIX_TEMPLATE = """\
{{ lib, config, ... }}:
let
  cfg = config.dotfiles.{name};
in
{{
  options.dotfiles.{name} = import ../../lib/module-options.nix {{ inherit lib; }} ./module.json;

  config = lib.mkIf cfg.enable {{ }};
}}
"""


@dataclass(frozen=True)
class Module:
    name: str
    path: Path
    description: str
    children: dict[str, str] = field(default_factory=dict)  # name -> description


def modules_dir(repo: Path) -> Path:
    return repo / "modules"


def discover(repo: Path) -> list[Module]:
    """All modules: subdirs of modules/ with BOTH default.nix and module.json.

    A directory with only one of the two files is a wiring bug (Nix and the
    TUI would disagree about it), so it raises instead of being skipped.
    """
    result: list[Module] = []
    root = modules_dir(repo)
    if not root.exists():
        return result
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        has_nix = (d / "default.nix").exists()
        has_meta = (d / "module.json").exists()
        if not has_nix and not has_meta:
            continue
        if has_nix != has_meta:
            missing = "module.json" if has_nix else "default.nix"
            raise RuntimeError(f"module '{d.name}' is missing {missing}")
        meta = json.loads((d / "module.json").read_text())
        result.append(
            Module(
                name=d.name,
                path=d,
                description=meta.get("description", ""),
                children=dict(meta.get("children", {})),
            )
        )
    return result


def validate_name(repo: Path, name: str) -> str | None:
    """Why `name` cannot become a new module, or None if it can."""
    if not name:
        return "name required"
    if not NAME_RE.match(name):
        return "use lowercase letters, digits, - and _, starting with a letter"
    if (modules_dir(repo) / name).exists():
        return f"module '{name}' already exists"
    return None


def create(repo: Path, name: str, description: str = "") -> Module:
    """Scaffold modules/<name>/{default.nix,module.json}.

    Both Nix (lib/modules.nix) and discover() pick the module up
    automatically. No files.json — files.add creates it lazily. The module
    resolves to enable=false until a preset or override turns it on.
    """
    error = validate_name(repo, name)
    if error:
        raise ValueError(error)
    d = modules_dir(repo) / name
    d.mkdir(parents=True)
    try:
        # discover() raises on a dir with only one of the two files, so
        # never leave a half-written module behind.
        (d / "module.json").write_text(
            json.dumps({"description": description, "children": {}}, indent=2) + "\n"
        )
        (d / "default.nix").write_text(_DEFAULT_NIX_TEMPLATE.format(name=name))
    except Exception:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return Module(name=name, path=d, description=description)
