# 18 — Editing TUI: secret editing + materialize preview

**What to build:** Adds two capabilities to the editing TUI from ticket 17: a decrypt→`$EDITOR`→re-encrypt→shred flow for secret items (reusing ticket 14's age/sops primitives), and a per-preset materialize dry-run preview that runs the core module (ticket 11) against a scratch directory to show composed fragment output, resolved settings overlay, and resolved package list before pushing.

**Blocked by:** 17 — Editing TUI CRUD, 14 — Secrets bootstrap

**Status:** ready-for-agent

- [ ] Selecting a secret item decrypts it with the age key into a temp file, opens `$EDITOR`, and re-encrypts with sops on save
- [ ] The temp plaintext is shredded after use, regardless of whether the edit was saved or cancelled
- [ ] The re-encrypted file is auto-committed/pushed like any other edit (per ticket 17's auto-commit behavior)
- [ ] A per-preset preview command runs the core module's resolution+compose logic (ticket 11) against a scratch directory
- [ ] Preview output shows composed fragment content, resolved settings overlay, and resolved package list
- [ ] Preview never writes to a real `$HOME` and never triggers a commit or push
