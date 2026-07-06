#!/usr/bin/env bash
# bootstrap.sh — install Nix if missing, then launch the dotfiles TUI.
#
# Nix is the only dependency of this repo. This script's sole job is getting
# Nix onto a fresh machine (which needs curl, once); with Nix already
# installed it is equivalent to `nix run . --impure`.

set -euo pipefail

REPO_DIR="$(dirname "$(realpath "$0")")"

# ---------------------------------------------------------------------------
# 1. Install Nix
# ---------------------------------------------------------------------------
if ! command -v nix &>/dev/null; then
  if ! command -v curl &>/dev/null; then
    echo "ERROR: Nix is not installed and curl is unavailable to fetch it." >&2
    echo "       Install Nix yourself (https://nixos.org/download) and re-run." >&2
    exit 1
  fi
  echo "Installing Nix via Determinate Systems..."
  curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix \
    | sh -s -- install --no-confirm
fi

# Source the Nix profile if nix isn't in PATH yet.
NIX_PROFILE="/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh"
if [[ -f "$NIX_PROFILE" ]] && ! command -v nix &>/dev/null; then
  # shellcheck source=/dev/null
  source "$NIX_PROFILE"
fi

if ! command -v nix &>/dev/null; then
  echo "ERROR: 'nix' is still not in PATH. Open a new shell and re-run." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# 2. Launch the TUI
# ---------------------------------------------------------------------------
cd "$REPO_DIR"
exec nix run .#tui --impure \
  --extra-experimental-features "nix-command flakes"
