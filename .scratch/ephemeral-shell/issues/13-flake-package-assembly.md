# 13 — Flake package assembly

**What to build:** `flake.nix` exposing package sets addressable per bundle name, plus a function that takes a resolved bundle list (from the core materialize module) and runs `nix shell` with exactly that package set, spawning `$SHELL` with them on `PATH`. Stateless — no profile or generation is written to disk.

**Blocked by:** 11 — Core materialize module

**Status:** ready-for-agent

- [ ] `flake.nix` defines package derivations/sets addressable per bundle name
- [ ] Given the core module's resolved bundle list for a preset, `nix shell` is invoked with exactly those packages assembled
- [ ] Invocation is stateless — no profile/generation bookkeeping is left behind after the shell exits
- [ ] Demoable: pick a preset with at least one real bundle, land in a shell with that bundle's tools on `PATH`
