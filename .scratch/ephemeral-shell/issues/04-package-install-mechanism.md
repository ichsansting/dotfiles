Type: grilling

## Question

Which Nix invocation should the launcher build on — `nix shell`, `nix profile install`, or `nix develop` — to assemble the package set for the ephemeral shell? Decide based on fit for "launch my shell" (interactive session vs. one-off command vs. dev-environment semantics), and confirm the assumption that the Nix store is safely shared and reusable across different same-uid sessions launching concurrently or sequentially on the same bastion (permissions, garbage collection interaction, concurrent builds).
