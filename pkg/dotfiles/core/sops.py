"""Subprocess wrapper for sops encrypt/decrypt operations.

No PyYAML dependency: the block-scalar YAML format is built by hand:

    key_name: |
      line1
      line2
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import tempfile
from pathlib import Path


def _sops_bin() -> str:
    return os.environ.get("DOTFILES_SOPS_BIN") or "sops"


def _age_key() -> Path:
    return Path.home() / ".config" / "sops" / "age" / "keys.txt"


def decrypt_extract(
    yaml_path: Path,
    key_name: str,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> bytes:
    """Decrypt a sops-encrypted yaml and extract the value for key_name."""
    sops = sops_bin or _sops_bin()
    key = str(age_key or _age_key())
    env = {**os.environ, "SOPS_AGE_KEY_FILE": key}
    result = subprocess.run(
        [sops, "--decrypt", "--extract", f'["{key_name}"]', str(yaml_path)],
        capture_output=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"sops decrypt failed for {yaml_path}: {result.stderr.decode().strip()}"
        )
    return result.stdout


def encrypt(
    plaintext: bytes,
    output_path: Path,
    key_name: str,
    sops_bin: str | None = None,
    age_key: Path | None = None,
) -> None:
    """Encrypt plaintext as a sops block-scalar YAML and write to output_path.

    The temp file is placed in output_path.parent so the .sops.yaml
    path_regex (modules/[^/]+/files/.*\\.sops\\.yaml$) matches and sops picks
    the right encryption key.
    """
    sops = sops_bin or _sops_bin()
    key = str(age_key or _age_key())
    env = {**os.environ, "SOPS_AGE_KEY_FILE": key}

    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = plaintext.decode("utf-8", errors="replace").splitlines()
    yaml_text = f"{key_name}: |\n" + "".join(f"  {line}\n" for line in lines)

    fd, tmp_path = tempfile.mkstemp(dir=output_path.parent, suffix=".sops.yaml")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(yaml_text)

        result = subprocess.run(
            [sops, "--encrypt", tmp_path],
            capture_output=True,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"sops encrypt failed: {result.stderr.decode().strip()}"
            )
        output_path.write_bytes(result.stdout)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
