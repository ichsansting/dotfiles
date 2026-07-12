# 15 — End-to-end launch app

**What to build:** The flake's default app — an interactive fzf preset picker that, once a preset is chosen, wires together isolation (ticket 12) to enter an ephemeral `$HOME`, secrets bootstrap (ticket 14) to decrypt secrets into it, the core module's file-write plan (ticket 11) to materialize static/fragment files into it, and package assembly (ticket 13) to drop into `nix shell` with the resolved package set. This is the first ticket that's demoable as a full launch, even against a minimal test preset/bundle/fragment fixture rather than real content.

**Blocked by:** 11 — Core materialize module, 12 — Isolation launcher, 13 — Flake package assembly, 14 — Secrets bootstrap

**Status:** ready-for-agent

- [ ] `nix run` on this flake presents an interactive fzf picker listing available presets
- [ ] Selecting a preset enters an isolated ephemeral `$HOME` (ticket 12)
- [ ] Secrets are decrypted and placed into that `$HOME` (ticket 14)
- [ ] Static and composed-fragment files are materialized into that `$HOME` per the core module's file-write plan (ticket 11)
- [ ] The session drops into `nix shell` with the preset's resolved package set (ticket 13)
- [ ] Demoable end-to-end using at least a minimal test preset/bundle/fragment fixture
- [ ] On exit (normal or Ctrl-C), nothing from the session survives outside the wiped ephemeral `$HOME`
