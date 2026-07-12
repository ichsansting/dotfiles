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
- [Classify what `~/dotfiles-old` tracks: decrypt-fresh, static-plain, or no-longer-makes-sense under the ephemeral model](issues/03-session-inventory.md) — full classified list produced; atuin joins the secrets bucket (needs a persisted login session, not previously sops-tracked — new secret to add later), zoxide is a plain install with no persistence goal. Nothing was dropped as no-longer-relevant. Work-persona items (aws-tools/granted/work secrets) bucketed as deferred, feeding [module-preset-survival](issues/06-module-preset-survival.md).
- [Which Nix invocation assembles the package set for the ephemeral shell, and is the shared store safe under concurrent same-uid launches](issues/04-package-install-mechanism.md) — `nix shell` (stateless, matches no-persistent-deploy-mode); `nix profile install` and `nix develop` rejected as stateful/project-scoped respectively. Store concurrency/GC-root safety confirmed standard, no follow-up needed.
- [What the ephemeral launcher needs on macOS, and what's actually available](issues/05-macos-research.md) — confirmed macOS has no same-uid-peer threat (only cleanup matters); Darwin has no namespace facility at all, `sandbox-exec` is deprecated, `chroot` is root-only — plain `mktemp -d` as `$HOME` with a `trap ... EXIT INT TERM` plus a stale-dir sweep at next launch (for the SIGKILL/crash gap) is the recommended macOS path.
- [Does the module/preset/child-toggle concept survive for organizing what the launcher materializes](issues/06-module-preset-survival.md) — nested module/children enable-tree dropped (it only existed via home-manager's option system, gone under no-home-manager); replaced by two flat layers: bundles (flat named item lists, split finer where launch footprint matters, e.g. mise tools per-language) and presets (bundle list + settings overlay, e.g. `git.name`, `claude.account`), with presets able to extend a shared base preset so `work1`/`work2` share one bundle list and only override the differing account. Personas (personal/work1/work2/bastion) are now just named presets.

## Not yet specified

- Launch UX: the actual shape of the "short command" (shell function vs. `nix run github:...` vs. an installed wrapper) and whether enabling flake experimental features is a precondition — package-install-mechanism is settled (`nix shell`); still depends on the repo-distribution answer below.
- How the repo itself gets onto a bastion (fresh clone needing git+auth each session, vendored so `nix run` pulls it directly, or something else) — tangled with secrets bootstrapping (repo auth is itself a credential problem) and launch UX.
- Preset/bundle editing UX — user wants editing presets/bundles to be easy, via a TUI (successor to `~/dotfiles-old`'s Textual TUI) rather than hand-writing files; not yet sharp what that TUI does or how it relates to the flat bundle/preset files from module-preset-survival.

## Out of scope

(none yet)
