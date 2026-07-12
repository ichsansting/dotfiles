# 17 — Editing TUI: bundle/preset/fragment CRUD + auto-commit/push

**What to build:** `nix run .#edit`, a separate Textual app run against a real, persistent git checkout (never an ephemeral session). Full CRUD over bundles, presets, and fragments, porting `~/dotfiles-old`'s interaction patterns (panels, modals, option lists). Every edit auto-commits (generated message) and auto-pushes immediately — no manual git step, no batching.

**Blocked by:** 11 — Core materialize module

**Status:** ready-for-agent

- [ ] Create/rename/delete bundles; add/remove items within a bundle
- [ ] Create/delete presets; toggle bundle membership within a preset
- [ ] Edit a preset's settings overlay values, set/change its base preset, edit its `exclude_fragments` list
- [ ] Create a new fragment (opens `$EDITOR`), edit existing fragment content, reorder (rename the `NN-` prefix), and delete a fragment
- [ ] Every edit action auto-commits with a generated message and auto-pushes immediately
- [ ] Runs only against a real persistent checkout — never touches or requires an ephemeral session
- [ ] Demoable: manage a preset entirely through the TUI with no hand-edited files
