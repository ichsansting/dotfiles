# macOS mechanisms for an ephemeral/throwaway $HOME

Type: research
Answers: `.scratch/ephemeral-shell/issues/05-macos-research.md`

## Threat model recap

The bastion threat model (research 01) is same-uid **peer** sessions on a
shared login account reached via AWS SSM: another person, logged in as the
same Unix user, whose mount/filesystem view must not reveal this session's
ephemeral `$HOME`. Root is trusted, not defended against.

On a personal macOS laptop there is no equivalent peer: the account is used
by one person, and nobody else logs into that same UID over a network. The
map's working assumption — "macOS likely only needs ephemeral cleanup, not
the strong isolation Linux/bastion requires" — is **confirmed**. There is no
DAC-can't-help/namespace-required argument to make here, because there is no
second actor to hide from in the first place. (Other processes *you* run
under your own UID can always read your own `$HOME` regardless of OS — that's
true on Linux too, and is a separate, broader "arbitrary local malware"
problem the bastion threat model explicitly doesn't cover either.) The only
real requirement left is: materialize a throwaway `$HOME`, and make sure it's
gone afterward, including when the script is killed or the machine crashes
mid-session — not "hide it from a sibling while it's running."

## 1. `sandbox-exec` / Seatbelt

- Apple's own man page for `sandbox-exec(1)` marks it **DEPRECATED** in the
  document header itself (BSD General Commands Manual, last revised March 9,
  2017): "sandbox-exec ... DEPRECATED ... Developers who wish to sandbox an
  app should instead adopt the App Sandbox feature described in the App
  Sandbox Design Guide."
  Source: [sandbox-exec(1), Mojave man page mirror](https://www.unix.com/man-page/mojave/1/SANDBOX-EXEC/)
- Running it at all now prints a runtime warning to the same effect:
  "WARNING: sandbox-exec is deprecated. Consider adopting the App Sandbox
  instead." Still executes despite the warning — it hasn't been removed, just
  discouraged, and Apple has never published a CLI/headless-process successor
  API (App Sandbox requires Xcode code-signing entitlements and targets
  Mac-App-Store GUI apps, not a plain shell script).
  Source: [jmmv.dev: A quick glance at macOS' sandbox-exec](https://jmmv.dev/2019/11/macos-sandbox-exec.html); confirmed by an open Apple-adjacent issue asking Apple to clarify the deprecation timeline and provide *any* supported non-GUI replacement, still unresolved: [apple/containerization#737](https://github.com/apple/containerization/issues/737)
- Even setting deprecation aside, Seatbelt is the wrong *shape* of tool for
  this job: it's a MAC (mandatory access control) policy that allow/denies a
  running process's syscalls against paths — it restricts what an existing
  process can touch, it does not substitute or redirect `$HOME` to a
  different, fresh directory the way a namespace/bind-mount does on Linux.
  Using it here would mean layering a deprecated access-restriction feature
  on top of a `$HOME` that's still the real one, for no benefit given there's
  no peer to restrict against.

**Verdict**: available, not removed, but deprecated with no CLI successor and
solves a different problem than "give me a fresh throwaway `$HOME`." Skip it.

## 2. `chroot` on macOS

- Darwin's `chroot(2)` man page: "This call is restricted to the
  super-user." No unprivileged path exists at all — same restriction as
  Linux's `chroot(2)`.
  Source: [chroot(2), Darwin man page mirror](https://www.manpagez.com/man/2/chroot/)
- The syscall itself is present in the current XNU source (`bsd/kern/syscalls.master`,
  fetched directly from Apple's own repo): `61 AUE_CHROOT ALL { int chroot(user_addr_t path); }`
  — it exists, unlike a namespace facility (see §3), but it's gated on the
  effective UID being root, full stop.
  Source: [apple-oss-distributions/xnu, bsd/kern/syscalls.master](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/syscalls.master)
- Unlike Linux, macOS has no `unshare --user --map-root-user` trick to fake
  root inside a private namespace first (§3) — there's no namespace to map
  root into. So for an unprivileged personal-user launcher, `chroot` is a
  dead end for the same underlying reason it would be on Linux without
  `CLONE_NEWUSER`: it needs real root, and there's no unprivileged escape
  hatch on this OS at all.

**Verdict**: technically present, unprivileged-unusable, not worth requiring
`sudo` for a problem that (per §0) doesn't need hiding from anyone.

## 3. Linux-style user/mount namespaces — confirmed absent

- Directly inspected the current Darwin/XNU syscall table rather than relying
  on secondhand claims: `curl`'d
  `https://raw.githubusercontent.com/apple-oss-distributions/xnu/main/bsd/kern/syscalls.master`
  and grepped for `unshare|clone|setns|newuser|newns`. The only hits are
  `clonefileat` / `fclonefileat` — APFS **file**-cloning (copy-on-write file
  duplication), unrelated to process/namespace isolation. There is no
  `unshare()`, no `clone(2)` with namespace flags, no `setns(2)`, and (also
  checked) no `jail(2)` either — Darwin never grew a BSD-jail-style container
  primitive on top of its inherited FreeBSD-derived `chroot`.
  Source: [apple-oss-distributions/xnu, bsd/kern/syscalls.master](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/syscalls.master) (fetched and grepped directly, see above)
- Why: `syscalls.master` is literally XNU's system-call table — the
  authoritative source `makesyscalls.sh` uses to generate the kernel's
  syscall dispatch. Its absence from that file isn't a documentation gap,
  it's confirmation the kernel has no entry point for it. Linux namespaces
  (`CLONE_NEWUSER`, `CLONE_NEWNS`, etc.) were added to the Linux kernel
  starting 2002 (`CLONE_NEWNS`) through 2013 (unprivileged `CLONE_NEWUSER`,
  Linux 3.8) as Linux-specific `clone(2)` flags; XNU's BSD layer derives from
  FreeBSD's process/VFS model, which never adopted this feature, and Apple
  has not added an equivalent syscall since.
  Source: [user_namespaces(7), Linux man-pages](https://man7.org/linux/man-pages/man7/user_namespaces.7.html) (for the Linux-side history/versioning cited above, contrasted against the XNU table)

**Verdict**: confirmed — there is no Darwin equivalent of `unshare -rm`.
Whatever the bastion research built (research 01) cannot be ported to macOS
even in principle; it's not a matter of a missing binary, the kernel has no
such facility.

## 4. Plain approach: fresh temp dir as `$HOME`, deleted on exit

- No OS-level sandboxing at all: `export HOME="$(mktemp -d)"`, materialize
  dotfiles/secrets into it, run the shell, and on exit `rm -rf` that
  directory. `mktemp -d` is POSIX/BSD-standard and already relied on
  elsewhere for scratch directories; no new dependency.
- Given §0's conclusion (no peer to hide from), this fully satisfies the
  actual goal. The only engineering problem left is making the cleanup
  reliable across every exit path — normal exit, `Ctrl-C`, `kill`, and a
  crash — which is a shell signal-handling problem, not an isolation
  problem:
  - Normal/interrupt/terminate exits: a `trap 'rm -rf "$tmphome"' EXIT INT TERM`
    in the launcher script covers these deterministically.
  - `SIGKILL` or a hard crash/power loss: **no trap can run**, on any OS —
    this is a real, inherent gap of the plain approach, not something a
    smarter shell script fixes. The mitigation is a stale-directory sweep
    the *next* time the launcher runs (e.g. delete abandoned ephemeral-home
    dirs under a known prefix in `TMPDIR` older than the current session),
    not a stronger cleanup-on-exit mechanism, because nothing runs after
    `SIGKILL`.
  - macOS does not aggressively auto-purge `/tmp`/`$TMPDIR` on its own the
    way some Linux distros do via `systemd-tmpfiles`; a crashed session's
    leftovers would sit there until the next launch's sweep, not disappear
    on their own. (No first-party citation found stating macOS's exact
    tmp-cleanup cadence; flagged under "what remains unknown" below rather
    than asserted further.)

**Verdict**: this is the right-shaped tool for the actual goal — cleanup
reliability, not filesystem hiding — and needs no OS sandboxing primitive at
all.

## 5. Apple's native containerization (`container` CLI / Containerization framework)

- Apple's own `container` tool: "a tool that you can use to create and run
  Linux containers as lightweight virtual machines on your Mac." Each
  container runs in its own dedicated lightweight VM (not a shared-kernel
  container), built on the open-source `Containerization` Swift framework.
  Source: [apple/container README](https://github.com/apple/container)
- System requirement, stated directly by Apple: "You need a Mac with Apple
  silicon to run container... container is supported on macOS 26, since it
  takes advantage of new features and enhancements to virtualization and
  networking in this release." Older macOS versions and Intel Macs are
  explicitly unsupported.
  Source: [apple/container README](https://github.com/apple/container)
- This is aimed at running **Linux** OCI container images on a Mac (a
  Docker-Desktop-alternative use case), not at isolating a native macOS
  login shell's `$HOME`. Adopting it here would mean: requiring macOS 26 +
  Apple Silicon (ruling out older/Intel laptops), paying VM boot latency for
  every ephemeral launch, and running the personal shell environment inside
  a Linux guest instead of natively on macOS — solving a problem ("hide
  `$HOME` from a peer") that §0 already established doesn't exist on this
  target, at the cost of a full VM boundary.

**Verdict**: real, first-party, well-documented — and overkill for this
goal. Worth knowing it exists as a ceiling if requirements ever change (e.g.
wanting root-equivalent isolation even on a personal laptop), but not
proportionate to "throwaway `$HOME`, clean exit."

## Summary table

| Mechanism | Unprivileged? | Deprecated/limited? | Solves "isolate/redirect $HOME"? | Fit for stated goal |
|---|---|---|---|---|
| `sandbox-exec` (Seatbelt) | Yes | Deprecated, no CLI successor | No — restricts access, doesn't redirect `$HOME` | Poor |
| `chroot` | No (root-only, no unprivileged escape hatch) | N/A | Yes, in principle | Poor (needs root for no benefit) |
| Linux-style user/mount namespaces | N/A | Don't exist on Darwin at all | N/A | Not available |
| Fresh `mktemp -d` as `$HOME` + trap-based cleanup | Yes | No | Yes, fully — matches actual goal | **Good fit** |
| `container` CLI / Containerization VM framework | Yes (as a normal app) | macOS 26 + Apple Silicon only | Yes, but at VM granularity | Overkill |

## What remains unknown

- Exact macOS `/tmp`/`TMPDIR` auto-cleanup cadence (if any) was not pinned
  down against a first-party source — doesn't block the recommendation below
  since the launcher shouldn't rely on OS auto-cleanup anyway, but worth a
  quick empirical check (`man periodic`, `/etc/periodic/daily`) if the
  stale-dir sweep design wants to lean on it as a backstop.
- Whether `TMPDIR` on macOS defaults to a per-user, already-somewhat-private
  location (`/var/folders/.../T/`, mode 0700) versus a shared `/tmp` doesn't
  change the recommendation (no peer threat either way) but is a nice-to-know
  for picking where the fresh dir gets created.

## Recommendation

Given the confirmed absence of a peer-uid threat on a personal laptop, and
that no namespace primitive exists on Darwin regardless:

1. **Primary: plain temp-dir `$HOME`.** `export HOME="$(mktemp -d)"`,
   materialize dotfiles/secrets exactly as the bastion path does, run the
   shell, and `trap 'rm -rf "$tmphome"' EXIT INT TERM` in the launcher for
   the normal/interrupted-exit paths. No new dependency, no OS-sandboxing
   primitive, matches the actual stated goal (throwaway `$HOME` + clean exit)
   with nothing extra.
2. **Accept the SIGKILL/crash gap as inherent, and cover it with a
   stale-dir sweep at next launch**, not a stronger trap — nothing can run
   after `SIGKILL`/power loss on any OS. The launcher should look for and
   remove abandoned ephemeral-home directories (by a recognizable prefix)
   at the start of each new session.
3. **Do not use `sandbox-exec`** — deprecated by Apple's own man page, no
   supported CLI/headless successor, and it's the wrong primitive shape
   anyway (access-restriction, not `$HOME` redirection).
4. **Do not use `chroot`** — root-only with no unprivileged path on this OS,
   and buys nothing given there's no peer to isolate from.
5. **Do not reach for the `container` CLI / Containerization VM framework**
   for this — real and first-party, but macOS-26-and-Apple-Silicon-only,
   Linux-container-shaped, and a full VM boundary is disproportionate to
   "throwaway `$HOME`." Keep it in mind only if a future requirement adds a
   root-equivalent threat to the personal-laptop case.
