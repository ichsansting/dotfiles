Type: grilling
Status: resolved

## Question

How does the age private key (or equivalent secret-decryption capability) get into an ephemeral session without ever persisting in plaintext on the shared bastion between launches, while still keeping "launch via a short command" low-friction? Weigh options such as a passphrase entered at each launch, a remote fetch from a vault/secrets manager, or another mechanism — and decide.

Include a quick sanity check that sops+age is still the right encryption mechanism for this ephemeral model (it was inherited from `~/dotfiles-old`, not re-litigated after the pivot to ephemeral-only).

## Answer

**Sanity check: sops+age confirmed unchanged.** Age is a single static binary (trivial to include in the flake's package set), the identity is one passphrase-encrypted file safe to keep committed in the repo, and per-module secrets stay as separate sops-encrypted YAML files decrypted on demand — nothing about going ephemeral changes this shape. The only thing that changes is *where* the decrypted key ends up.

**Mechanism: reuse the `~/dotfiles-old` identity.age + passphrase flow as-is, run fresh on every launch.**

- `identity.age` (the age keypair, passphrase-encrypted via `age --passphrase --encrypt`) stays committed in the repo, same as today.
- On every launch, after entering the isolated tmpfs `$HOME` (from [ticket 01](01-isolation-mechanism-research.md)'s `unshare -rm` boundary), the launcher runs `age --decrypt` with an interactively-typed passphrase, writing straight to `~/.config/sops/age/keys.txt` *inside that fresh isolated `$HOME`* — never a persistent location, never cached to disk outside the session.
- Per-module secrets then decrypt via `sops --decrypt --extract` with `SOPS_AGE_KEY_FILE` pointed at that path, same as `~/dotfiles-old`'s `sops.py`.
- **Rejected: an ssh-agent-style caching helper** to avoid retyping the passphrase on frequent relaunches. Rejected because on the shared bastion, any socket persisting outside the per-launch isolation boundary is reachable by other same-uid peer sessions — a different human sharing the account could pull the decrypted key without ever knowing the passphrase, undermining the isolation work in ticket 01. Explicitly accepted: passphrase is typed on every single launch, even for frequent same-day relaunches, as the cost of never holding a standing decryption capability.
- **Rejected: remote vault/secrets-manager fetch.** Not pursued — adds a new mechanism and a new bootstrapping-trust problem without solving anything the existing passphrase flow doesn't already solve.

**Open dependency, not resolved here:** `identity.age` must already be present on the machine before decrypt can run, which depends on how the repo itself gets onto a bastion — still fog (see map's Not yet specified).
