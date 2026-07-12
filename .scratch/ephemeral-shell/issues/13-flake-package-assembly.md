# 13 — Flake package assembly

**What to build:** `flake.nix` exposing package sets addressable per bundle name, plus a function that takes a resolved bundle list (from the core materialize module) and runs `nix shell` with exactly that package set, spawning `$SHELL` with them on `PATH`. Stateless — no profile or generation is written to disk.

**Blocked by:** 11 — Core materialize module

**Status:** done

- [x] `flake.nix` defines package derivations/sets addressable per bundle name
- [x] Given the core module's resolved bundle list for a preset, `nix shell` is invoked with exactly those packages assembled
- [x] Invocation is stateless — no profile/generation bookkeeping is left behind after the shell exits
- [x] Demoable: pick a preset with at least one real bundle, land in a shell with that bundle's tools on `PATH`

## Comments

Implemented as `flake.nix` (package assembly) plus `bin/assemble` (the launcher-facing "function," mirroring `bin/isolate`'s CLI shape) and `bin/assemble-demo` (standalone verification).

- Bundle→package mapping is read as data, not hand-authored per bundle in `flake.nix`: each bundle's existing `bundles/<name>/files.json` (the same manifest `pkg/dotfiles/core/materialize.py` reads for its file list) may carry an optional `packages` array of nixpkgs attribute names. `flake.nix` discovers bundle names via `readDir ./bundles` and exposes `packages.<system>.<bundle>` as a `pkgs.buildEnv` of that bundle's packages — so ticket 16's later bundles need zero `flake.nix` changes, only new/edited `files.json` entries.
- `bin/assemble BUNDLE... [-- CMD...]` turns a resolved bundle list into `nix shell <flakedir>#bundle1 <flakedir>#bundle2 ... [--command CMD]`. No manual `buildEnv` merge across bundles is needed — `nix shell` already unions multiple installables' `PATH`s itself. Defaults to spawning `$SHELL` (matches the spec's "spawn `$SHELL` with them on PATH"); an explicit `CMD` after `--` is used instead (needed for the demo's non-interactive check and for ticket 15's eventual wiring). `nix shell` itself guarantees statelessness — no profile/generation is written, confirmed by `nix profile list` showing no new entry after several `bin/assemble` runs, and exit codes pass through untouched (verified: `exit 3` inside `CMD` surfaces as `bin/assemble`'s own exit code).
- Added one minimal **real** bundle/preset pair so this ticket's demo criterion has something real to point at rather than a pytest fixture: `bundles/vcs/files.json` (`packages: ["git"]`, no files yet) and `presets/personal.json` (`bundles: ["vcs"]`). Names match `~/dotfiles-old`'s existing `vcs` module for continuity; ticket 16 (real content migration) will flesh both out with their full file/package lists — this ticket only needed enough real content to prove the mechanism.
- **Verified live in this sandbox**: `nix flake show`/`nix flake check` evaluate cleanly; `nix build .#vcs` fetches and builds a real `git` closure from `cache.nixos.org`; `bin/assemble-demo` resolves `personal` → `["vcs"]` via `load_preset`, runs `bin/assemble vcs -- sh -c 'command -v git'`, and confirms `git`'s store path is on `PATH` inside the assembled shell. A bad bundle name fails loudly with Nix's own "does not provide attribute" error and a nonzero exit, no silent fallback. `flake.lock` is committed (pins `nixpkgs`, per standard Nix/`~/dotfiles-old` practice) — this is unrelated to the spec's "no version pinning" decision, which is about the launcher repo's own `git` ref, not the `nixpkgs` input.
