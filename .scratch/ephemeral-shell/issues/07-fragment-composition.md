Type: grilling

## Question

Some materialized files today are assembled from pieces contributed by multiple modules rather than owned by one (e.g. `.claude/CLAUDE.md`, per [session-inventory](03-session-inventory.md)'s static-plain bucket). Now that [module-preset-survival](06-module-preset-survival.md) has replaced modules with flat bundles, how does that composition work: does a bundle contribute a fragment that gets concatenated/merged at materialize time, does one bundle just own the whole file per preset, or something else? Decide the mechanism the materializing script uses when a preset's bundle list produces more than one contributor to the same destination file.
