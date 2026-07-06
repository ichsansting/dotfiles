"""Non-interactive CLI for home-manager activation hooks.

Invoked from the store at switch time (see lib/files-activation.nix and
modules/vcs/default.nix), so it must work with plain `python3 activate.py`
and no PYTHONPATH:

    activate.py deploy --module-dir <dir> [--sops-bin <bin>] [--overwrite]
                       [--disable-child <name>]...
    activate.py clean --module-dir <dir> [--sops-bin <bin>] [--force]
    activate.py pubkey --ssh-keygen <bin> --email <addr>

`deploy` honors DOTFILES_OVERWRITE=1 as an alternative to --overwrite,
skips secrets (exit 0, with a warning) when no age key is present yet, and
skips files owned by any --disable-child toggle (passed by
lib/files-activation.nix for children that are switched off).

`clean` removes a module's tracked files from $HOME (repo copies are left
alone). Not wired into home-manager activation — run it by hand after
disabling a module. Honors DOTFILES_FORCE=1 as an alternative to --force.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotfiles.core import agekey, files  # noqa: E402


def _cmd_deploy(args: argparse.Namespace) -> int:
    module_dir = Path(args.module_dir)
    overwrite = args.overwrite or os.environ.get("DOTFILES_OVERWRITE") == "1"
    skip_secrets = not agekey.has_key()
    if skip_secrets:
        print(
            f"files: no age key at {agekey.key_path()}; deploying plain files only",
            flush=True,
        )
    files.deploy_module(
        module_dir,
        overwrite=overwrite,
        sops_bin=args.sops_bin,
        skip_secrets=skip_secrets,
        disabled_children=set(args.disable_child),
    )
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    module_dir = Path(args.module_dir)
    force = args.force or os.environ.get("DOTFILES_FORCE") == "1"
    files.clean_module(module_dir, force=force, sops_bin=args.sops_bin)
    return 0


def _cmd_pubkey(args: argparse.Namespace) -> int:
    agekey.setup_pubkey(args.ssh_keygen, args.email)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="activate.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_deploy = sub.add_parser("deploy", help="deploy a module's tracked files into $HOME")
    p_deploy.add_argument("--module-dir", required=True)
    p_deploy.add_argument("--sops-bin", default=None)
    p_deploy.add_argument("--overwrite", action="store_true")
    p_deploy.add_argument(
        "--disable-child",
        action="append",
        default=[],
        metavar="NAME",
        help="skip files owned by this child toggle (repeatable)",
    )
    p_deploy.set_defaults(func=_cmd_deploy)

    p_clean = sub.add_parser("clean", help="remove a module's tracked files from $HOME")
    p_clean.add_argument("--module-dir", required=True)
    p_clean.add_argument("--sops-bin", default=None)
    p_clean.add_argument("--force", action="store_true")
    p_clean.set_defaults(func=_cmd_clean)

    p_pubkey = sub.add_parser("pubkey", help="derive ssh pubkey + allowed_signers")
    p_pubkey.add_argument("--ssh-keygen", required=True)
    p_pubkey.add_argument("--email", required=True)
    p_pubkey.set_defaults(func=_cmd_pubkey)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
