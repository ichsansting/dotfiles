Status: ready-for-agent

# Ephemeral personal-shell launcher

## Problem Statement

The current dotfiles setup (`~/dotfiles-old`) deploys a persistent, home-manager-managed `$HOME`: packages, config, and decrypted secrets are installed once and live on disk until explicitly undeployed. That's the right shape for a personal laptop, but it doesn't fit a shared bastion account reached via AWS SSM — a same-uid peer on that account could read another user's decrypted secrets or leftover config, because nothing about a persistent deploy isolates one session's `$HOME` from another's.

The user wants one launcher that works the same way everywhere — laptop or bastion — dropping them into their full personal shell (packages, dotfiles, secrets) without leaving anything behind that a peer session, or the next login, could see.

## Solution

A short command (`nix run github:ichsansting/dotfiles`), runnable anywhere Nix is already installed, builds and drops the user into their full personal shell inside a throwaway `$HOME` assembled fresh on every launch. On a shared bastion, that `$HOME` sits behind a private mount namespace invisible to other same-uid sessions; on a personal machine (no peer-uid threat), it's a plain temp directory. Either way, the whole session — config, decrypted secrets, isolation boundary — is wiped on exit; only the shared Nix store persists on the machine, so the next launch is fast.

There is no persistent-deploy mode anywhere, including on the user's own laptop, and no home-manager: a Nix flake defines the package sets, and a plain script (not a declarative home-manager module tree) materializes dotfiles and decrypts secrets into the ephemeral `$HOME` on every launch.

A separate, non-ephemeral editing app (`nix run .#edit`) lets the user manage presets/bundles/fragments/secrets against a real persistent git checkout, so the launcher itself never needs write access back to the repo.

## User Stories

