# 19 — Repo distribution + launch documentation

**What to build:** Flip the dotfiles repo to public and verify the bare launch and edit commands work fetched fresh from GitHub with no local clone, per the [repo-distribution](08-repo-distribution.md) and [launch-ux](09-launch-ux.md) design decisions. Document the experimental-features fallback for machines without flakes pre-enabled.

**Blocked by:** 16 — Real content migration, 18 — Editing TUI secret editing + preview

**Status:** done

- [x] Repository visibility is public
- [x] `nix run github:ichsansting/dotfiles` succeeds from a machine with only Nix installed, no local clone, resolving current `main` HEAD
- [x] `nix run github:ichsansting/dotfiles#edit` succeeds the same way for the editing app
- [x] README documents the `nix run --extra-experimental-features 'nix-command flakes' github:ichsansting/dotfiles` fallback for machines without flakes pre-enabled
- [x] No version pinning is introduced — every invocation resolves current `main`

## Comments

Repo visibility was already public (confirmed via `gh repo view`). The
substantive gap this ticket closed: **tickets 16-18's work (six commits —
real content migration, editing TUI CRUD, secret editing/preview) had only
ever been committed locally, never pushed** — `origin/main` was 6 commits
behind. Since this ticket's job is verifying the bare commands against what
GitHub actually serves, that gap had to close first; pushed after explicit
user confirmation (public repo, visible/hard-to-reverse action).

- **Verification method**: a real interactive TTY is needed to drive `fzf`
  (plain piped stdin hits "inappropriate ioctl for device"), so both apps
  were driven inside a `tmux` session against `github:ichsansting/dotfiles`
  fetched fresh (`--refresh` to bypass the tarball-fetch TTL cache and force
  re-resolution of `main` after the push).
- **`nix run github:ichsansting/dotfiles`**: builds clean, presents the
  interactive preset picker with real content (`bastion`, `personal`,
  `work1`), and correctly hands off into `bin/isolate` on selection.
  `isolate` then fails loud — "unprivileged user namespaces are unavailable
  on this host" — which is this *sandbox's* kernel restriction, not a repo
  defect: it's exactly the documented no-fallback behavior from
  [isolation-mechanism-research](01-isolation-mechanism-research.md) and the
  spec ("fail loudly rather than silently drop isolation"). Verifying past
  that point needs a host with unprivileged userns available (a real bastion
  or laptop), out of reach of this environment.
- **`nix run github:ichsansting/dotfiles#edit`**: builds clean and boots the
  full 3-panel TUI against a real local checkout, showing live preset/bundle/
  fragment content (5 presets, 13 bundles) — confirms the flake resolves,
  fetches, and runs correctly with no local clone of the *launcher* needed
  (only the target repo being edited needs a local checkout, by design).
- **Fallback command**: `nix run --extra-experimental-features 'nix-command
  flakes' github:ichsansting/dotfiles` runs and reaches the same fzf-init
  point as the bare command — confirms the flag is accepted and doesn't
  interfere with resolution. Actually exercising the "flakes disabled"
  failure path isn't testable here without disabling flakes on this machine.
- **No version pinning**: confirmed no `?ref=`/`/rev=` anywhere in
  `flake.nix`, `bin/`, or `pkg/` — every invocation resolves whatever
  `origin/main`'s HEAD is at call time.
- **README.md added** (repo had none) documenting the launch/edit commands
  and the experimental-features fallback.
