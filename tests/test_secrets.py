"""Secrets bootstrap: age passphrase decrypt + sops decrypt. See
.scratch/ephemeral-shell/issues/14-secrets-bootstrap.md.

Exercises real `age`/`sops` binaries (skipped if unavailable) rather than
mocking them — the thing worth testing here is the subprocess wiring and
target-directory containment, not resolution logic (already covered by
test_materialize.py). An interactive passphrase prompt needs a controlling
terminal, so `with_passphrase` (dotfiles.testing) redirects this process's
stdin/stdout/stderr to a pty pair for the duration of the call under test.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from dotfiles.core import materialize as m
from dotfiles.core import secrets
from dotfiles.testing import with_passphrase as _with_passphrase
from conftest import write_bundle_file, write_fragment, write_preset

HAS_AGE = shutil.which("age") is not None and shutil.which("age-keygen") is not None
HAS_SOPS = shutil.which("sops") is not None
needs_age = pytest.mark.skipif(not HAS_AGE, reason="age/age-keygen not available")
needs_age_sops = pytest.mark.skipif(not (HAS_AGE and HAS_SOPS), reason="age/sops not available")


def _make_age_identity(tmp_path: Path, passphrase: str) -> tuple[Path, str]:
    """Generate a fresh age keypair and passphrase-encrypt it into
    identity.age, returning (identity_file, recipient public key)."""
    raw_key = tmp_path / "raw-key.txt"
    subprocess.run(["age-keygen", "-o", str(raw_key)], check=True, capture_output=True)
    recipient = next(
        line.split(":", 1)[1].strip()
        for line in raw_key.read_text().splitlines()
        if "public key:" in line.lower()
    )

    identity_file = tmp_path / "identity.age"
    _with_passphrase(
        passphrase,
        subprocess.run,
        ["age", "--passphrase", "--encrypt", "-o", str(identity_file), str(raw_key)],
        feed_count=2,
        check=True,
    )
    raw_key.unlink()
    return identity_file, recipient


def _sops_encrypt_binary(content: bytes, recipient: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".plain-tmp")
    tmp.write_bytes(content)
    try:
        result = subprocess.run(
            [
                "sops",
                "--encrypt",
                "--config",
                "/dev/null",  # ignore any .sops.yaml sops finds via cwd — this fixture supplies its own recipient
                "--age",
                recipient,
                "--input-type",
                "binary",
                "--output-type",
                "binary",
                str(tmp),
            ],
            capture_output=True,
            check=True,
        )
        out_path.write_bytes(result.stdout)
    finally:
        tmp.unlink()


# -- decrypt_identity ----------------------------------------------------------


def test_decrypt_identity_missing_file_raises_without_invoking_age(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        secrets.decrypt_identity(tmp_path / "no-such-identity.age", tmp_path / "target")


@needs_age
def test_decrypt_identity_correct_passphrase(tmp_path: Path):
    passphrase = "correct horse battery staple"
    identity_file, _ = _make_age_identity(tmp_path, passphrase)
    target = tmp_path / "target"
    target.mkdir()

    key_path = _with_passphrase(passphrase, secrets.decrypt_identity, identity_file, target)

    assert key_path == target / ".config" / "sops" / "age" / "keys.txt"
    assert key_path.exists()
    assert (key_path.stat().st_mode & 0o777) == 0o600
    assert "AGE-SECRET-KEY" in key_path.read_text()


@needs_age
def test_decrypt_identity_wrong_passphrase_raises(tmp_path: Path):
    identity_file, _ = _make_age_identity(tmp_path, "correct horse battery staple")
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(RuntimeError, match="wrong passphrase"):
        _with_passphrase("definitely wrong", secrets.decrypt_identity, identity_file, target)

    assert not (target / ".config" / "sops" / "age" / "keys.txt").exists()


# -- bootstrap: end-to-end secret decrypt + write -------------------------------


@needs_age_sops
def test_bootstrap_decrypts_identity_and_every_secret_entry(tmp_path: Path):
    passphrase = "correct horse battery staple"
    identity_file, recipient = _make_age_identity(tmp_path, passphrase)

    repo = tmp_path / "repo"
    write_bundle_file(repo, "vcs", ".ssh/id_ed25519", "secret")
    write_fragment(repo, ".claude/CLAUDE.md", "10", "vcs", "unused-plaintext-placeholder", secret=True)
    write_preset(repo, "personal", bundles=["vcs"], settings={})

    ssh_key_content = b"-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----\n"
    fragment_content = b"secret claude fragment content"
    _sops_encrypt_binary(ssh_key_content, recipient, repo / "bundles" / "vcs" / "files" / ".ssh" / "id_ed25519")
    _sops_encrypt_binary(
        fragment_content, recipient, repo / "fragments" / ".claude" / "CLAUDE.md.d" / "10-vcs.secret.md"
    )

    target = tmp_path / "ephemeral-home"
    target.mkdir()

    decrypted = _with_passphrase(passphrase, secrets.bootstrap, repo, "personal", target, identity_file)

    assert decrypted[".ssh/id_ed25519"] == ssh_key_content
    assert decrypted[".claude/CLAUDE.md.d/10-vcs.secret.md"] == fragment_content

    key_path = target / ".config" / "sops" / "age" / "keys.txt"
    assert key_path.exists()
    assert (key_path.stat().st_mode & 0o777) == 0o600

    ssh_key_path = target / ".ssh" / "id_ed25519"
    assert ssh_key_path.read_bytes() == ssh_key_content
    assert (ssh_key_path.stat().st_mode & 0o777) == 0o600

    claude_md_path = target / ".claude" / "CLAUDE.md"
    assert claude_md_path.read_bytes() == fragment_content + b"\n"
    assert (claude_md_path.stat().st_mode & 0o777) == 0o600

    # Nothing lands outside the target directory.
    assert not (tmp_path / ".config").exists()
    assert not (repo / ".config").exists()


@needs_age_sops
def test_bootstrap_wrong_recipient_raises_clear_error(tmp_path: Path):
    passphrase = "correct horse battery staple"
    identity_file, _real_recipient = _make_age_identity(tmp_path, passphrase)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    _, other_recipient = _make_age_identity(other_dir, passphrase)

    repo = tmp_path / "repo"
    write_bundle_file(repo, "vcs", ".ssh/id_ed25519", "secret")
    write_preset(repo, "personal", bundles=["vcs"], settings={})
    _sops_encrypt_binary(
        b"content encrypted for a different identity",
        other_recipient,
        repo / "bundles" / "vcs" / "files" / ".ssh" / "id_ed25519",
    )

    target = tmp_path / "ephemeral-home"
    target.mkdir()

    with pytest.raises(RuntimeError, match="sops decrypt failed"):
        _with_passphrase(passphrase, secrets.bootstrap, repo, "personal", target, identity_file)

    assert not (target / ".ssh" / "id_ed25519").exists()


# -- existing-secret edit flow (ticket 18): decrypt one file, re-encrypt ------


@needs_age_sops
def test_decrypt_edit_reencrypt_roundtrip(tmp_path: Path):
    """The editing TUI's existing-secret flow (ticket 18): decrypt_identity
    + decrypt_secret_file to get plaintext for $EDITOR, encrypt_secret to
    write the edited content back — the new content must decrypt cleanly
    with the same identity afterward."""
    passphrase = "correct horse battery staple"
    identity_file, recipient = _make_age_identity(tmp_path, passphrase)

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".sops.yaml").write_text(f"keys:\n  - &identity {recipient}\n")

    secret_path = repo / "bundles" / "vcs" / "files" / ".ssh" / "id_ed25519"
    original = b"-----BEGIN OPENSSH PRIVATE KEY-----\noriginal\n-----END OPENSSH PRIVATE KEY-----\n"
    _sops_encrypt_binary(original, recipient, secret_path)

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    key_path = _with_passphrase(passphrase, secrets.decrypt_identity, identity_file, scratch)
    plaintext = secrets.decrypt_secret_file(secret_path, key_path)
    assert plaintext == original

    edited = plaintext.replace(b"original", b"edited")
    encrypted = secrets.encrypt_secret(repo, edited)
    secret_path.write_bytes(encrypted)

    assert secrets.decrypt_secret_file(secret_path, key_path) == edited


def test_required_secrets_covers_whole_file_and_fragment(root: Path):
    write_bundle_file(root, "vcs", ".ssh/id_ed25519", "secret")
    write_bundle_file(root, "vcs", ".gitconfig", "plain", content="[user]\n")
    write_fragment(root, ".claude/CLAUDE.md", "10", "vcs", "secret content", secret=True)
    write_fragment(root, ".claude/CLAUDE.md", "20", "vcs", "plain content", secret=False)
    write_preset(root, "personal", bundles=["vcs"], settings={})

    sources = m.required_secrets(root, "personal")
    keys = {s.key for s in sources}

    assert keys == {".ssh/id_ed25519", ".claude/CLAUDE.md.d/10-vcs.secret.md"}
    by_key = {s.key: s.source for s in sources}
    assert by_key[".ssh/id_ed25519"] == root / "bundles" / "vcs" / "files" / ".ssh" / "id_ed25519"
    assert by_key[".claude/CLAUDE.md.d/10-vcs.secret.md"] == (
        root / "fragments" / ".claude" / "CLAUDE.md.d" / "10-vcs.secret.md"
    )
