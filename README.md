# dotfiles

Ephemeral personal-shell launcher. One command builds a throwaway `$HOME`
(packages, dotfiles, decrypted secrets) and drops you into it; everything is
wiped on exit. No persistent install, no home-manager. See
`.scratch/ephemeral-shell/spec.md` for the full design.

## Launch

```
nix run github:ichsansting/dotfiles
```

Picks an interactive preset (personal, work1, bastion, ...) via `fzf`, then
drops you into that persona's shell. Always resolves the current `main`
HEAD — no version pinning, no local clone required.

## Edit

```
nix run github:ichsansting/dotfiles#edit
```

CRUD TUI for bundles/presets/fragments/secrets. Run from inside a real,
persistent clone of this repo (it edits and auto-commits/pushes against
your checkout's working directory) — never against an ephemeral session.

## Flakes not enabled?

If `nix run` fails because `nix-command`/`flakes` aren't enabled on the
target machine:

```
nix run --extra-experimental-features 'nix-command flakes' github:ichsansting/dotfiles
```

## What you still need to do

- **Run `bin/migrate-secrets ~/dotfiles-old` locally.** The `identity.age`
  committed here is still the ticket-15 demo fixture (passphrase
  `ephemeral-shell-demo-fixture`), not your real one — your old
  `dotfiles-old` passphrase won't decrypt it until you run this. It needs a
  real terminal (types your real passphrase, never passed through an
  agent). It migrates your ssh key, `gh` hosts, AWS config, the Traveloka
  fish secrets, and Claude credentials into this repo's format, captures
  atuin's session/key (new — never tracked before), and swaps in the real
  `identity.age`. Review `git status`/`git diff --stat` after, then commit
  and push.

## Known gaps (not ported from dotfiles-old)

- `work2` preset doesn't exist yet — only one real work account exists
  today. `work1` is based on the shared `devbase` preset so a future
  `work2` can extend it without duplicating the bundle list.
- `git config`'s `allowedSignersFile` isn't auto-derived from `id_ed25519`
  at launch — populate it by hand if you need `git verify-commit`.
- nix-direnv isn't wired into `.config/direnv/direnvrc` — `use flake`/
  `use nix` work but without eval caching.
- fish's "done" notification plugin isn't ported (needs a plugin manager)
  — no desktop notification when a long command finishes.
- Isolation needs unprivileged user namespaces on the host; if unavailable,
  launch fails loudly by design, not silently — needs a real machine or
  bastion account, not a restricted sandbox.
