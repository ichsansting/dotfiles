# 11 — Core materialize module

**What to build:** A pure, stdlib-only Python module that resolves a preset into everything the launcher and editing TUI need to write: the bundle list (with base-preset inheritance applied), the resolved settings overlay, the filtered+composed fragment output, and the final file-write plan (path, content, secret/plain classification). It takes bundle/preset/fragment definitions and already-decrypted secret contents as data — it never invokes Nix, sops, or git itself, and never touches a live filesystem session. This is the spec's primary tested seam; every other ticket calls into it rather than duplicating resolution logic.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Given a directory of bundle/preset/fragment definitions and a preset name, returns the resolved bundle list, including bundles inherited from a base preset
- [x] Settings overlay resolution applies base-preset inheritance, with the child preset's own settings taking precedence over inherited ones
- [x] Fragment filtering keeps a fragment only if its owner (a bundle name or the preset name) is active, and honors a preset's `exclude_fragments` list
- [x] Fragment compose sorts survivors by filename, trims trailing newlines per block, drops empty blocks, joins with a single blank line between blocks, and ends with exactly one trailing newline
- [x] A target path that mixes whole-file ownership and fragment ownership raises a config error before any output is produced for that target
- [x] A fragment target that depends on a secret contributor whose decrypted content isn't available is skipped entirely (not partially written)
- [x] The module has zero runtime dependency on Nix, sops, or git — all external state (decrypted secrets, definition trees) is passed in as data
- [x] Unit tests exercise every behavior above against fixture directories, with no mocking of external tools required

## Comments

Implemented as `pkg/dotfiles/core/materialize.py`, tested by `tests/test_materialize.py` (20 cases, fixture-tree based, no mocking). On-disk schema (not pinned by the spec) chosen for this ticket:

```
presets/<name>.json         {"base": "<name>"?, "bundles": [...], "settings": {...}}
bundles/<name>/files.json   {"files": [{"path": "<home-rel>", "mode": "plain"|"secret"}]}
bundles/<name>/files/<path> plain whole-file content
fragments/<target>.d/<NN>-<owner>.md          plain fragment
fragments/<target>.d/<NN>-<owner>.secret.md   secret fragment
```

`exclude_fragments` lives under a preset's `settings` and names fragment paths relative to `fragments/`. Secret content (whole-file or fragment) is never read from disk — it's supplied by the caller via `decrypted_secrets`, keyed by the whole-file's `$HOME`-relative path or the fragment's path relative to `fragments/`. Ticket 16 (real content migration) should follow this layout, or update this note if it changes it.
