# 12 — Isolation launcher

**What to build:** A standalone entry point that produces an ephemeral, isolated `$HOME` and guarantees its cleanup. On Linux, this means probing unprivileged user-namespace availability, then building a private mount namespace with a tmpfs `$HOME` via `unshare -rm` (with `bwrap` used opportunistically if already present, never as a hard dependency) — failing loudly, never silently degrading, if the probe fails. On macOS, this means a plain `mktemp -d` `$HOME` with trap-based cleanup on normal/interrupted exit, plus a stale-directory sweep at the start of the next launch to catch the `SIGKILL`/crash gap. This component is independently verifiable — it doesn't need the materialize module, secrets, or package assembly to demonstrate isolation and cleanup.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] Linux: probes unprivileged user-namespace availability before proceeding
- [ ] Linux: on probe success, creates a private mount namespace with an isolated `$HOME` (`unshare -rm` + bind/tmpfs mount) invisible to a peer same-uid session's filesystem view
- [ ] Linux: on probe failure, fails loudly with a clear error — never falls back to an unisolated `$HOME`
- [ ] Linux: uses `bwrap` instead of raw `unshare` when already present on the target, without adding it as a required dependency
- [ ] macOS: creates `$HOME` via `mktemp -d`
- [ ] macOS: registers a trap on `EXIT INT TERM` that removes the temp `$HOME` on normal exit, Ctrl-C, and terminate signal
- [ ] macOS: sweeps stale leftover temp directories from a prior crashed/`SIGKILL`ed session at the start of the next launch
- [ ] A standalone test/demo enters the isolated `$HOME`, writes a marker file, and verifies peer-invisibility (Linux) or cleanup (macOS) independent of any other ticket
