"""Shared pty-driving helper for exercising age's interactive passphrase
prompt without a real controlling terminal. Used by tests/test_secrets.py and
bin/launch-demo — both need to feed a passphrase into an `age` subprocess
that inherits this process's stdin/stdout/stderr.
"""
from __future__ import annotations

import contextlib
import os
import pty
import threading
import time
from collections.abc import Iterator


@contextlib.contextmanager
def fake_tty() -> Iterator[int]:
    """Redirects this process's stdin/stdout/stderr to a pty pair so a
    subprocess that inherits them (age's interactive passphrase prompt) can
    be driven without a real terminal. Yields the pty master fd."""
    master, slave = pty.openpty()
    saved = [os.dup(0), os.dup(1), os.dup(2)]
    os.dup2(slave, 0)
    os.dup2(slave, 1)
    os.dup2(slave, 2)
    try:
        yield master
    finally:
        for fd_no, saved_fd in enumerate(saved):
            os.dup2(saved_fd, fd_no)
            os.close(saved_fd)
        os.close(slave)
        os.close(master)


def with_passphrase(passphrase: str, fn, *args, feed_count: int = 1, **kwargs):
    """Calls fn(*args, **kwargs) while feeding `passphrase` into a faked
    controlling terminal `feed_count` times (2 covers an encrypt/confirm
    pair, 1 covers a single decrypt prompt)."""
    with fake_tty() as master:
        def feed():
            for _ in range(feed_count):
                time.sleep(0.3)
                try:
                    os.write(master, (passphrase + "\n").encode())
                except OSError:
                    return

        t = threading.Thread(target=feed)
        t.start()
        try:
            return fn(*args, **kwargs)
        finally:
            t.join()
