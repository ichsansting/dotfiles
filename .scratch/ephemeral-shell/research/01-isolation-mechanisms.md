# Isolation mechanisms for a private mount namespace / tmpfs $HOME as unprivileged same-uid user

Type: research
Answers: `.scratch/ephemeral-shell/issues/01-isolation-mechanism-research.md`

## Threat model recap

Same-uid peer users on a shared bastion account reached via AWS SSM. Root is
trusted, not defended against. Goal: hide one same-uid session's ephemeral
`$HOME` from another same-uid session's filesystem view. Not container-grade,
not defending against hostile root.

One structural fact worth stating up front: because both sessions log in as
the **same UID**, standard Unix DAC permissions (`chmod`/`chown`) cannot hide
anything between them — a `0700` directory is still readable by the same
UID. The only thing that can hide a directory from a sibling same-uid
process is **namespace isolation** (the sibling's mount table simply doesn't
contain the entry). That is why this entire investigation reduces to "can an
unprivileged same-uid user create a private mount namespace," and there is
no filesystem-permission fallback if the answer is no.

## 1. bubblewrap (bwrap)

- Fully unprivileged today. From the project README: "There is a feature in
  the Linux kernel called user namespaces which allows unprivileged users to
  use container features. Bubblewrap uses these to build the sandbox,
  allowing any user to use the tool." It depends on `CLONE_NEWUSER` (Linux
  user namespaces).
  Source: [containers/bubblewrap README](https://github.com/containers/bubblewrap)
- Setuid fallback is gone: "Historically, bubblewrap also supported a setuid
  mode for systems where unprivileged user namespaces were not supported.
  However, this has been removed." So on a machine where unprivileged
  userns is disabled/restricted, current bubblewrap has **no fallback** — it
  just fails.
  Source: same README as above.
- It also hardens itself once inside: "bubblewrap uses PR_SET_NO_NEW_PRIVS to
  turn off setuid binaries" and only retains a minimal capability set
  (`CAP_SYS_ADMIN` inside its own new user namespace) while always accessing
  the filesystem as the invoking uid — i.e. it's still fundamentally a
  same-uid tool, consistent with this threat model.
  Source: same README.
- Man page (`bwrap.xml`, source of `bwrap(1)`): "bwrap is an unprivileged
  low-level sandboxing tool... Optionally it also sets up new user, ipc,
  pid, network and uts namespaces (but note the user namespace is required
  if bwrap is not run as root)." Relevant flags: `--unshare-user` (new user
  namespace), `--tmpfs DEST` (mount a fresh tmpfs at DEST), `--bind SRC DEST`
  / `--ro-bind SRC DEST` (bind-mount host paths in).
  Source: [bwrap.xml on GitHub](https://github.com/containers/bubblewrap/blob/main/bwrap.xml)
- Concretely, for a private `$HOME`: something like
  `bwrap --unshare-user --unshare-pid --dev-bind / / --tmpfs "$HOME" --bind /path/to/ephemeral-home "$HOME" bash`
  gives the sandboxed process (and only it) a `$HOME` mount replaced by a
  fresh tmpfs/bind target; a sibling shell outside the sandbox still sees the
  real `$HOME` untouched, because the remount only exists in bwrap's private
  mount namespace.

**Caveat**: requires the `bwrap` binary to be present on the bastion. Not
guaranteed on an arbitrary AWS SSM target (see unknowns below). It could be
brought in via the Nix flake itself (`nixpkgs#bubblewrap`) if Nix is present
and unprivileged userns works — but that's circular with the very thing
being tested.

## 2. `unshare --user` / `unshare --mount`

- `-r, --map-root-user`: "Run the program only after the current effective
  user and group IDs have been mapped to the superuser UID and GID in the
  newly created user namespace... makes it possible to conveniently gain
  capabilities needed to manage various aspects of the newly created
  namespaces (such as configuring interfaces in the network namespace or
  mounting filesystems in the mount namespace) even when run unprivileged."
  Source: [unshare(1)](https://man7.org/linux/man-pages/man1/unshare.1.html)
- `-m, --mount [file]`: "Create a new mount namespace." `-U, --user [file]`:
  "Create a new user namespace." Combining `-U`/`-r` with `-m` in one
  invocation is exactly the unprivileged pattern (`unshare --user --map-root-user --mount ...`,
  commonly shortened `unshare -rm`).
  Source: same man page.
- Why the combination works unprivileged: `unshare(2)` guarantees ordering —
  "If CLONE_NEWUSER is specified along with other CLONE_NEW* flags in a
  single clone(2) or unshare(2) call, the user namespace is guaranteed to be
  created first, giving the child (clone(2)) or caller (unshare(2))
  privileges over the remaining namespaces created by the call." This is
  precisely what lets an unprivileged caller unshare the mount namespace in
  the same call as the user namespace.
  Source: [unshare(2)](https://man7.org/linux/man-pages/man2/unshare.2.html)
- What you get inside: `user_namespaces(7)` — "Since Linux 3.8, unprivileged
  processes can create user namespaces, and the other types of namespaces
  can be created with just the CAP_SYS_ADMIN capability in the caller's user
  namespace." And: "The child process created by clone(2) with the
  CLONE_NEWUSER flag starts out with a complete set of capabilities in the
  new user namespace" — but "that process has no capabilities in the
  parent... user namespace, even if the new namespace is created or joined
  by the root user." Crucially for mounts: "Holding CAP_SYS_ADMIN within the
  user namespace that owns a process's mount namespace allows that process
  to create bind mounts and mount [...] tmpfs" among other pseudo/virtual
  filesystems, but "mounting block-based filesystems can be done only by a
  process that holds CAP_SYS_ADMIN in the initial user namespace." tmpfs and
  bind mounts are exactly what's needed here, so this restriction doesn't
  block the use case.
  Source: [user_namespaces(7)](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)
- Concretely: `unshare --user --map-root-user --mount --propagation private -- bash`
  then inside that shell, `mount -t tmpfs tmpfs "$HOME"` (or bind-mount a
  prepared ephemeral dir over `$HOME`) is invisible outside the new mount
  namespace — a sibling same-uid shell that did not join this namespace sees
  the original `$HOME`. `--propagation private` (or manually
  `mount --make-rprivate /`) matters: without it, mount events can still
  propagate to/from the parent's mount namespace depending on the original
  propagation type of the mount point.

**This is the lower-dependency option** — `unshare` ships in `util-linux`,
which is present on essentially every Linux distro by default (no extra
package to source), unlike `bwrap`.

## 3. Unprivileged user namespace availability / restrictions

Two independent gates exist, and a machine can have either, both, or
neither:

**(a) `kernel.unprivileged_userns_clone` — Debian/Ubuntu-specific, not
upstream.** Debian bug #1024186 ("linux: consider deprecating
unprivileged_userns_clone") confirms it is a Debian-specific out-of-tree
kernel patch, and that Debian's own guidance is to move off it in favor of
the upstream sysctl `user.max_user_namespaces`: "kernel.unprivileged_userns_clone
comes from a Debian-specific patch that might be removed in future
releases," with `user.max_user_namespaces=0` having the equivalent disabling
effect and being the upstream-portable knob. Unprivileged user namespaces
have been enabled by default in Debian since Bullseye.
Source: [Debian bug #1024186](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1024186&msg=2)

Non-Debian-derived distros (RHEL/CentOS family, and — relevant here — Amazon
Linux, which is what most AWS-managed SSM-accessible EC2 bastions run) don't
carry this sysctl at all; `/proc/sys/kernel/unprivileged_userns_clone`
simply won't exist there. The portable check is
`/proc/sys/user/max_user_namespaces` (upstream), where `0` means disabled.

**(b) AppArmor-mediated restriction — Ubuntu 23.10+, on by default since
24.04.** This is newer and easy to miss. Ubuntu added a second, independent
gate on top of the kernel feature: "Ubuntu 23.10 and 24.04 LTS introduced
new AppArmor-based features to reduce the attack surface presented by
unprivileged user namespaces... Unprivileged processes will only be able to
create user namespaces if they are confined and have the `userns,` rule in
their AppArmor profile (or if they have CAP_SYS_ADMIN)."
Source: [Ubuntu blog: Restricted unprivileged user namespaces are coming to Ubuntu 23.10](https://ubuntu.com/blog/ubuntu-23-10-restricted-unprivileged-user-namespaces)

The controlling sysctl is `kernel.apparmor_restrict_unprivileged_userns`
(`1` = restriction enforced, `0` = not enforced). Ubuntu's spec doc for this
feature confirms the exact name and semantics, and that as of the spec
being written the plan was to flip the default to `1`: "This sysctl is
currently not enabled (via a value of 0). As such, this sysctl should be
changed to be enabled by default (via a default value of 1)." Ubuntu's own
23.10 blog post states 24.04 LTS ships it enabled by default.
Source: [Ubuntu discourse spec: Unprivileged user namespace restrictions via AppArmor in Ubuntu 23.10](https://discourse.ubuntu.com/t/spec-unprivileged-user-namespace-restrictions-via-apparmor-in-ubuntu-23-10/37626)

Practically: even where the kernel allows unprivileged `CLONE_NEWUSER`
(gate (a) open), an unconfined process on Ubuntu 24.04+ can still be blocked
by gate (b) unless its AppArmor profile carries a `userns,` rule (interactive
login shells are typically "unconfined" and get denied unless an admin has
added a local override profile, per the same spec doc's bypass/allow
discussion).

**Detection**: no single command covers both gates portably. See the
"unknowns" section below for the exact commands to run on the actual
bastion; the single most reliable check is just attempting the real
operation (`unshare -rm ... mount -t tmpfs ...`) and checking the exit
code/error text, rather than trying to interpret sysctls whose existence
and meaning vary by distro.

## 4. Other rootless mechanisms

- **`mount --bind` inside a plain (non-userns) private mount namespace**:
  not a separate escape route — `CLONE_NEWNS` (new mount namespace) by
  itself still requires `CAP_SYS_ADMIN` in the current user namespace. For
  an unprivileged process that means it still needs the paired
  `CLONE_NEWUSER` first (see §2's ordering guarantee from `unshare(2)`).
  There's no way to get a private mount namespace unprivileged that doesn't
  route through the same "unprivileged userns" gate covered in §3.
- **fakeroot**: doesn't provide real isolation. It's an `LD_PRELOAD` shim
  that fakes the *results* of `stat`/`chown`/etc. for processes running
  under it, so a program *thinks* it's root and thinks files have different
  ownership — but the underlying files, and their real visibility to any
  other process (same uid or not), are completely unchanged. It cannot hide
  a directory from a sibling session; not viable for this threat model.
- **setuid helper binaries** (e.g. historically `fusermount`, old `bwrap`
  setuid mode): would work regardless of unprivileged-userns availability,
  but require a setuid-root binary to be installed by an admin ahead of
  time — not something the launcher can provision itself on an arbitrary
  bastion, and current bubblewrap has dropped this path entirely (§1).
- No other rootless kernel mechanism grants a same-uid process a private
  view of the filesystem outside of the mount-namespace family gated by
  `CLONE_NEWUSER`. If unprivileged userns is unavailable, there is no
  fallback that satisfies "hide $HOME from a sibling same-uid session" short
  of privileged (root/sudo/setuid) help.

## 5. Does Nix's own sandbox depend on unprivileged user namespaces?

Short answer: **not in the standard multi-user install**, so "Nix works on
this bastion" is **not** evidence that unprivileged user namespaces are
available to ordinary users.

- The Nix manual: sandbox default is "`true` on Linux and `false` on all
  other platforms," and on Linux "builds run in private PID, mount,
  network, IPC and UTS namespaces to isolate them from other processes in
  the system," with "private versions of `/proc`, `/dev`, `/dev/shm` and
  `/dev/pts`." Crucially: "The use of a sandbox requires that Nix is run as
  root (so you should use the 'build users' feature to perform the actual
  builds under different users than root)."
  Source: [Nix manual, nix.conf `sandbox` setting](https://nix.dev/manual/nix/stable/command-ref/conf-file.html)
- That "run as root" is the standard multi-user install shape: an
  unprivileged user's `nix build` is forwarded over a socket to `nix-daemon`,
  which runs as root and does the actual namespace setup with real root
  privilege (`CAP_SYS_ADMIN` in the initial namespace), not via the
  unprivileged-userns-clone path at all.
  Source: [Nix manual, Multi-User Mode](https://nix.dev/manual/nix/2.22/installation/multi-user)
- This was confirmed empirically in a NixOS/nix upstream bug report: with
  `kernel.unprivileged_userns_clone=0` (unprivileged userns disabled), the
  reporter found Nix "will silently run sandboxed tasks without a userns,
  leaking host system UIDs/GIDs. This happens even though `nix-daemon` runs
  as root and should not be impacted by the value of that sysctl," and after
  direct process inspection: "the `nix-daemon` sandbox appears to work
  perfectly fine with `kernel.unprivileged_userns_clone = 0`." I.e. the
  daemon's own namespace creation doesn't go through the unprivileged path
  at all, because it already holds real root.
  Source: [NixOS/nix issue #8165](https://github.com/NixOS/nix/issues/8165)

**Implication for this project**: even if a bastion already has a working
Nix install (which the launcher's design assumes), that tells us nothing
about whether an ordinary interactive user on that box can call
`unshare --user`. It must be checked independently. (A single-user,
daemonless Nix install would be a different story — it runs builds as the
invoking user without root, and would likely need real sandboxing
capability from that same user — but multi-user/daemon mode, the common
default install today, sidesteps the question entirely.)

## Summary table

| Mechanism | Unprivileged? | Extra binary needed | Depends on unprivileged userns | Fallback if userns blocked |
|---|---|---|---|---|
| `unshare -rm` + manual `mount` | Yes | No (`util-linux`, near-universal) | Yes | None |
| `bwrap` | Yes | Yes (`bwrap`) | Yes, and no setuid fallback anymore | None |
| `mount --bind` alone | N/A | No | Same gate as above (needs paired userns) | N/A |
| fakeroot | Yes | Usually yes | No | N/A — doesn't actually isolate |
| setuid helper | Yes (for the user) | Yes, pre-installed by admin | No | N/A — not self-provisionable |
| Nix sandbox (daemon mode) | Daemon is root, not the user | Already assumed present | No (daemon has real root) | Irrelevant to this problem |

## What remains unknown until we actually SSM into the bastion

The two gates in §3 are real but distro/version-specific, and we don't know
which distro or how recent AWS's bastion image is. Concrete checks to run
once there:

```sh
# Which distro/kernel are we actually on? (AWS SSM bastions are often
# Amazon Linux 2/2023, not Debian/Ubuntu — the sysctls below may not exist there.)
cat /etc/os-release
uname -r

# Upstream, portable gate: 0 = unprivileged userns disabled.
cat /proc/sys/user/max_user_namespaces 2>/dev/null || echo "sysctl absent (older kernel or not exposed)"

# Debian/Ubuntu-specific legacy gate: 0 = disabled, may not exist on non-Debian derivatives.
cat /proc/sys/kernel/unprivileged_userns_clone 2>/dev/null || echo "sysctl absent (not Debian/Ubuntu-patched kernel)"

# Ubuntu 23.10+/24.04+ AppArmor gate: 1 = restriction enforced (need a userns rule).
sysctl kernel.apparmor_restrict_unprivileged_userns 2>/dev/null || echo "sysctl absent (not on Ubuntu w/ this patch)"

# Is AppArmor even loaded/enforcing, and is there a profile confining this shell?
aa-status 2>/dev/null || echo "apparmor tools not present / not root-readable"

# The actual, authoritative test: just try it.
unshare --user --map-root-user --mount --propagation private -- \
  sh -c 'mount -t tmpfs tmpfs /mnt 2>/dev/null; mkdir -p /tmp/unshare-probe && mount --bind /tmp /tmp/unshare-probe && echo UNSHARE_MOUNT_OK' \
  || echo UNSHARE_MOUNT_FAILED

# Is bwrap present at all, and does it work unprivileged?
command -v bwrap && bwrap --unshare-user --unshare-pid --ro-bind / / --tmpfs /tmp -- echo BWRAP_OK

# Any leftover setuid bwrap install (unlikely with current bwrap, but check)?
command -v bwrap && getcap "$(command -v bwrap)"; ls -l "$(command -v bwrap)" 2>/dev/null
```

The `unshare ... UNSHARE_MOUNT_OK` line is the one that actually answers the
ticket's question for this specific machine — everything else is diagnostic
context for *why* it succeeded or failed.

## Recommendation

Given the threat model (hide ephemeral `$HOME` from a same-uid sibling,
root trusted, not container-grade):

1. **Primary: `unshare --user --map-root-user --mount --propagation private`
   followed by a `mount --bind`/`mount -t tmpfs` over `$HOME`, run directly
   from the launcher script.** No extra dependency beyond `util-linux`
   (present on essentially every target), so it doesn't add a "is X
   installed" precondition on top of "is Nix installed." This should be the
   thing the launcher builds on.
2. **Optional upgrade, not a dependency: use `bwrap` instead if it happens
   to already be present** (e.g. pull it from nixpkgs once the flake's
   packages are realized) for a more hardened/ergonomic sandbox invocation
   (`--tmpfs $HOME --bind ... $HOME ...` in one declarative command,
   NO_NEW_PRIVS, etc.) — but don't make first-launch depend on fetching it,
   since that's circular (you'd need Nix + network to get a tool whose only
   job here is a task `unshare` already does unprivileged).
3. **No viable fallback if unprivileged userns is blocked** on the target
   bastion (§3's gates). If detection at launch time shows
   `unshare -rm` failing, the launcher should fail loudly and say so, rather
   than silently degrading to an unisolated `$HOME` — per the DAC point in
   the threat-model recap, there is no permission-based fallback that
   actually hides anything between two sessions sharing a UID.
4. Treat the AWS SSM bastion's actual distro/AppArmor posture as unresolved
   until checked (see commands above) — this determines whether item 3 ever
   triggers in practice.
