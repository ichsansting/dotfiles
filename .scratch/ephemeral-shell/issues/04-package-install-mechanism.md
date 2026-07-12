Type: grilling
Status: resolved

## Question

Which Nix invocation should the launcher build on — `nix shell`, `nix profile install`, or `nix develop` — to assemble the package set for the ephemeral shell? Decide based on fit for "launch my shell" (interactive session vs. one-off command vs. dev-environment semantics), and confirm the assumption that the Nix store is safely shared and reusable across different same-uid sessions launching concurrently or sequentially on the same bastion (permissions, garbage collection interaction, concurrent builds).

## Answer

**`nix shell`** is the invocation the launcher wraps. It's stateless — it realizes the flake's package set and spawns `$SHELL` with them on `PATH`, with nothing written as a tracked "generation." That matches the map's locked no-persistent-deploy-mode decision: every launch is a fresh, throwaway assembly, and there's no profile state left behind to clean up when the ephemeral `$HOME` is wiped.

Rejected alternatives:
- `nix profile install` — generation-based and stateful by design (built to accumulate upgrades/rollbacks over time). That statefulness fights the ephemeral model: every launch would pay installation/bookkeeping cost into a profile that's discarded immediately, for no persistence benefit.
- `nix develop` — built for project devShells (`mkShell`): entering a build/dev environment for a specific package's dependencies, often carrying build env vars (e.g. `NIX_CFLAGS`) meant for compiling that package. Repurposing it for a general personal shell strains a tool meant for a narrower, project-specific job.

**Store-sharing safety confirmed, no follow-up ticket needed.** Nix's store is designed for concurrent, multi-session access: per-path locking serializes concurrent builds of the same derivation, and a running `nix shell` holds a temporary GC root so its paths can't be collected mid-session even under concurrent GC. This holds in both single-user and daemon-mode Nix, same-uid or not — no bastion-specific wrinkle (cron GC, per-uid quota) was flagged as a concern worth its own investigation.
