Type: grilling
Status: resolved
Blocked by: 08 (resolved)

## Question

What is the actual shape of the "short command" a user types to drop into the ephemeral shell — a shell function wrapping a longer invocation, `nix run github:...` directly, an installed wrapper script, or something else — and does reaching it require flake experimental features to be pre-enabled on the target machine as a precondition?

Depends on [repo-distribution](08-repo-distribution.md): resolved as a public repo, fetched via `nix run github:ichsansting/dotfiles` directly (no local clone), floating on `main`. Package-install-mechanism is already settled (`nix shell`, see [package-install-mechanism](04-package-install-mechanism.md)) — this ticket is only about the invocation wrapping it.

**Constraint carried from repo-distribution:** the command must not require memorizing/typing a preset name upfront (e.g. not `nix run github:.../#work1` where the user must already know `work1` exists) — the user wants to choose from what's available, not remember it. Whatever shape this command takes needs to present the available presets and let the user pick, rather than baking a preset name into the invocation itself.

## Answer

The command is the bare invocation from repo-distribution, unchanged and un-wrapped: **`nix run github:ichsansting/dotfiles`**. No shell function, no installed wrapper, no args, no `#preset` selector — repeat/scripted use was considered (a `--preset` bypass flag) and explicitly rejected to keep this interactive-only and avoid reintroducing the "must know a preset name" constraint through a side door.

**Experimental features precondition:** assumed pre-enabled on the target, not defensively flagged. If `nix-command`/`flakes` aren't enabled, `nix run` fails with Nix's own error before any of the flake's code ever runs — there's no way for our script to intercept that and print a custom message, since Nix refuses before evaluating the flake at all. The fallback (`nix run --extra-experimental-features 'nix-command flakes' github:ichsansting/dotfiles`) is therefore a **documentation** note (README/onboarding), not a runtime-detected suggestion. Determinate Nix (this laptop) ships flakes enabled by default via `/etc/nix/nix.conf`; a vanilla/official Nix install or the bastion's actual config is not assumed to.

**Preset selection:** happens *inside* the flake's default app, not via invocation args. `nix run` resolves and executes a script (the app) that presents an **interactive fzf picker** over the available presets (personal/work1/work2/bastion/...) and drops into the one the user selects. This makes fzf a build input of the app itself — a separate package surface from the per-preset bundle packages that `nix shell` (settled in [package-install-mechanism](04-package-install-mechanism.md)) assembles once a preset is chosen.
