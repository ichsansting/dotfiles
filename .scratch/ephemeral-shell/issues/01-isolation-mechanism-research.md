Type: research
Status: resolved

## Question

What mechanisms are actually available to get a private mount namespace / isolated tmpfs `$HOME` as an unprivileged same-uid user on the target bastion (accessed via AWS SSM)? Investigate bubblewrap availability, `unshare --user`/`unshare --mount` behavior without root, whether unprivileged user namespaces are enabled (e.g. `/proc/sys/kernel/unprivileged_userns_clone` or the distro equivalent), and any other rootless isolation mechanism that would let one same-uid session hide its ephemeral `$HOME` from another same-uid session's filesystem view.

Output a summary of which mechanisms are viable, their caveats, and what facts remain unknown without direct access to the actual bastion. Root is trusted (not the threat), so nothing here needs to defend against a hostile root.

## Answer

Full findings: [`research/01-isolation-mechanisms.md`](../research/01-isolation-mechanisms.md).

All rootless routes to a private mount namespace funnel through one kernel gate: unprivileged `CLONE_NEWUSER`. Both `unshare --user --map-root-user --mount` (util-linux, near-universal) and `bwrap` (which dropped its setuid fallback entirely) depend on it; `mount --bind` alone doesn't sidestep it since `CLONE_NEWNS` still needs `CAP_SYS_ADMIN`, only obtainable by first creating a user namespace. `fakeroot` fakes stat/chown results but provides zero real isolation. Because both sessions share a UID, there is no permission-based fallback if userns is blocked.

Two independent, distro-specific gates can block it: (a) `kernel.unprivileged_userns_clone` (Debian-specific, superseded by upstream `user.max_user_namespaces`), and (b) Ubuntu's AppArmor-mediated `kernel.apparmor_restrict_unprivileged_userns` (on by default since 24.04). Amazon Linux (the likely AWS SSM bastion image) carries neither sysctl by default.

Key corrective finding: Nix's own sandbox does **not** prove unprivileged userns works — the standard multi-user install forwards builds to a root `nix-daemon`, which creates namespaces with real root privilege regardless of the userns sysctls (confirmed in NixOS/nix issue #8165). "Nix works here" is not evidence.

**Decision**: build the launcher on `unshare -rm` + manual bind/tmpfs mount directly (zero extra dependency beyond `util-linux`), treat `bwrap` as an optional upgrade if already present, and **fail loudly** (not silently degrade to an unisolated `$HOME`) if the userns probe fails. Actual distro/AppArmor posture on the real bastion remains unchecked — the research file includes copy-paste probe commands (`unshare --user --map-root-user --mount ... UNSHARE_MOUNT_OK` is the authoritative one) to run there.
