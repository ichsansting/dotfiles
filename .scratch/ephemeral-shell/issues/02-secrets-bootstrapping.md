Type: grilling

## Question

How does the age private key (or equivalent secret-decryption capability) get into an ephemeral session without ever persisting in plaintext on the shared bastion between launches, while still keeping "launch via a short command" low-friction? Weigh options such as a passphrase entered at each launch, a remote fetch from a vault/secrets manager, or another mechanism — and decide.

Include a quick sanity check that sops+age is still the right encryption mechanism for this ephemeral model (it was inherited from `~/dotfiles-old`, not re-litigated after the pivot to ephemeral-only).
