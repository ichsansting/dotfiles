Type: grilling
Status: resolved

## Question

Editing presets/bundles should be easy via a TUI (successor to `~/dotfiles-old`'s Textual TUI) rather than hand-writing files directly. Sharpen what that TUI actually does under the flat bundle/preset model from [module-preset-survival](06-module-preset-survival.md) and the fragment layout from [fragment-composition](07-fragment-composition.md) — is it a full editor (create/rename/delete bundles, add/remove items, edit fragments) or a narrower view/toggle surface, does it run inside the ephemeral session or against the repo directly, and how does it relate to (or replace) `dotfiles-old`'s module tree / file list / preset picker screens?

## Answer

A separate flake app, `nix run .#edit` (exposed as `github:ichsansting/dotfiles#edit`), distinct from the launch app from [launch-ux](09-launch-ux.md). It is not part of the ephemeral launcher at all:

- **Editing locus**: runs against a real, persistent git checkout of the dotfiles repo (your laptop, not a bastion session). The ephemeral launcher stays fetch-only (no local clone, per [repo-distribution](08-repo-distribution.md)) and never touches editing. There is nothing to sync back from an ephemeral `$HOME` — it's wiped on exit, so editing can't happen there.
- **Git integration**: every edit auto-commits (generated message) and auto-pushes immediately. No manual `git add`/`commit`/`push` step, and no batching multiple edits into one commit.
- **Bundle/preset scope — full CRUD**: create/rename/delete bundles; add/remove items within a bundle; create/delete presets; toggle bundle membership; edit the settings overlay (`git.name`, `claude.account`, ...); set/change a preset's base preset; edit `exclude_fragments`.
- **Fragment editing — full content + structure**: create a new fragment (opens `$EDITOR`, same pattern as `dotfiles-old`'s file-edit action), edit existing fragment content, reorder (rename the `NN-` prefix), delete, and preview the composed result for a target file.
- **Secret item editing**: closes the gap `dotfiles-old` left open ("editing secret fragments is not supported yet"). The TUI decrypts with the age key into a temp file, opens `$EDITOR`, re-encrypts with sops on save, and shreds the temp plaintext — then auto-commits/pushes the re-encrypted file like any other edit.
- **Preview**: a per-preset dry-run — runs the materialize script's compose logic against a scratch directory (not a real ephemeral `$HOME`) and shows composed fragment output, resolved settings overlay, and package list. Catches fragment-ordering/`exclude_fragments`/settings mistakes before pushing.
- **Tech stack**: kept Python/Textual, porting `dotfiles-old`'s interaction patterns (panels, modals, option lists) rather than rewriting them in something lighter. Home-manager was the thing being dropped, not Python — Textual ships as its own flake app/package, independent of home-manager.

Rejected: a narrower toggle/view-only surface (hand-editing would still be needed for new bundles/presets/inheritance) — full CRUD was preferred since the whole point is not hand-writing files. Rejected leaving secret-fragment editing unsupported (dotfiles-old's punt) — decrypt/edit/re-encrypt was judged worth the sops roundtrip. Rejected switching to a lighter fzf/bash-menu mechanism to match the plain-script ethos elsewhere on this map — that ethos targeted home-manager's option-merging machinery specifically, not Python/Textual as a UI toolkit.
