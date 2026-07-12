Type: grilling
Status: resolved

## Question

Does `~/dotfiles-old`'s module/preset/child-toggle concept (modules with enable/disable children, presets selecting a bundle of modules + settings like `git.name`/`git.email`) survive in any form for organizing what the ephemeral launcher materializes — or does the new flake+script model need a different organizing structure entirely?

Feed in from [session-inventory](03-session-inventory.md): the classified list already sorts items into "decrypt-fresh secrets," "static plain files," and a work-persona-only bucket (aws-tools/granted/work secrets) whose activation is gated behind a toggle (`dotfiles.work.enable`) today. Decide whether that toggle/preset shape carries over, gets replaced by something simpler (e.g. a flat list of secret files + a single script), or something else — this decision is what the persona-distinction fog (personal vs. work) graduates from next.

## Answer

The nested module/children enable-tree does not survive. It replaced by two flat layers:

- **Bundles**: flat named lists of items to materialize (e.g. `vcs`, `claude-oauth`, `work-tools`, `mise-node`) — an item is either in a bundle or it isn't, no per-item enable/disable flags nested inside. Split bundles finer where launch footprint matters (e.g. mise tools split per-language/group, not one monolithic list) so a fast bastion launch can pick a small subset.
- **Presets**: the only activation surface — pick which bundles to include, plus a small settings overlay (`git.name`/`git.email`, which credential/account to decrypt e.g. `claude.account`). Presets can extend a shared base preset and override just the differing settings, so `work1`/`work2` (same tools, different Claude Code account) share one bundle list instead of duplicating it.

Rejected: keeping the module/children shape as-is. It's implemented entirely via home-manager's option system (`lib.mkOption`/`lib.mkEnableOption`/module merging in `lib/module-options.nix`) — gone under the no-home-manager decision, so keeping the shape means hand-rolling an options/merge engine. It's also built for arbitrary combinatorial toggling, when real usage is a handful of known named contexts (personal, work1, work2, bastion) — solving a flexibility problem that doesn't exist here. The one real ergonomic it offered (default-on, opt-out) is covered instead by preset inheritance (extend a base preset's bundle list, add/drop specific bundles).

This is what the personal-vs-work persona-distinction fog graduates from: personas become presets (`personal`, `work1`, `work2`) selecting bundles + a settings overlay, not module toggles.
