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

- ["What mechanisms are actually available to get a private mount namespace / isolated tmpfs $HOME as an unprivileged same-uid user"](issues/01-isolation-mechanism-research.md) — isolation builds on `unshare -rm` + manual bind/tmpfs mount (no extra dependency); `bwrap` is an optional upgrade only; fail loudly if the unprivileged-userns probe fails, since same-uid sharing means there's no permission-based fallback. Actual bastion distro/AppArmor posture is still unchecked — see linked research for probe commands.
- [How the age private key gets into an ephemeral session without persisting in plaintext](issues/02-secrets-bootstrapping.md) — sops+age confirmed unchanged; reuse `~/dotfiles-old`'s `identity.age` + interactive-passphrase decrypt as-is, run fresh into the isolated tmpfs `$HOME` on every launch (never cached). A caching agent was rejected: any socket outside the per-launch isolation boundary would be reachable by other same-uid peers on the bastion, undermining ticket 01's isolation. Passphrase-per-launch friction is accepted as the cost.

## Not yet specified

- Whether the old module/preset/child-toggle concept survives in any form for organizing what gets materialized — depends on the session-inventory and secrets-bootstrapping answers.
- Launch UX: the actual shape of the "short command" (shell function vs. `nix run github:...` vs. an installed wrapper) and whether enabling flake experimental features is a precondition — depends on the package-installation-mechanism and repo-distribution answers.
- How the repo itself gets onto a bastion (fresh clone needing git+auth each session, vendored so `nix run` pulls it directly, or something else) — tangled with secrets bootstrapping (repo auth is itself a credential problem) and launch UX.
- Personal vs. work persona distinction — depends on the module/preset-survival and session-inventory answers.
- Fragment composition (files assembled from multiple modules, e.g. `CLAUDE.md`) — depends on whether the module concept survives at all.

## Out of scope

(none yet)
