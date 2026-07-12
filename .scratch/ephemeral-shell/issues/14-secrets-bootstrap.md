# 14 — Secrets bootstrap

**What to build:** The age passphrase decrypt + sops decrypt flow. Given an interactively-typed passphrase, decrypts `identity.age` into `<target>/.config/sops/age/keys.txt` under a target directory (never any other location), then sops-decrypts each secret entry named in the core module's resolved file-write plan into its planned path under that same target directory. Testable by pointing at any writable directory — it does not require real isolation (ticket 12) to run or verify.

**Blocked by:** 11 — Core materialize module

**Status:** ready-for-agent

- [ ] Interactive passphrase prompt decrypts `identity.age` into `<target>/.config/sops/age/keys.txt`, and only that path — never a persistent or shared location
- [ ] Each secret entry in the resolved file-write plan is sops-decrypted using `SOPS_AGE_KEY_FILE` pointed at that `keys.txt`, written to its planned path under the target directory
- [ ] No caching/agent process (e.g. an ssh-agent-style helper) is started or left running after decrypt completes
- [ ] No key material or decrypted secret is written outside the given target directory
- [ ] Testable by pointing at any writable directory — no dependency on ticket 12's isolation mechanism
- [ ] A wrong passphrase or decrypt failure surfaces a clear error rather than silently proceeding with partial/missing secrets
