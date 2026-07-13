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
- Isolation only covers `$HOME` — `TMPDIR` and (on Linux) `XDG_RUNTIME_DIR`
  still point at real, host-shared paths, so tools that write there leak to
  peers and outlive the session. Accepted for now: config/secrets are
  unaffected (they're written inside the isolated `$HOME`), only temp/cache
  leakage is exposed.
- On macOS, a tool that resolves its home directory via `getpwuid()` instead
  of reading `$HOME` bypasses isolation entirely and writes to your real
  home directory — no clean fix without root. A `sandbox-exec` deny-write
  profile on the real home path would turn this into a loud failure instead
  of a silent leak, but isn't implemented yet.
