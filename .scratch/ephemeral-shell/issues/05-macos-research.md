Type: research

## Question

What does the ephemeral launcher need on macOS, and what's actually available? Since the peer-uid threat model is bastion-specific (a personal laptop has no other same-uid users), macOS likely only needs ephemeral cleanup, not the strong isolation Linux/bastion requires — confirm that reasoning, then investigate what mechanisms macOS offers for an isolated or throwaway `$HOME` (sandbox-exec, chroot, plain tmp-dir-as-HOME, or "no isolation needed at all").

Output a summary of viable approaches and their tradeoffs for a follow-up decision ticket.
