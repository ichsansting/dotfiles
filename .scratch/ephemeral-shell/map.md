Status: wayfinder:map

## Destination

A design spec for an ephemeral personal-shell launcher that replaces `~/dotfiles-old` entirely. On any machine with Nix already installed — own laptop or a shared same-uid bastion account (AWS SSM) — a short command builds and drops you into your full personal shell (packages, dotfiles, secrets/credentials) inside an isolated, throwaway `$HOME`, via a Nix flake (no home-manager) plus a script that materializes config and decrypts secrets there. On exit, the whole session — including its isolation boundary — is wiped; only the shared Nix store persists on the machine, so the next launch is fast. This map is plan-only: it ends when the design decisions are settled, not when code ships.

## Notes

- Domain: `~/dotfiles-old` (Nix flake + home-manager + Python/Textual TUI + sops/age) is the predecessor system being replaced, not extended — read its README/modules for prior art, not as a target to preserve.
- Threat model: same-uid peer users on a shared bastion account (AWS SSM login); root is trusted, not defended against.
- Locked decisions (settled during destination-scoping — not subject to re-litigation by tickets):
  - No persistent-deploy mode anywhere, including the user's own laptop — every launch rebuilds into a throwaway `$HOME`.
  - No home-manager — a flake defines packages (`nix shell`/`profile`/`develop`), a plain script materializes dotfiles and decrypts secrets into the ephemeral `$HOME`.
  - sops+age is the assumed secrets-encryption mechanism (carried over from `~/dotfiles-old`; a quick sanity check happens inside the secrets-bootstrapping ticket, not a separate fight).
  - Isolation on the bastion means a private mount namespace/tmpfs `$HOME` invisible to other same-uid sessions — not container-grade, not defending against root.
- Use `/grilling` and `/domain-modeling` for ticket sessions unless a ticket's `Type:` says otherwise.

## Decisions so far

(none yet)

## Not yet specified

- Whether the old module/preset/child-toggle concept survives in any form for organizing what gets materialized — depends on the session-inventory and secrets-bootstrapping answers.
- Launch UX: the actual shape of the "short command" (shell function vs. `nix run github:...` vs. an installed wrapper) and whether enabling flake experimental features is a precondition — depends on the package-installation-mechanism and repo-distribution answers.
- How the repo itself gets onto a bastion (fresh clone needing git+auth each session, vendored so `nix run` pulls it directly, or something else) — tangled with secrets bootstrapping (repo auth is itself a credential problem) and launch UX.
- Personal vs. work persona distinction — depends on the module/preset-survival and session-inventory answers.
- Fragment composition (files assembled from multiple modules, e.g. `CLAUDE.md`) — depends on whether the module concept survives at all.

## Out of scope

(none yet)
