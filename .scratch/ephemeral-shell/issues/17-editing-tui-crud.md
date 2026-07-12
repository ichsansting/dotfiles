# 17 — Editing TUI: bundle/preset/fragment CRUD + auto-commit/push

**What to build:** `nix run .#edit`, a separate Textual app run against a real, persistent git checkout (never an ephemeral session). Full CRUD over bundles, presets, and fragments, porting `~/dotfiles-old`'s interaction patterns (panels, modals, option lists). Every edit auto-commits (generated message) and auto-pushes immediately — no manual git step, no batching.

**Blocked by:** 11 — Core materialize module

**Status:** done

- [x] Create/rename/delete bundles; add/remove items within a bundle
- [x] Create/delete presets; toggle bundle membership within a preset
- [x] Edit a preset's settings overlay values, set/change its base preset, edit its `exclude_fragments` list
- [x] Create a new fragment (opens `$EDITOR`), edit existing fragment content, reorder (rename the `NN-` prefix), and delete a fragment
- [x] Every edit action auto-commits with a generated message and auto-pushes immediately
- [x] Runs only against a real persistent checkout — never touches or requires an ephemeral session
- [x] Demoable: manage a preset entirely through the TUI with no hand-edited files

## Comments

Implemented as `pkg/dotfiles/core/edit.py` (bundle/preset/fragment CRUD, pure FS mutations returning `EditResult(paths, message)`), `pkg/dotfiles/core/gitops.py` (`commit_and_push` — the single seam every mutating dashboard handler funnels through), a `pkg/dotfiles/core/secrets.py` addition (`encrypt_secret`/`shred_file`, for brand-new secret items/fragments — needs only the repo's public age recipient from `.sops.yaml`, mirroring `bin/migrate-secrets`'s `--config /dev/null --age <recipient>` technique), and `pkg/dotfiles/tui/` (a new Textual app, `nix run .#edit`).

- **UI shape**: three panels (presets / bundles / fragments, all `Tree` widgets sharing a `PanelTree` base for node-map/expand-collapse) plus a contextual preview pane, porting `dotfiles-old`'s `ModalScreen[T]` + `OptionList` interaction vocabulary via two generic, reused modals — `FormModal` (text entry) and `PickerModal` (single-select) — rather than one bespoke modal per action.
- **Preset bundle model**: no exclude-inherited-bundle mechanism exists in the flat bundle/preset model (only `exclude_fragments` for fragments), so inherited bundles render read-only (dim, `◦ name (inherited)`) and toggling one warns instead of silently adding a redundant explicit entry.
- **Secret items/fragments**: creating a *new* secret item only needs the repo's public age key (sops `--encrypt`), so it's in scope here (`$EDITOR` on a private tmp plaintext → sops-encrypt → shred). Editing an *existing* secret's content needs the private key/passphrase — left to ticket 18 as designed; the TUI explicitly declines with a pointer there.
- **Flake wiring**: `apps.<system>.edit`, mirroring `dotfiles-old`'s `pkgs.python3.withPackages (ps: [ ps.textual ])` + `writeShellApplication` pattern (runtime inputs: `git`/`sops`/`age`), setting `DOTFILES_REPO="$(pwd)"` so the app always runs against the invoking directory's checkout, never a fetched/ephemeral one.
- **Reviewed via `/code-review`** (Standards + Spec axes, parallel sub-agents). Fixed: (1) the three tree widgets' identical `_cursor_data`/expand/collapse/`__init__` boilerplate, extracted into a shared `PanelTree` base; (2) a new fragment's "owner" field was free text, letting a typo silently create a fragment `materialize.py` would never compose into anything — changed to a `PickerModal` constrained to real bundle/preset names; (3) toggling an inherited bundle row silently mutated state with no exclude mechanism behind it — now warns instead; (4) a push failure (after a successful local commit) read like nothing happened — `gitops.GitError`'s message now says the commit landed locally and will retry on the next edit. Not acted on: tuple-tagged `NodeData` over per-kind dataclasses, and `dashboard.py`'s single-file span across git/editor/encrypt/UI concerns — both flagged as judgement calls, not requested by the ticket, and reasonable for a personal-tool TUI at this size.
- **Verified**: `nix flake show`/`nix build` on the `edit` app's derivation (pulls `textual` from the nixpkgs binary cache, builds clean); a real invocation of the built binary against a scratch fixture repo rendered the full 3-panel UI. Full pytest suite (`uv run --with pytest --with textual --with pytest-asyncio pytest`) — 75 passed, 4 skipped (`age`/`sops` unavailable in this sandbox), including headless Pilot smoke tests (`tests/test_tui_smoke.py`) that drive real git commits/pushes against a local bare "origin". `$EDITOR`-invoking actions (`app.suspend()`) aren't exercised by automated tests — Textual's headless Pilot doesn't support process suspension, the same limitation `dotfiles-old`'s own TUI tests worked around by never testing its file-edit action either; those paths were verified manually instead (bundle-item/fragment content creation with a fake `$EDITOR` script, end to end through to the pushed commit).
