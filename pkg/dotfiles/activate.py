"""Non-interactive CLI for home-manager activation hooks.

Invoked from the store at switch time (see lib/files-activation.nix and
modules/vcs/default.nix), so it must work with plain `python3 activate.py`
and no PYTHONPATH:

    activate.py deploy-all --modules-root <dir> [--enable <mod>]...
                           [--disable-child <mod>:<child>]...
                           [--sops-bin <bin>]
    activate.py deploy --module-dir <dir> [--sops-bin <bin>] [--overwrite]
                       [--disable-child <name>]...
    activate.py clean --module-dir <dir> [--sops-bin <bin>] [--force]
    activate.py pubkey --ssh-keygen <bin> --email <addr>

`deploy-all` is what lib/files-activation.nix runs at switch time: it
deploys the tracked files of every --enable'd module, composes fragment
targets (one $HOME file assembled from blocks contributed by several
modules, ordered by their manifest `order`), then prunes files recorded
in ~/.local/state/dotfiles/deployed.json that are no longer desired
(module/child disabled, file untracked, module deleted) — so undeploy is
declarative. A path tracked whole-file by one module and as a fragment
by another (or whole-file by two modules) is a config error: exit 2
before anything is deployed. Files with local edits are never overwritten or
pruned here, only warned about — overwrite/force decisions are made per
file in the TUI, behind confirmation dialogs. A conflict in one module
doesn't stop the others; the exit code is non-zero if any module had
conflicts.

`deploy`/`deploy-all` skip secrets (with a warning) when no age key is
present yet, and skip files owned by disabled child toggles
(--disable-child).

`clean` removes a module's tracked files from $HOME (repo copies are left
alone) — a manual escape hatch; switch-time cleanup happens via deploy-all.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotfiles.core import agekey, files  # noqa: E402
from dotfiles.core import manifest as mf  # noqa: E402


def _cmd_deploy_all(args: argparse.Namespace) -> int:
    modules_root = Path(args.modules_root)
    skip_secrets = not agekey.has_key()
    if skip_secrets:
        print(
            f"files: no age key at {agekey.key_path()}; deploying plain files only",
            flush=True,
        )

    disabled: dict[str, set[str]] = {}
    for item in args.disable_child:
        module, sep, child = item.partition(":")
        if not sep or not module or not child:
            print(f"Error: --disable-child expects <module>:<child>, got {item!r}")
            return 2
        disabled.setdefault(module, set()).add(child)

    enabled = [(modules_root / n, disabled.get(n, set())) for n in args.enable]
    frag_targets, errors = files.partition_targets(enabled)
    if errors:
        print("Error: " + "; ".join(errors), flush=True)
        return 2
    desired = files.desired_paths(enabled)
    conflicts: list[str] = []
    for module_dir, mod_disabled in enabled:
        if not mf.load(module_dir):  # [] when the module tracks no files
            continue
        try:
            files.deploy_module(
                module_dir,
                sops_bin=args.sops_bin,
                skip_secrets=skip_secrets,
                disabled_children=mod_disabled,
            )
        except RuntimeError as e:
            conflicts.append(f"{module_dir.name}: {e}")

    try:
        files.deploy_fragments(
            frag_targets, sops_bin=args.sops_bin, skip_secrets=skip_secrets
        )
    except RuntimeError as e:
        conflicts.append(f"composed: {e}")

    files.prune(desired)

    if conflicts:
        print("Error: " + "; ".join(conflicts), flush=True)
        return 1
    return 0


def _cmd_deploy(args: argparse.Namespace) -> int:
    module_dir = Path(args.module_dir)
    skip_secrets = not agekey.has_key()
    if skip_secrets:
        print(
            f"files: no age key at {agekey.key_path()}; deploying plain files only",
            flush=True,
        )
    files.deploy_module(
        module_dir,
        overwrite=args.overwrite,
        sops_bin=args.sops_bin,
        skip_secrets=skip_secrets,
        disabled_children=set(args.disable_child),
    )
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    module_dir = Path(args.module_dir)
    files.clean_module(module_dir, force=args.force, sops_bin=args.sops_bin)
    return 0


def _cmd_pubkey(args: argparse.Namespace) -> int:
    agekey.setup_pubkey(args.ssh_keygen, args.email)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="activate.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_all = sub.add_parser(
        "deploy-all",
        help="deploy every enabled module's files and prune undeployed ones",
    )
    p_all.add_argument("--modules-root", required=True)
    p_all.add_argument("--sops-bin", default=None)
    p_all.add_argument(
        "--enable",
        action="append",
        default=[],
        metavar="MODULE",
        help="enabled module name (repeatable)",
    )
    p_all.add_argument(
        "--disable-child",
        action="append",
        default=[],
        metavar="MODULE:CHILD",
        help="skip files owned by this child toggle (repeatable)",
    )
    p_all.set_defaults(func=_cmd_deploy_all)

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
