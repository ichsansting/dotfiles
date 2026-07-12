"""Secrets bootstrap: age passphrase decrypt + sops decrypt (ticket 14).

A thin caller of materialize.py — resolving *which* secrets a preset needs
still goes through `required_secrets`/`build_plan`, never duplicated here.
This module only owns the age/sops subprocess invocations and where their
output is allowed to land: exclusively under a caller-given target directory,
never a persistent or shared location, and with no caching/agent process left
running afterward. See .scratch/ephemeral-shell/issues/14-secrets-bootstrap.md.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import materialize


def decrypt_identity(identity_file: Path, target: Path) -> Path:
    """Interactively decrypt a passphrase-protected identity.age into
    <target>/.config/sops/age/keys.txt, and only that path. Inherits
    stdin/stdout/stderr so `age` can prompt for the passphrase on the
    controlling terminal."""
    if not identity_file.exists():
        raise FileNotFoundError(f"identity file not found: {identity_file}")

    key_path = target / ".config" / "sops" / "age" / "keys.txt"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(["age", "--decrypt", "-o", str(key_path), str(identity_file)])
    if result.returncode != 0:
        raise RuntimeError("age decrypt failed — wrong passphrase?")
    os.chmod(key_path, 0o600)
    return key_path


def _decrypt_secret(source: Path, age_key_file: Path) -> bytes:
    env = {**os.environ, "SOPS_AGE_KEY_FILE": str(age_key_file)}
    result = subprocess.run(
        ["sops", "--decrypt", "--input-type", "binary", "--output-type", "binary", str(source)],
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"sops decrypt failed for {source}: {result.stderr.decode().strip()}")
    return result.stdout


def bootstrap(root: Path, preset_name: str, target: Path, identity_file: Path) -> dict[str, bytes]:
    """Decrypt the age identity into `target`, then sops-decrypt every secret
    entry the preset's resolved file-write plan depends on, writing each to
    its planned path under `target`.

    Returns the decrypted_secrets mapping (key -> plaintext bytes) so a
    caller can feed it back into materialize.build_plan for the full plan
    (plain + secret) without decrypting twice.

    Raises on the first passphrase or decrypt failure — nothing is written
    for entries after the failure, and no partial secret is left behind.
    """
    age_key_file = decrypt_identity(identity_file, target)

    decrypted: dict[str, bytes] = {}
    for src in materialize.required_secrets(root, preset_name):
        decrypted[src.key] = _decrypt_secret(src.source, age_key_file)

    for entry in materialize.build_plan(root, preset_name, decrypted):
        if entry.mode != materialize.MODE_SECRET:
            continue
        out_path = target / entry.path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(entry.content)
        os.chmod(out_path, 0o600)

    return decrypted
