Type: research

## Question

What mechanisms are actually available to get a private mount namespace / isolated tmpfs `$HOME` as an unprivileged same-uid user on the target bastion (accessed via AWS SSM)? Investigate bubblewrap availability, `unshare --user`/`unshare --mount` behavior without root, whether unprivileged user namespaces are enabled (e.g. `/proc/sys/kernel/unprivileged_userns_clone` or the distro equivalent), and any other rootless isolation mechanism that would let one same-uid session hide its ephemeral `$HOME` from another same-uid session's filesystem view.

Output a summary of which mechanisms are viable, their caveats, and what facts remain unknown without direct access to the actual bastion. Root is trusted (not the threat), so nothing here needs to defend against a hostile root.
