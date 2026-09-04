"""Pytest configuration and shared fixtures for streammail tests."""

import socket
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

# Add imap-slim-mcp directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim-mcp"))

from imapclient import IMAPClient  # noqa: E402  (needs the path insert above)

# Short socket timeout for the fake-server tests: production uses 30s, and the
# point of these tests is that no blocking command is sent at all.
SILENT_SERVER_TIMEOUT = 3


@dataclass
class MockEnvelope:
    """Mock IMAP envelope."""

    subject: bytes = b"Test Subject"
    from_: list = field(default_factory=list)
    to: list = field(default_factory=list)
    cc: list = field(default_factory=list)
    date: Any = None
    message_id: bytes = b"<test@example.com>"
    in_reply_to: bytes | None = None


@dataclass
class MockAddress:
    """Mock email address."""

    name: bytes | None = None
    mailbox: bytes = b"test"
    host: bytes = b"example.com"


SIMPLE_TEXT_BODYSTRUCTURE = (
    b"TEXT",
    b"PLAIN",
    (b"CHARSET", b"utf-8"),
    None,
    None,
    b"7BIT",
    100,
    5,
    None,
    None,
    None,
    None,
)


class MockIMAPClient:
    """Mock IMAP client for testing."""

    def __init__(self):
        self.folders: dict[str, list[dict]] = {
            "INBOX": [],
            "Drafts": [],
        }
        self.selected_folder: str | None = None
        self.logged_in: bool = False
        self.appended_messages: list[dict] = []
        self.deleted_messages: list[int] = []
        self.noop_count: int = 0
        self.shutdown_count: int = 0

    def noop(self):
        """Liveness probe. Silent success means the connection is reusable."""
        self.noop_count += 1

    def shutdown(self):
        """Non-graceful close: drops the socket without sending LOGOUT."""
        self.shutdown_count += 1
        self.logged_in = False

    def login(self, username: str, password: str):
        """Mock login."""
        self.logged_in = True

    def logout(self):
        """Mock logout."""
        self.logged_in = False

    def list_folders(self) -> list[tuple]:
        """Return mock folder list."""
        return [
            ([b"\\HasNoChildren"], b"/", "INBOX"),
            ([b"\\Drafts"], b"/", "Drafts"),
            ([b"\\Sent"], b"/", "Sent"),
        ]

    def select_folder(self, folder: str, readonly: bool = False):
        """Select a folder."""
        if folder not in self.folders:
            raise Exception(f"Folder '{folder}' not found")
        self.selected_folder = folder
        messages = self.folders.get(folder, [])
        return {
            b"UIDVALIDITY": 1,
            b"UIDNEXT": len(messages) + 1,
            b"EXISTS": len(messages),
        }

    def search(self, criteria: list) -> list[int]:
        """Return message IDs matching criteria."""
        if self.selected_folder is None:
            return []
        messages = self.folders.get(self.selected_folder, [])
        return [msg["id"] for msg in messages]

    def fetch(self, message_ids: list[int], data: list[str]) -> dict:
        """Fetch message data."""
        if self.selected_folder is None:
            return {}

        messages = self.folders.get(self.selected_folder, [])
        result = {}
        body_peek_section = None
        for selector in data:
            selector_text = selector.decode() if isinstance(selector, bytes) else selector
            if not selector_text.startswith("BODY.PEEK["):
                continue
            start = selector_text.find("[")
            end = selector_text.find("]", start + 1)
            if start != -1 and end != -1:
                body_peek_section = selector_text[start + 1 : end]
                break

        for msg_id in message_ids:
            for msg in messages:
                if msg["id"] == msg_id:
                    if body_peek_section is not None:
                        snippet_body = msg.get("snippet_body")
                        snippet_section = msg.get("snippet_section", "1")
                        if snippet_body is not None and snippet_section == body_peek_section:
                            key_variant = msg.get("snippet_key_variant", "<0>")
                            if key_variant == "<0.600>":
                                response_key = f"BODY[{body_peek_section}]<0.600>"
                            elif key_variant == "bare":
                                response_key = f"BODY[{body_peek_section}]"
                            else:
                                response_key = f"BODY[{body_peek_section}]<0>"
                            result[msg_id] = {response_key.encode(): snippet_body}
                        else:
                            result[msg_id] = {}
                    else:
                        msg_data = msg.get("data", {})
                        filtered = {}
                        for selector in data:
                            selector_key = selector.encode() if isinstance(selector, str) else selector
                            if selector_key in msg_data:
                                filtered[selector_key] = msg_data[selector_key]
                        result[msg_id] = filtered if filtered else msg_data
                    break

        return result

    def append(self, folder: str, message: bytes, flags: list[bytes] = None) -> int:
        """Append message to folder."""
        msg_id = len(self.folders.get(folder, [])) + 1
        self.appended_messages.append(
            {
                "folder": folder,
                "message": message,
                "flags": flags or [],
                "id": msg_id,
            }
        )
        return msg_id

    def delete_messages(self, message_ids: list[int]):
        """Mark messages for deletion."""
        self.deleted_messages.extend(message_ids)

    def expunge(self):
        """Expunge deleted messages."""
        pass

    # Helper methods for tests
    def add_message(
        self,
        folder: str,
        msg_id: int,
        envelope: MockEnvelope,
        body_text: str = "",
        body_html: str = "",
        flags: list = None,
        raw_email: bytes = None,
        bodystructure: tuple | None = SIMPLE_TEXT_BODYSTRUCTURE,
        snippet_body: bytes | str | None = None,
        snippet_section: str = "1",
        snippet_key_variant: str = "<0>",
    ):
        """Add a message to a folder for testing."""
        if folder not in self.folders:
            self.folders[folder] = []

        if raw_email is None:
            raw_email = f"Subject: {envelope.subject.decode()}\r\n\r\n{body_text}".encode()

        data = {
            b"ENVELOPE": envelope,
            b"FLAGS": flags or [],
            b"RFC822.SIZE": len(raw_email),
            b"RFC822": raw_email,
        }
        if bodystructure is not None:
            data[b"BODYSTRUCTURE"] = bodystructure

        normalized_snippet = snippet_body.encode() if isinstance(snippet_body, str) else snippet_body
        self.folders[folder].append(
            {
                "id": msg_id,
                "data": data,
                "snippet_body": normalized_snippet,
                "snippet_section": snippet_section,
                "snippet_key_variant": snippet_key_variant,
            }
        )


