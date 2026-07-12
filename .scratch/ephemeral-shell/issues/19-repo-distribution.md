# 19 — Repo distribution + launch documentation

**What to build:** Flip the dotfiles repo to public and verify the bare launch and edit commands work fetched fresh from GitHub with no local clone, per the [repo-distribution](08-repo-distribution.md) and [launch-ux](09-launch-ux.md) design decisions. Document the experimental-features fallback for machines without flakes pre-enabled.

**Blocked by:** 16 — Real content migration, 18 — Editing TUI secret editing + preview

**Status:** ready-for-agent

- [ ] Repository visibility is public
- [ ] `nix run github:ichsansting/dotfiles` succeeds from a machine with only Nix installed, no local clone, resolving current `main` HEAD
- [ ] `nix run github:ichsansting/dotfiles#edit` succeeds the same way for the editing app
- [ ] README documents the `nix run --extra-experimental-features 'nix-command flakes' github:ichsansting/dotfiles` fallback for machines without flakes pre-enabled
- [ ] No version pinning is introduced — every invocation resolves current `main`
