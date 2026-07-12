# 16 — Real bundle/preset/fragment content migration

**What to build:** Port the actual bundles, presets, and fragments from `~/dotfiles-old` into this repo's flat bundle/preset/fragment layout, using the classification already produced during design (see [session-inventory](03-session-inventory.md) and [module-preset-survival](06-module-preset-survival.md)). This is what turns ticket 15's launch app from a toy-fixture demo into a real, usable launcher — including adding atuin's session/key to the secrets manifest, since it wasn't previously sops-tracked anywhere in `~/dotfiles-old`.

**Blocked by:** 15 — End-to-end launch app

**Status:** ready-for-agent

- [ ] Bundles ported: `vcs`, `terminal`, `editor`, `devenv`, `utils`, `env`, `work-tools`, per-language `mise-*` bundles, `claude-oauth`
- [ ] Presets ported: `personal`, `work1`, `work2`, `bastion` — `work1`/`work2` share one bundle list via base-preset inheritance, differing only in the settings overlay (e.g. `claude.account`)
- [ ] Fragments ported (e.g. `.claude/CLAUDE.md` composition across contributing bundles), preserving existing ordering intent
- [ ] atuin's session/key is added to the secrets manifest as a new decrypt-fresh secret
- [ ] Full real `personal` and `work` launches succeed end-to-end via ticket 15's launch app, not just the toy fixture preset