@pytest.fixture
def mock_imap():
    """Provide mock IMAP client."""
    return MockIMAPClient()


@pytest.fixture
def mock_credentials(monkeypatch):
    """Mock keyring credentials."""

    def mock_get_password(service, key):
        creds = {
            "accounts": '["default"]',
            "default_account": "default",
            "default:imap_server": "mail.example.com",
            "default:imap_port": "993",
            "default:imap_username": "testuser",
            "default:imap_password": "testpass",
        }
        return creds.get(key)

    monkeypatch.setattr("keyring.get_password", mock_get_password)


@pytest.fixture
def sample_envelope():
    """Sample email envelope."""
    return MockEnvelope(
        subject=b"Test Email Subject",
        from_=[MockAddress(name=b"Sender Name", mailbox=b"sender", host=b"example.com")],
        to=[MockAddress(name=b"Recipient", mailbox=b"recipient", host=b"example.com")],
        cc=[],
        message_id=b"<unique-id@example.com>",
        in_reply_to=None,
    )


@pytest.fixture
def sample_raw_email():
    """Sample raw email content."""
    return b"""MIME-Version: 1.0
From: sender@example.com
To: recipient@example.com
Subject: Test Email
Content-Type: text/plain; charset=utf-8

This is the email body.
"""


@pytest.fixture
def sample_multipart_email():
    """Sample multipart email with HTML and plain text."""
    return b"""MIME-Version: 1.0
From: sender@example.com
To: recipient@example.com
Subject: Test Multipart Email
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset=utf-8

Plain text body.

--boundary123
Content-Type: text/html; charset=utf-8

<html><body><p>HTML body.</p></body></html>

--boundary123--
"""


class SilentIMAPServer:
    """Fake IMAP server that completes LOGIN then goes permanently silent.

    Models an idle-reaped connection: the socket stays open, the server never
    answers again. Records every command line it receives so tests can assert
    on what was actually sent rather than only on elapsed time.
    """

    def __init__(self):
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self.port = self._sock.getsockname()[1]
        self.commands: list[str] = []
        self.ready = threading.Event()
        self._conns: list[socket.socket] = []
        self._stop = False
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        self.ready.set()
        while not self._stop:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            self._conns.append(conn)
            threading.Thread(target=self._session, args=(conn,), daemon=True).start()

    def _session(self, conn):
        try:
            handle = conn.makefile("rwb")
            conn.sendall(b"* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] fake ready\r\n")
            while True:
                line = handle.readline()
                if not line:
                    return
                text = line.decode("utf-8", "replace").strip()
                self.commands.append(text)
                tag = line.split(b" ", 1)[0]
                upper = line.upper()
                if b"CAPABILITY" in upper:
                    conn.sendall(b"* CAPABILITY IMAP4rev1\r\n" + tag + b" OK done\r\n")
                elif b"LOGIN" in upper:
                    conn.sendall(tag + b" OK LOGIN completed\r\n")
                    return  # from here on: silence, socket stays open
        except OSError:
            return

    def received(self, verb: str) -> bool:
        """True if any received command line contains the given IMAP verb."""
        return any(verb.upper() in c.upper() for c in self.commands)

    def close(self):
        self._stop = True
        for conn in self._conns:
            try:
                conn.close()
            except OSError:
                pass
        try:
            self._sock.close()
        except OSError:
            pass
        self._thread.join(timeout=2)


@pytest.fixture
def silent_imap_server():
    """A server that logs in then stops responding. Yields the server object."""
    server = SilentIMAPServer()
    server.ready.wait(timeout=5)
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def connected_to_silent(silent_imap_server):
    """Factory building real IMAPClients logged into the silent server."""
    clients = []

    def build():
        client = IMAPClient("127.0.0.1", port=silent_imap_server.port, ssl=False, timeout=SILENT_SERVER_TIMEOUT)
        client.login("u", "p")
        clients.append(client)
        return client

    try:
        yield silent_imap_server, build
    finally:
        for client in clients:
            try:
                client.shutdown()
            except Exception:
                pass