1. As a user with Nix installed on my own laptop, I want to run one short command, so that I land in my full personal shell without a persistent install step.
2. As a user on a shared bastion account (AWS SSM), I want my ephemeral `$HOME` hidden from other same-uid sessions on that account, so that a peer sharing the account can't read my decrypted secrets or session config.
3. As a user on a shared bastion, I want the launcher to fail loudly rather than silently drop isolation, so that I never end up in an unknowingly-exposed session.
4. As a user, I want the shared Nix store to persist across launches on the same machine, so that repeat launches are fast even though nothing else persists.
5. As a user, I want my age private key never written to a persistent location, so that a stolen or inspected disk on a shared machine never yields my decryption capability.
6. As a user, I want to type my age-key passphrase once per launch, so that a peer session can never piggyback on a cached decryption capability I've left running.
7. As a user, I want the launcher's isolation boundary and everything inside it wiped on exit — normal exit, Ctrl-C, or crash — so that nothing about my session survives to be read later.
8. As a user, I want a stale-directory sweep on next launch, so that a `SIGKILL`'d or crashed prior session's leftover temp `$HOME` still gets cleaned up eventually.
9. As a user on macOS, I want the same launch command to work, so that I don't need a different mental model per platform.
10. As a user, I want my static config (fish, starship, zellij, mise, direnv, helix, Claude Code settings/skills) materialized the same way every launch, so that my shell always looks and behaves the same regardless of machine.
11. As a user, I want my secrets (SSH key, GitHub CLI auth, Claude Code OAuth credentials, AWS config, work-specific secrets, atuin session) decrypted fresh into the ephemeral `$HOME` on every launch and never cached outside it, so that no persistent copy of any secret exists on a shared machine.
12. As a user, I want to pick which named context (personal, work1, work2, bastion, ...) I'm launching into via an interactive picker, so that I don't have to memorize or type a preset name upfront.
13. As a user, I want `work1` and `work2` presets to share one bundle list and differ only in the overridden Claude Code account, so that I don't maintain two near-duplicate preset definitions.
14. As a user, I want to compose a file like `.claude/CLAUDE.md` from multiple contributing bundles' fragments, so that shared base content and context-specific additions (e.g. work-only instructions) combine into one file without me hand-merging them.
15. As a user, I want a preset to be able to suppress one bundle's fragment contribution to a composed file while still using that bundle's tools, so that I can opt out of a specific piece of injected config without dropping the whole bundle.
16. As a user, I want the launcher to refuse to start (rather than deploy a half-composed file) if a fragment target is missing the age key needed to decrypt one of its secret contributors, so that I never end up with silently-incomplete config.
17. As a user, I want mise tool sets split finer than one monolithic list (e.g. per language), so that a fast bastion launch can pick just the tools it needs instead of installing everything.
18. As a user, I want to fetch and run the launcher directly from a public GitHub repo (`nix run github:ichsansting/dotfiles`) with no local git clone, so that there's no clone artifact to manage as part of teardown.
19. As a user, I want the launcher to always run the current `main` branch with no version pinning, so that I always get the latest state consistent with this repo's trunk-based workflow.
20. As a user, I want a documented fallback command (`--extra-experimental-features 'nix-command flakes'`) for machines where flakes aren't pre-enabled, so that I have a next step when the bare command fails with Nix's own error.
21. As a developer of this repo, I want a full-CRUD Textual TUI (`nix run .#edit`) for bundles, presets, fragments, and secret items, so that I never hand-edit the underlying files or manifests directly.
22. As a developer of this repo, I want the editing TUI to auto-commit and auto-push every edit immediately, so that I never forget a manual git step and the repo (which the launcher fetches live) is always current.
23. As a developer of this repo, I want to decrypt, edit, and re-encrypt a secret fragment/file directly from the editing TUI (with the plaintext temp file shredded after use), so that editing secrets no longer requires manual sops roundtrips outside the tool.
24. As a developer of this repo, I want a per-preset materialize dry-run preview in the editing TUI (composed fragment output, resolved settings overlay, package list) against a scratch directory, so that I catch fragment-ordering, `exclude_fragments`, or settings mistakes before pushing.
25. As a developer of this repo, I want the preset/bundle/fragment resolution logic (bundle list + settings overlay + fragment compose + file-write plan) implemented as one pure, stdlib-only core module, so that it's unit-testable without invoking Nix, sops, or a real filesystem session.
26. As a developer of this repo, I want the launcher's isolation setup (unshare/mktemp) and the editing TUI to stay thin wrappers around that core module, so that the bulk of the logic lives in one testable place rather than being duplicated or entangled with shell/UI concerns.
27. As a developer of this repo, I want the isolation mechanism to try `unshare -rm` first and use `bwrap` only as an optional upgrade if already present, so that the launcher has zero new required dependency beyond `util-linux`.
28. As a developer of this repo, I want the Nix invocation for package assembly to be `nix shell` (not `nix profile install` or `nix develop`), so that no generation state or project-devShell semantics leak into a throwaway session.

## Implementation Decisions

**Isolation (Linux/bastion):**
- Build on `unshare -rm` (util-linux) creating a private user + mount namespace, then manually bind/tmpfs-mount an isolated `$HOME` inside it. No new required dependency.
- Treat `bwrap` as an optional upgrade path only, used if already present on the target — not a dependency the launcher installs.
- Probe unprivileged userns availability (`unshare --user --map-root-user --mount` succeeding) before proceeding; **fail loudly** if the probe fails. There is no permission-based fallback to an unisolated `$HOME`, because same-uid sharing means an unisolated session is exactly the threat being defended against.
- Root is trusted and out of scope for this threat model; only same-uid peer sessions on the shared bastion account are defended against.
- Actual distro/AppArmor posture (`kernel.unprivileged_userns_clone`, `kernel.apparmor_restrict_unprivileged_userns`) on the real target bastion is unverified by this spec — confirm at deployment time using the probe commands captured in `research/01-isolation-mechanisms.md`.

**Isolation (macOS):**
- No namespace facility exists on Darwin/XNU; `sandbox-exec` is deprecated with no headless successor; `chroot` is root-only; Apple's `container`/Containerization VM framework is macOS-26+/Apple-Silicon-only and the wrong shape (full VM boundary).
- Use plain `mktemp -d` as `$HOME`, with `trap '...' EXIT INT TERM` removing it on normal exit, Ctrl-C, or terminate signal.
- Because no trap survives `SIGKILL` or a hard crash, perform a stale-directory sweep at the start of the next launch to catch abandoned temp dirs from a prior session.
- macOS has no same-uid-peer threat model (a personal laptop has no other same-uid users) — cleanup reliability is the only concern, not isolation from a peer.

