Type: grilling
Status: resolved

## Question

Walk everything `~/dotfiles-old`'s modules track (fish, starship, atuin, zoxide, zellij, git/SSH/gh, helix, mise/direnv, claude-code + `.claude` skills, aws-tools/granted, claude-oauth secrets, work secrets) and classify each item: must be decrypted/rebuilt fresh every ephemeral launch, is static config safe to materialize plainly every time, or no longer makes sense under an ephemeral model (e.g. atuin's history sync, since local history is wiped on every exit).

Produce the classified list — this is the input the module-survival and persona-distinction fog will graduate from later.

## Answer

Every item `~/dotfiles-old` tracks classifies into three buckets. Facts below came from `files.json` (`mode: secret`/`plain`), `.sops.yaml`, and each module's `default.nix`; the two items with real ambiguity (atuin, zoxide) were resolved by the user.

**Decrypt fresh every launch (secrets — sops+age, per [secrets-bootstrapping](02-secrets-bootstrapping.md)'s already-locked "never cached" policy):**
- `.ssh/id_ed25519` (vcs/ssh)
- `.config/gh/hosts.yml` (vcs/gh)
- `.claude/.credentials.json` (claude-oauth)
- `.aws/config` (work)
- `.config/fish/conf.d/traveloka-secrets.fish` (work)
- **atuin session/key (new)** — atuin sync only requires a persisted login session; that session/key isn't sops-tracked anywhere in `dotfiles-old` today (grepped `.sops.yaml` and all modules — nothing). It needs to be added to the secrets manifest and bootstrapped via the same decrypt-fresh mechanism as the rest of this list. Exact file(s) — typically a session token + encryption key under atuin's data dir — are an implementation detail for whichever ticket actually builds the secrets manifest, not a design decision.

**Static, safe to materialize plainly every launch:**
- `.claude/CLAUDE.md` fragments, `.claude/settings.json`, `.claude/skills/*/SKILL.md` (devenv/ai), `.omp/agent/*` (work) — tracked plaintext (`mode: plain`) today
- fish (abbrs/plugins), starship (prompt), zellij (multiplexer), mise (tool list/settings), direnv (nix-direnv), helix + language-servers — no `files.json` entry at all; purely `programs.*.settings` that home-manager renders at build time today. *How* an equivalent gets generated without home-manager stays in the package-install-mechanism fog, not resolved here.
- **zoxide** — per-machine directory ranking, no cross-session persistence goal (confirmed by user: "just install it"). No tracked state, same bucket as the declarative-config items above.

**Deferred — not this ticket's call:**
- Everything under `modules/work` (aws-tools, granted, plus the work secrets already listed above) is work-persona-only by construction (gated behind `dotfiles.work.enable`). Which persona(s) an ephemeral launch supports is separate fog ([module-preset-survival](06-module-preset-survival.md) and the persona-distinction fog it feeds).

**No longer makes sense under the ephemeral model:** none. atuin and zoxide were the two candidates the question flagged, and both landed in existing buckets once actual usage was clear — atuin as a secret (persisted login), zoxide as a plain install (no persistence goal in the first place).
