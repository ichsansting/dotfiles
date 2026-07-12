Type: grilling
Status: resolved

## Question

How does the dotfiles repo itself get onto a bastion account so a fresh ephemeral launch can run — a fresh `git clone` needing its own auth every session, something vendored/published so `nix run github:...` (or similar) pulls it directly without a local clone, or some other mechanism?

Feed in from [secrets-bootstrapping](02-secrets-bootstrapping.md): repo auth is itself a credential problem, distinct from the age-key decrypt already settled there — decide whether this needs its own bootstrap step, reuses the same mechanism, or is sidestepped entirely (e.g. a public repo + `nix run` needs no auth at all). This decision also shapes [launch-ux](09-launch-ux.md), which is blocked on it.

## Answer

**The dotfiles repo becomes public.** Nothing inside it is sensitive without its passphrase: `identity.age` is passphrase-encrypted at rest, and per-module secrets are separate sops-encrypted YAML files (per [secrets-bootstrapping](02-secrets-bootstrapping.md)). Going public removes the repo-auth problem entirely rather than solving it with a second credential mechanism.

**Fetch mechanism: `nix run github:ichsansting/dotfiles` directly, no local git clone.** Nix fetches the flake straight into the store per launch. Needs only `nix` on the bastion plus network reachability to GitHub — no `git` dependency, no working tree to clean up as part of teardown.

**No version pinning — floats on `main`.** Every launch resolves to the current HEAD of the default branch, consistent with this repo's trunk-based workflow (small frequent commits, main always working). Rejected pinning to a tag/ref: would need a release/tagging step and manual pin bumps to pick up new changes, solving a reproducibility need nobody asked for.

**Rejected: fresh git clone each session.** Adds a `git` dependency and a clone artifact to the ephemeral-teardown surface for no benefit once the repo is public and `nix run github:...` works directly.

**Note carried to [launch-ux](09-launch-ux.md):** the exact command should not require memorizing/typing a preset name upfront (e.g. not `nix run github:.../#work1` where you must already know `work1` exists) — the user wants to choose from what's available, not remember it. This doesn't change the answer above; it's a constraint on how ticket 09 shapes the invocation.