**Secrets bootstrapping:**
- sops+age remains the encryption mechanism, unchanged from `~/dotfiles-old`.
- `identity.age` (the age keypair, passphrase-encrypted) stays committed in the repo.
- On every launch, after entering the isolated `$HOME`, the launcher runs `age --decrypt` with an interactively-typed passphrase, writing the decrypted key to `~/.config/sops/age/keys.txt` inside the fresh isolated `$HOME` only — never a persistent location, never cached outside the session, never a caching daemon or agent.
- Per-module secrets decrypt via `sops --decrypt --extract` with `SOPS_AGE_KEY_FILE` pointed at that path.
- The passphrase is retyped on every launch, including frequent same-day relaunches — an accepted cost in exchange for never holding a standing decryption capability that a peer session could reach.

**What gets materialized (classification, carried into the bundle model below):**
- **Decrypt-fresh secrets:** SSH key, GitHub CLI auth (`gh`), Claude Code OAuth credentials, AWS config, a work-specific fish secrets file, and atuin's session/login credential (newly identified — not previously sops-tracked in `~/dotfiles-old`; must be added to the secrets manifest).
- **Static plaintext, materialized every launch:** Claude Code `CLAUDE.md` fragments/settings/skills, fish config, starship, zellij, mise tool lists/settings, direnv, helix + language servers, zoxide (installed with no persisted state — no cross-session ranking goal).
- **Work-persona-only:** aws-tools, granted, and the work secrets above — gated by which preset(s) include the relevant bundle(s), not by a module toggle.
- No item was found to no longer make sense under the ephemeral model.

