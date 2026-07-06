from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dotfiles.core import agekey


@pytest.mark.skipif(shutil.which("age-keygen") is None, reason="age-keygen not available")
def test_generate_creates_key_and_returns_pubkey(home: Path):
    pub = agekey.generate()
    assert pub.startswith("age1")
    p = agekey.key_path()
    assert p.exists()
    assert (p.stat().st_mode & 0o777) == 0o600
    assert agekey.has_key()


def test_patch_sops_yaml(tmp_path: Path):
    sy = tmp_path / ".sops.yaml"
    sy.write_text(
        "keys:\n  - &main age1oldoldoldold\n"
        "creation_rules:\n"
        "  - path_regex: modules/[^/]+/files/.*\\.sops\\.yaml$\n"
        "    key_groups:\n      - age:\n          - *main\n"
    )
    agekey.patch_sops_yaml(sy, "age1newnewnewnew")
    text = sy.read_text()
    assert "age1newnewnewnew" in text and "age1old" not in text
    assert "path_regex" in text  # rest of the file untouched


def test_setup_pubkey_noop_without_private_key(home: Path):
    agekey.setup_pubkey("ssh-keygen", "t@example.com")  # must not raise
    assert not (home / ".ssh/id_ed25519.pub").exists()


@pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="ssh-keygen not available")
def test_setup_pubkey_derives_and_writes(home: Path):
    import subprocess

    ssh = home / ".ssh"
    ssh.mkdir()
    subprocess.run(
        ["ssh-keygen", "-t", "ed25519", "-N", "", "-q", "-f", str(ssh / "id_ed25519")],
        check=True,
    )
    (ssh / "id_ed25519.pub").unlink()

    agekey.setup_pubkey("ssh-keygen", "t@example.com")
    pub = (ssh / "id_ed25519.pub").read_text()
    assert pub.startswith("ssh-ed25519 ")
    signers = (ssh / "allowed_signers").read_text()
    assert signers.startswith("t@example.com ssh-ed25519 ")
    assert ((ssh / "allowed_signers").stat().st_mode & 0o777) == 0o600
