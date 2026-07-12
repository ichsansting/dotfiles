Type: research
Status: resolved

## Question

What does the ephemeral launcher need on macOS, and what's actually available? Since the peer-uid threat model is bastion-specific (a personal laptop has no other same-uid users), macOS likely only needs ephemeral cleanup, not the strong isolation Linux/bastion requires — confirm that reasoning, then investigate what mechanisms macOS offers for an isolated or throwaway `$HOME` (sandbox-exec, chroot, plain tmp-dir-as-HOME, or "no isolation needed at all").

Output a summary of viable approaches and their tradeoffs for a follow-up decision ticket.

## Answer

Confirmed: a personal macOS laptop has no same-uid peer, so nothing needs to be hidden from a sibling session — only reliable cleanup on exit matters. Full research: [macos-mechanisms](../research/02-macos-mechanisms.md).

- `sandbox-exec`/Seatbelt: deprecated per Apple's own man page, no supported CLI/headless successor, and the wrong shape of tool anyway (access-restriction, not `$HOME` redirection). Skip it.
- `chroot`: root-only on Darwin (same as Linux), and macOS has no `unshare`-style unprivileged escape hatch to fake root first. Skip it.
- Linux-style user/mount namespaces: confirmed absent from Darwin/XNU entirely (checked Apple's own `syscalls.master` directly) — the bastion's `unshare -rm` approach has no macOS equivalent, in principle, not just in practice.
- Apple's `container` CLI/Containerization VM framework: real and first-party, but macOS-26 + Apple-Silicon-only, Linux-container-shaped, and a full VM boundary — overkill for this goal.
- **Recommended: plain `mktemp -d` as `$HOME`**, materialize dotfiles/secrets into it same as the bastion path, `trap 'rm -rf "$tmphome"' EXIT INT TERM` for normal/interrupted exits, plus a stale-directory sweep at next launch to catch the inherent `SIGKILL`/crash gap (no trap survives that, on any OS).