**Package installation:**
- `nix shell` is the invocation the launcher wraps to assemble a preset's package set and spawn `$SHELL` with it on `PATH`. Stateless, no generation/profile bookkeeping left behind.
- Rejected: `nix profile install` (stateful, generation-based — fights the throwaway-every-launch model) and `nix develop` (devShell semantics meant for a specific package's build environment, not a general personal shell).
- The Nix store is safely shared across concurrent/sequential same-uid sessions: per-path locking serializes concurrent builds, and a running `nix shell` holds a temporary GC root protecting its paths mid-session. No bastion-specific store wrinkle identified.

**Organizing structure (replaces `~/dotfiles-old`'s nested module/children tree):**
- **Bundles**: flat named lists of items to materialize (e.g. `vcs`, `claude-oauth`, `work-tools`, per-language `mise-*` bundles). An item is either in a bundle or not — no nested per-item enable flags. Split bundles finer where launch footprint matters, so a fast bastion launch can select a small subset.
- **Presets**: the only activation surface. A preset selects a list of bundles plus a settings overlay (e.g. `git.name`, `git.email`, `claude.account`). A preset may extend a base preset and override just the differing settings/bundles — e.g. `work1`/`work2` share one bundle list and differ only in `claude.account`.
- Named personas (personal, work1, work2, bastion, ...) are presets — there is no separate persona concept.
- The nested module/children enable-tree from `~/dotfiles-old` is dropped entirely; it existed only via home-manager's option-merging system, which this design does not use.

**Fragment composition (for files with more than one contributor, e.g. `.claude/CLAUDE.md`):**
- Filesystem-convention layout: `fragments/<target-path>.d/<NN>-<owner>.md`, one directory per composed target file, holding every potential contributor.
- Ordering is the `NN` numeric filename prefix — no separate manifest `order` field.
- `<owner>` is either a bundle name or a preset name; a preset may contribute its own fragment directly through the same mechanism as a bundle.
- At materialize time, a fragment survives filtering if its owner is a bundle in the active preset's bundle list, or is the active preset itself.
- A preset's settings overlay may carry `exclude_fragments: [...]` naming specific fragment files to drop even when their owning bundle is otherwise active.
- Compose by sorting surviving fragments by filename, trimming trailing newlines per block, dropping empty blocks, joining with one blank line between blocks, single trailing newline overall.
- Invariant: a target path is either whole-file (exactly one owner) or all-fragments (composed) — mixing the two is a config error caught by the materialize script before anything is written.
- If a fragment target's composition depends on a secret contributor and the age key needed to decrypt it isn't available, skip writing that whole target rather than deploying it half-built.
- `~/dotfiles-old`'s JSON-manifest-driven fragment engine (`files.json` `fragment`/`order` fields, hash-aware anti-clobber/state tracking) is dropped entirely — nothing persists across an ephemeral launch to protect, so the anti-clobber machinery has no job left to do.

**Repo distribution:**
- The dotfiles repo is public. Nothing inside it is sensitive without the age passphrase (`identity.age` is passphrase-encrypted; per-module secrets are separately sops-encrypted).
- Fetched via `nix run github:ichsansting/dotfiles` directly — no local `git clone`, no `git` runtime dependency for the launcher.
- No version pinning: every launch resolves the current `main` HEAD.

**Launch UX:**
- The command is exactly `nix run github:ichsansting/dotfiles` — no wrapper shell function, no installed script, no arguments, no `#preset` selector.
- Nix's experimental-features precondition (`nix-command`, `flakes`) is assumed pre-enabled on the target and is not defensively checked at runtime — if unmet, `nix run` fails with Nix's own error before the flake evaluates. The fallback invocation (`nix run --extra-experimental-features 'nix-command flakes' github:ichsansting/dotfiles`) is documented (README/onboarding), not runtime-detected or auto-retried.
- Preset selection happens inside the flake's default app: an interactive fzf picker lists the available presets and the chosen one drives the rest of the launch (isolation setup → secrets decrypt → materialize → `nix shell` into the resolved package set). fzf is a build input of this app, distinct from the per-preset packages `nix shell` assembles afterward.

**Editing app (`nix run .#edit`, exposed as `github:ichsansting/dotfiles#edit`):**
- A separate flake app from the launcher, run against a real persistent git checkout — never touches an ephemeral session, since there's nothing to sync back from a `$HOME` that's wiped on exit.
- Every edit auto-commits (generated message) and auto-pushes immediately — no manual git step, no batching.
- Full CRUD scope: create/rename/delete bundles; add/remove items within a bundle; create/delete presets; toggle bundle membership; edit settings overlay values; set/change a preset's base preset; edit `exclude_fragments`.
- Full fragment editing: create (opens `$EDITOR`), edit content, reorder (rename the `NN-` prefix), delete, and preview the composed result for a target file.
- Secret item editing: decrypt with the age key into a temp file, open `$EDITOR`, re-encrypt with sops on save, shred the temp plaintext, then auto-commit/push the re-encrypted file like any other edit.
- Preview: a per-preset dry-run that runs the materialize core module's compose logic against a scratch directory (not a real ephemeral `$HOME`) and shows composed fragment output, resolved settings overlay, and resolved package list.
- Tech stack: Python + Textual, porting `~/dotfiles-old`'s interaction patterns (panels, modals, option lists). Textual ships as its own flake app/package — home-manager is what's dropped, not Python/Textual.

**Core module boundary (see Testing Decisions):**
- A single pure, stdlib-only "materialize core" module resolves: preset → bundle list, settings overlay (with base-preset inheritance applied), fragment filtering + compose, and the final file-write plan (paths + content + secret/plain classification). It takes filesystem/decrypted-secret inputs as data, not by reaching out to Nix/sops/git itself.
- The launcher shell script (isolation setup, age/sops invocation, `nix shell` invocation) and the editing TUI (Textual UI, git auto-commit/push, `$EDITOR` invocation) are both thin callers of this core module — they own I/O and side effects, the core module owns resolution logic.

## Testing Decisions

- **Primary tested seam: the materialize core module.** A good test here exercises resolution behavior through its public inputs/outputs only — given a preset name, a bundle/preset/fragment directory tree, and a set of already-decrypted secret file contents, assert on the resulting bundle list, resolved settings overlay, composed fragment content, and file-write plan. No mocking of Nix, sops, git, or a real filesystem session beyond fixture directories.
  - Cover: base-preset inheritance and override precedence; bundle-membership fragment filtering; `exclude_fragments` suppression; fragment ordering and compose join semantics (trimmed blocks, blank-line join, single trailing newline); the whole-file-vs-all-fragments mixing error; the skip-target-on-missing-age-key behavior.
  - Prior art: `~/dotfiles-old`'s `pkg/dotfiles/core/` (stdlib-only logic for profiles/manifests/sops/age) tested with plain pytest units, e.g. `tests/test_profile.py`, `tests/test_fragments.py`, `tests/test_manifest.py` — same shape of test, updated for the new bundle/preset/fragment model in place of the old module/children/manifest one.
- **Smoke-level only: the launcher shell script and the editing TUI.** These are thin wrappers around the core module's decisions above and don't need deep independent test coverage.
  - Launcher: a smoke test that the isolation probe/fallback path and `nix shell` invocation wire together correctly end-to-end where feasible in CI (e.g. isolation-mechanism probe succeeds/fails as expected; macOS `mktemp -d` + trap cleanup removes its directory). Full bastion-specific behavior (actual AppArmor/sysctl posture) is out of reach of automated tests and stays a manual verification step at deployment.
  - Editing TUI: headless Textual `Pilot` smoke tests, same pattern as `~/dotfiles-old`'s `tests/test_tui_smoke.py` — enough to confirm screens load and core actions (toggle, edit, preview) don't crash, not exhaustive interaction coverage.
- Do not re-test Nix's own guarantees (store locking, GC-root protection, concurrent build safety) — those were confirmed as standard Nix behavior during design (see [package-install-mechanism](issues/04-package-install-mechanism.md)) and don't need project-level tests.

## Out of Scope

- Any persistent-deploy mode, on the bastion or the user's own laptop — every launch rebuilds into a throwaway `$HOME`, with no exception.
- home-manager, or any declarative option-merging system replacing it — the flake + plain script model replaces that role entirely.
- Defending against a hostile root user on the shared bastion — root is trusted in this threat model.
- A caching/agent mechanism for the age-key passphrase (e.g. an ssh-agent-style helper) — rejected because any socket persisting outside the per-launch isolation boundary is reachable by other same-uid peers.
- A remote vault/secrets-manager fetch mechanism for the age key — rejected as an unneeded second bootstrapping-trust problem.
- Version-pinning the launched repo to a tag/ref — the launcher always floats on `main`.
- A `--preset` non-interactive bypass flag for the launch command — rejected to keep launch interactive-only and avoid a side door around picking a preset by name.
- Runtime detection or auto-retry of Nix's experimental-features precondition — documented as a manual fallback only.
- Container/VM-based isolation on macOS (Apple's `container`/Containerization framework) — overkill relative to the plain-`mktemp`-plus-cleanup approach chosen.

## Further Notes

- This spec's decisions were produced by a wayfinder map (`.scratch/ephemeral-shell/map.md`) with ten resolved tickets; each Implementation Decision above traces to one of those tickets, linked inline in the Testing Decisions references and listed in the map's Decisions-so-far for full context and rejected alternatives.
- Two research artifacts back the isolation decisions: `research/01-isolation-mechanisms.md` (Linux/bastion userns probing, with copy-paste probe commands to run on the actual target) and `research/02-macos-mechanisms.md` (macOS mechanism survey).
- One open verification step is explicitly *not* resolved by this spec: the actual bastion's distro/AppArmor posture for unprivileged user namespaces. This should be checked with the probe commands in `research/01-isolation-mechanisms.md` before or during implementation, since a blocked probe means the loud-failure path (not a silent fallback) is what a real user will hit.
- atuin's session/key needs to be added to the secrets manifest as part of implementation — it was identified as a gap during design (see [session-inventory](issues/03-session-inventory.md)) but the exact file(s) to track are an implementation detail, not resolved here.
