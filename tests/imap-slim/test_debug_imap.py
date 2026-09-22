"""The protocol trace must not run across the login.

imaplib.Debug echoes every command it sends, and LOGIN carries the password in
clear text, so tracing that was switched on before login printed the password
into whatever the user pasted into a bug report.
"""

import imaplib
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim"))

import debug_imap  # noqa: E402


class FakeIMAP:
    """Records the debug level in force at each step."""

    def __init__(self, *_args, **_kwargs):
        self.seen = {}

    def login(self, _user, _password):
        self.seen["login"] = imaplib.Debug

    def select(self, *_args, **_kwargs):
        self.seen["select"] = imaplib.Debug

    def noop(self):
        self.seen["noop"] = imaplib.Debug

    def logout(self):
        pass


def test_tracing_is_off_during_login_and_on_afterwards():
    created = []

    def _factory(*args, **kwargs):
        client = FakeIMAP(*args, **kwargs)
        created.append(client)
        return client

    before = imaplib.Debug
    try:
        with (
            patch("debug_imap.get_credentials", return_value=("imap.example.com", "993", "me@example.com", "hunter2")),
            patch("imaplib.IMAP4_SSL", _factory),
        ):
            debug_imap.test_with_imaplib_debug()

        client = created[0]
        assert client.seen["login"] == 0, "the password would have been echoed"
        assert client.seen["select"] == 4, "nothing after login would have been traced"
        assert imaplib.Debug == 0, "tracing must not leak out of the function"
    finally:
        imaplib.Debug = before
