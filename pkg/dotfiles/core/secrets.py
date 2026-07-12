"""Secrets bootstrap: age passphrase decrypt + sops decrypt (ticket 14), plus
sops encrypt for the editing TUI's new-secret-item flow (ticket 17).

A thin caller of materialize.py — resolving *which* secrets a preset needs
still goes through `required_secrets`/`build_plan`, never duplicated here.
This module only owns the age/sops subprocess invocations and where their
output is allowed to land: exclusively under a caller-given target directory,
never a persistent or shared location, and with no caching/agent process left
running afterward. See .scratch/ephemeral-shell/issues/14-secrets-bootstrap.md.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
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


def decrypt_secret_file(source: Path, age_key_file: Path) -> bytes:
    """sops-decrypts a single already-encrypted secret file (binary format)
    with `age_key_file`. Used both by `bootstrap` (every secret a preset's
    plan depends on) and by the editing TUI's existing-secret edit flow
    (ticket 18, one file at a time, decrypted straight to a plaintext temp
    file for `$EDITOR` rather than into a materialized plan)."""
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
        decrypted[src.key] = decrypt_secret_file(src.source, age_key_file)

    for entry in materialize.build_plan(root, preset_name, decrypted):
        if entry.mode != materialize.MODE_SECRET:
            continue
        out_path = target / entry.path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(entry.content)
        os.chmod(out_path, 0o600)

    return decrypted


def shred_file(path: Path) -> None:
    """Best-effort overwrite-then-delete of a plaintext temp file; falls
    back to a plain unlink if `shred` isn't on PATH."""
    if not path.exists():
        return
    if shutil.which("shred"):
        subprocess.run(["shred", "-u", str(path)], check=False)
    else:
        path.unlink()


def _read_recipient(root: Path) -> str:
    """Reads the single age recipient out of .sops.yaml's `keys:` anchor —
    the same value bin/migrate-secrets extracts by hand. Needed because
    encrypting freshly-typed content (unlike sops editing a real target
    path) has no destination path for .sops.yaml's path_regex creation
    rules to match against."""
    sops_yaml = root / ".sops.yaml"
    if not sops_yaml.exists():
        raise FileNotFoundError(f".sops.yaml not found at {sops_yaml}")
    for line in sops_yaml.read_text().splitlines():
        line = line.strip()
        if line.startswith("- &identity"):
            return line.split("&identity", 1)[1].strip()
    raise RuntimeError(f"no age recipient found in {sops_yaml}")


def encrypt_secret(root: Path, content: bytes) -> bytes:
    """sops-encrypts `content` for the repo's age recipient, returning the
    encrypted binary blob for the caller to write wherever the new secret
    item lives. Bypasses .sops.yaml's path-based creation_rules
    (--config /dev/null) the same way bin/migrate-secrets does, since there
    is no real destination path yet to match against."""
    recipient = _read_recipient(root)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_file = Path(tmp) / "plain"
        tmp_file.write_bytes(content)
        try:
            result = subprocess.run(
                [
                    "sops",
                    "--encrypt",
                    "--config",
                    "/dev/null",
                    "--age",
                    recipient,
                    "--input-type",
                    "binary",
                    "--output-type",
                    "binary",
                    str(tmp_file),
                ],
                capture_output=True,
            )
        finally:
            shred_file(tmp_file)
    if result.returncode != 0:
        raise RuntimeError(f"sops encrypt failed: {result.stderr.decode().strip()}")
    return result.stdout
