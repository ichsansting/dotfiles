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
