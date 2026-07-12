# 11 — Core materialize module

**What to build:** A pure, stdlib-only Python module that resolves a preset into everything the launcher and editing TUI need to write: the bundle list (with base-preset inheritance applied), the resolved settings overlay, the filtered+composed fragment output, and the final file-write plan (path, content, secret/plain classification). It takes bundle/preset/fragment definitions and already-decrypted secret contents as data — it never invokes Nix, sops, or git itself, and never touches a live filesystem session. This is the spec's primary tested seam; every other ticket calls into it rather than duplicating resolution logic.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Given a directory of bundle/preset/fragment definitions and a preset name, returns the resolved bundle list, including bundles inherited from a base preset
- [ ] Settings overlay resolution applies base-preset inheritance, with the child preset's own settings taking precedence over inherited ones
- [ ] Fragment filtering keeps a fragment only if its owner (a bundle name or the preset name) is active, and honors a preset's `exclude_fragments` list
- [ ] Fragment compose sorts survivors by filename, trims trailing newlines per block, drops empty blocks, joins with a single blank line between blocks, and ends with exactly one trailing newline
- [ ] A target path that mixes whole-file ownership and fragment ownership raises a config error before any output is produced for that target
- [ ] A fragment target that depends on a secret contributor whose decrypted content isn't available is skipped entirely (not partially written)
- [ ] The module has zero runtime dependency on Nix, sops, or git — all external state (decrypted secrets, definition trees) is passed in as data
- [ ] Unit tests exercise every behavior above against fixture directories, with no mocking of external tools required
