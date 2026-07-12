Type: grilling
Status: resolved

## Question

Some materialized files today are assembled from pieces contributed by multiple modules rather than owned by one (e.g. `.claude/CLAUDE.md`, per [session-inventory](03-session-inventory.md)'s static-plain bucket). Now that [module-preset-survival](06-module-preset-survival.md) has replaced modules with flat bundles, how does that composition work: does a bundle contribute a fragment that gets concatenated/merged at materialize time, does one bundle just own the whole file per preset, or something else? Decide the mechanism the materializing script uses when a preset's bundle list produces more than one contributor to the same destination file.

## Answer

Fragments are a plain filesystem convention, not a JSON manifest field — grouped by target file rather than by bundle:

- **Layout**: `fragments/<target-path>.d/<NN>-<owner>.md` (e.g. `fragments/.claude/CLAUDE.md.d/10-devenv.md`, `fragments/.claude/CLAUDE.md.d/50-work.md`). One directory per composed target holds every contributor, so a file's whole composition is visible at a glance.
- **Ordering**: pure filename convention — the `NN` numeric prefix decides order, no `order:` field to maintain elsewhere. Reordering or splitting a fragment is a plain rename/move.
- **Owner**: the suffix after `NN-` is either a bundle name or a preset name — presets can contribute their own fragment directly, through the same directory and mechanism as bundles (no separate "preset fragment" concept).
- **Filtering**: the materialize script keeps a fragment if its owner is a bundle in the active preset's bundle list, or is the active preset itself; everything else in the directory is dropped.
- **Suppression**: a preset's settings overlay can carry `exclude_fragments: [...]` naming specific fragment files to drop even when their owning bundle is otherwise active — covers the case where a preset wants a bundle's tools but not its fragment contribution.
- **Compose**: sort survivors by filename, each block trimmed of trailing newlines, empty blocks dropped, join with a blank line, single trailing newline overall — same join semantics as `dotfiles-old`'s `compose()`, just fed by a directory listing instead of a manifest.
- **No state tracking**: the hash-aware anti-clobber/conflict-detection machinery in `dotfiles-old` (`state.load`/`save`/digest comparison) is dropped entirely, not ported. It existed to protect a *persistent* deploy from user hand-edits; under the ephemeral model `$HOME` is rebuilt fresh every launch and wiped on exit, so there's nothing persistent to protect — materialize just writes.
- **Invariant carried over unchanged**: a target path is either whole-file (exactly one owner) or all-fragments — mixing is still a config error, just checked by the plain script at materialize time instead of by `dotfiles-old`'s Python manifest-validation code.

Rejected: porting `dotfiles-old`'s JSON-manifest-driven fragment engine (`files.json` `fragment`/`order` fields + Python `compose()`/`partition_targets()`) as-is. The ordering and ownership it tracks in a manifest are exactly what a numbered filename already encodes for free, and its anti-clobber logic solves a persistence problem this model doesn't have.
