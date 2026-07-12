Type: grilling

## Question

Does `~/dotfiles-old`'s module/preset/child-toggle concept (modules with enable/disable children, presets selecting a bundle of modules + settings like `git.name`/`git.email`) survive in any form for organizing what the ephemeral launcher materializes — or does the new flake+script model need a different organizing structure entirely?

Feed in from [session-inventory](03-session-inventory.md): the classified list already sorts items into "decrypt-fresh secrets," "static plain files," and a work-persona-only bucket (aws-tools/granted/work secrets) whose activation is gated behind a toggle (`dotfiles.work.enable`) today. Decide whether that toggle/preset shape carries over, gets replaced by something simpler (e.g. a flat list of secret files + a single script), or something else — this decision is what the persona-distinction fog (personal vs. work) graduates from next.
