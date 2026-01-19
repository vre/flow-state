"""Pytest configuration and shared fixtures for streammail tests."""

import sys
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from contextlib import contextmanager
import pytest

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class MockEnvelope:
    """Mock IMAP envelope."""
    subject: bytes = b"Test Subject"
    from_: list = field(default_factory=list)
    to: list = field(default_factory=list)
    cc: list = field(default_factory=list)
    date: Any = None
    message_id: bytes = b"<test@example.com>"
    in_reply_to: Optional[bytes] = None


@dataclass
class MockAddress:
    """Mock email address."""
    name: Optional[bytes] = None
    mailbox: bytes = b"test"
    host: bytes = b"example.com"


class MockIMAPClient:
    """Mock IMAP client for testing."""

    def __init__(self):
        self.folders: dict[str, list[dict]] = {
            "INBOX": [],
            "Drafts": [],
        }
        self.selected_folder: Optional[str] = None
        self.logged_in: bool = False
        self.appended_messages: list[dict] = []
        self.deleted_messages: list[int] = []

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

        for msg_id in message_ids:
            for msg in messages:
                if msg["id"] == msg_id:
                    result[msg_id] = msg.get("data", {})
                    break

        return result

    def append(self, folder: str, message: bytes, flags: list[bytes] = None) -> int:
        """Append message to folder."""
        msg_id = len(self.folders.get(folder, [])) + 1
        self.appended_messages.append({
            "folder": folder,
            "message": message,
            "flags": flags or [],
            "id": msg_id,
        })
        return msg_id

    def delete_messages(self, message_ids: list[int]):
        """Mark messages for deletion."""
        self.deleted_messages.extend(message_ids)

    def expunge(self):
        """Expunge deleted messages."""
        pass

    # Helper methods for tests
    def add_message(self, folder: str, msg_id: int, envelope: MockEnvelope,
                    body_text: str = "", body_html: str = "", flags: list = None,
                    raw_email: bytes = None):
        """Add a message to a folder for testing."""
        if folder not in self.folders:
            self.folders[folder] = []

        if raw_email is None:
            raw_email = f"Subject: {envelope.subject.decode()}\r\n\r\n{body_text}".encode()

        self.folders[folder].append({
            "id": msg_id,
            "data": {
                b"ENVELOPE": envelope,
                b"FLAGS": flags or [],
                b"RFC822.SIZE": len(raw_email),
                b"RFC822": raw_email,
            }
        })


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
