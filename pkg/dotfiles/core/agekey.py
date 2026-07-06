"""Age key management and SSH pubkey derivation."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path


def key_path() -> Path:
    return Path.home() / ".config" / "sops" / "age" / "keys.txt"


def has_key(path: Path | None = None) -> bool:
    return (path or key_path()).exists()


def _age_bin() -> str:
    return os.environ.get("DOTFILES_AGE_BIN") or "age"


def _age_keygen_bin() -> str:
    return os.environ.get("DOTFILES_AGE_KEYGEN_BIN") or "age-keygen"


def generate(path: Path | None = None) -> str:
    """Generate a new age keypair. Returns the public key string."""
    p = path or key_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [_age_keygen_bin(), "-o", str(p)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"age-keygen failed: {result.stderr.strip()}")

    os.chmod(p, 0o600)

    # Public key is echoed by age-keygen and embedded as a comment in the file.
    for line in p.read_text().splitlines():
        m = re.search(r"public key: (age\S+)", line, re.IGNORECASE)
        if m:
            return m.group(1)
    raise RuntimeError("Could not extract public key from generated key file")


def restore(identity_file: Path, path: Path | None = None) -> None:
    """Decrypt a passphrase-protected identity.age into the key path.

    Inherits stdin so the user can enter the passphrase interactively.
    """
    p = path or key_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [_age_bin(), "--decrypt", "-o", str(p), str(identity_file)],
    )
    if result.returncode != 0:
        raise RuntimeError("age decrypt failed — wrong passphrase?")
    os.chmod(p, 0o600)


def backup(identity_file: Path, path: Path | None = None) -> None:
    """Encrypt the key file with a passphrase into identity_file.

    Inherits stdin so the user can enter the passphrase interactively.
    """
    p = path or key_path()
    result = subprocess.run(
        [_age_bin(), "--passphrase", "--encrypt", str(p), "-o", str(identity_file)],
    )
    if result.returncode != 0:
        raise RuntimeError("age encrypt failed")


def patch_sops_yaml(sops_yaml: Path, new_public_key: str) -> None:
    """Replace the age public key in .sops.yaml."""
    text = sops_yaml.read_text()
    new_text = re.sub(r"age1[a-zA-Z0-9]+", new_public_key, text)
    sops_yaml.write_text(new_text)


def setup_pubkey(ssh_keygen_bin: str, git_email: str, ssh_dir: Path | None = None) -> None:
    """Derive the SSH public key from the private key and write allowed_signers.

    No-ops silently if the private key is absent (e.g. git module disabled or
    first run before secrets are deployed).
    """
    ssh_key = (ssh_dir or Path.home() / ".ssh") / "id_ed25519"
    if not ssh_key.exists():
        return

    result = subprocess.run(
        [ssh_keygen_bin, "-y", "-f", str(ssh_key)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ssh-keygen -y failed: {result.stderr.strip()}")

    pub_key = result.stdout.strip()

    pub_path = ssh_key.parent / "id_ed25519.pub"
    pub_path.write_text(pub_key + "\n")
    os.chmod(pub_path, 0o644)

    allowed = ssh_key.parent / "allowed_signers"
    allowed.write_text(f"{git_email} {pub_key}\n")
    os.chmod(allowed, 0o600)
