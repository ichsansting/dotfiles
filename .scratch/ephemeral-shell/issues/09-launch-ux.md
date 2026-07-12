Type: grilling
Status: open
Blocked by: 08 (resolved)

## Question

What is the actual shape of the "short command" a user types to drop into the ephemeral shell — a shell function wrapping a longer invocation, `nix run github:...` directly, an installed wrapper script, or something else — and does reaching it require flake experimental features to be pre-enabled on the target machine as a precondition?

Depends on [repo-distribution](08-repo-distribution.md): resolved as a public repo, fetched via `nix run github:ichsansting/dotfiles` directly (no local clone), floating on `main`. Package-install-mechanism is already settled (`nix shell`, see [package-install-mechanism](04-package-install-mechanism.md)) — this ticket is only about the invocation wrapping it.

**Constraint carried from repo-distribution:** the command must not require memorizing/typing a preset name upfront (e.g. not `nix run github:.../#work1` where the user must already know `work1` exists) — the user wants to choose from what's available, not remember it. Whatever shape this command takes needs to present the available presets and let the user pick, rather than baking a preset name into the invocation itself.
