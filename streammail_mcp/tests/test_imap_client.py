"""Tests for imap_client module."""

import email
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from contextlib import contextmanager

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from imap_client import (
    to_str,
    decode_header_value,
    parse_folder_path,
    format_address,
    format_address_list,
    get_credentials,
    list_folders,
    list_messages,
    read_message,
    search_messages,
    create_draft,
    modify_draft,
    IMAPError,
)
from conftest import MockIMAPClient, MockEnvelope, MockAddress


class TestToStr:
    """Tests for to_str utility function."""

    def test_bytes_to_str(self):
        """Test bytes conversion."""
        assert to_str(b"hello") == "hello"

    def test_str_passthrough(self):
        """Test string passthrough."""
        assert to_str("hello") == "hello"

    def test_none_returns_empty(self):
        """Test None returns empty string."""
        assert to_str(None) == ""

    def test_bytes_with_invalid_utf8(self):
        """Test bytes with invalid UTF-8 uses replace."""
        result = to_str(b'\xff\xfe')
        assert isinstance(result, str)

    def test_int_to_str(self):
        """Test int conversion."""
        assert to_str(123) == "123"


class TestGetCredentials:
    """Tests for get_credentials function.

    Verifies keychain priority over env vars (keychain is primary).
    """

    @patch('imap_client.keyring.get_password')
    def test_keychain_takes_priority(self, mock_keyring, monkeypatch):
        """Keychain credentials should be used when available."""
        # Set env vars (should be ignored when keychain has credentials)
        monkeypatch.setenv("STREAMMAIL_IMAP_SERVER", "env.server.com")
        monkeypatch.setenv("STREAMMAIL_IMAP_PORT", "143")
        monkeypatch.setenv("STREAMMAIL_IMAP_USERNAME", "envuser")
        monkeypatch.setenv("STREAMMAIL_IMAP_PASSWORD", "envpass")

        # Mock keyring to return credentials
        mock_keyring.side_effect = lambda service, key: {
            "imap_server": "keychain.server.com",
            "imap_port": "993",
            "imap_username": "keychainuser",
            "imap_password": "keychainpass",
        }.get(key)

        server, port, username, password = get_credentials()

        # Keychain should take priority
        assert server == "keychain.server.com"
        assert port == "993"
        assert username == "keychainuser"
        assert password == "keychainpass"

    @patch('imap_client.keyring.get_password')
    def test_default_port_when_not_set(self, mock_keyring, monkeypatch):
        """Default port should be 993 when not specified."""
        # Clear env vars
        monkeypatch.delenv("STREAMMAIL_IMAP_SERVER", raising=False)
        monkeypatch.delenv("STREAMMAIL_IMAP_PORT", raising=False)
        monkeypatch.delenv("STREAMMAIL_IMAP_USERNAME", raising=False)
        monkeypatch.delenv("STREAMMAIL_IMAP_PASSWORD", raising=False)

        # Mock keyring - no port set
        mock_keyring.side_effect = lambda service, key: {
            "imap_server": "server.com",
            "imap_username": "user",
            "imap_password": "pass",
        }.get(key)

        server, port, username, password = get_credentials()

        assert port == "993"

    @patch('imap_client.keyring.get_password')
    def test_falls_back_to_env_vars(self, mock_keyring, monkeypatch):
        """Should fall back to env vars when keychain not configured."""
        # Set env vars
        monkeypatch.setenv("STREAMMAIL_IMAP_SERVER", "env.server.com")
        monkeypatch.setenv("STREAMMAIL_IMAP_PORT", "143")
        monkeypatch.setenv("STREAMMAIL_IMAP_USERNAME", "envuser")
        monkeypatch.setenv("STREAMMAIL_IMAP_PASSWORD", "envpass")

        # Mock keyring to return None (not configured)
        mock_keyring.return_value = None

        server, port, username, password = get_credentials()

        assert server == "env.server.com"
        assert port == "143"
        assert username == "envuser"
        assert password == "envpass"

    @patch('imap_client.keyring.get_password')
    def test_raises_when_not_configured(self, mock_keyring, monkeypatch):
        """Should raise IMAPError when no credentials available."""
        # Clear env vars
        monkeypatch.delenv("STREAMMAIL_IMAP_SERVER", raising=False)
        monkeypatch.delenv("STREAMMAIL_IMAP_USERNAME", raising=False)
        monkeypatch.delenv("STREAMMAIL_IMAP_PASSWORD", raising=False)

        # Mock keyring returning None
        mock_keyring.return_value = None

        with pytest.raises(IMAPError, match="not configured"):
            get_credentials()


class TestDecodeHeaderValue:
    """Tests for decode_header_value utility function."""

    def test_plain_string(self):
        """Test plain ASCII string."""
        assert decode_header_value("Hello World") == "Hello World"

    def test_bytes_input(self):
        """Test bytes input."""
        assert decode_header_value(b"Hello World") == "Hello World"

    def test_empty_string(self):
        """Test empty string."""
        assert decode_header_value("") == ""

    def test_none(self):
        """Test None."""
        assert decode_header_value(None) == ""

    def test_mime_encoded_utf8(self):
        """Test MIME-encoded UTF-8 header."""
        # =?UTF-8?B?...?= format
        encoded = "=?UTF-8?B?SGVsbG8gV29ybGQ=?="  # "Hello World" in base64
        assert decode_header_value(encoded) == "Hello World"

    def test_mime_encoded_iso(self):
        """Test MIME-encoded ISO-8859-1 header."""
        encoded = "=?ISO-8859-1?Q?Caf=E9?="  # "Café"
        assert decode_header_value(encoded) == "Café"


class TestFormatAddress:
    """Tests for format_address utility function.

    TDD: Extracts duplicate address formatting from list_messages,
    read_message, and search_messages.
    """

    def test_with_name_and_email(self):
        """Test address with display name."""
        addr = MockAddress(name=b"John Doe", mailbox=b"john", host=b"example.com")
        result = format_address(addr)
        assert result == "John Doe <john@example.com>"

    def test_email_only(self):
        """Test address without display name."""
        addr = MockAddress(name=None, mailbox=b"john", host=b"example.com")
        result = format_address(addr)
        assert result == "john@example.com"

    def test_mime_encoded_name(self):
        """Test address with MIME-encoded name."""
        addr = MockAddress(
            name=b"=?UTF-8?B?SGVsbG8gV29ybGQ=?=",  # "Hello World"
            mailbox=b"hello",
            host=b"example.com"
        )
        result = format_address(addr)
        assert result == "Hello World <hello@example.com>"

    def test_empty_name(self):
        """Test address with empty name bytes."""
        addr = MockAddress(name=b"", mailbox=b"user", host=b"domain.com")
        result = format_address(addr)
        assert result == "user@domain.com"


class TestFormatAddressList:
    """Tests for format_address_list utility function."""

    def test_single_address(self):
        """Test list with single address."""
        addrs = [MockAddress(name=b"John", mailbox=b"john", host=b"example.com")]
        result = format_address_list(addrs)
        assert result == ["John <john@example.com>"]

    def test_multiple_addresses(self):
        """Test list with multiple addresses."""
        addrs = [
            MockAddress(name=b"John", mailbox=b"john", host=b"example.com"),
            MockAddress(name=None, mailbox=b"jane", host=b"example.com"),
        ]
        result = format_address_list(addrs)
        assert result == ["John <john@example.com>", "jane@example.com"]

    def test_empty_list(self):
        """Test empty address list."""
        result = format_address_list([])
        assert result == []

    def test_none_list(self):
        """Test None address list."""
        result = format_address_list(None)
        assert result == []


class TestParseFolderPath:
    """Tests for parse_folder_path utility function."""

    def test_imap_url_simple(self):
        """Test simple IMAP URL."""
        url = "imap://user@server/INBOX"
        assert parse_folder_path(url) == "INBOX"

    def test_imap_url_subfolder(self):
        """Test IMAP URL with subfolder."""
        url = "imap://user@server/INBOX/Subfolder/Deep"
        assert parse_folder_path(url) == "INBOX/Subfolder/Deep"

    def test_plain_path(self):
        """Test plain folder path (no URL)."""
        assert parse_folder_path("INBOX") == "INBOX"
        assert parse_folder_path("Drafts") == "Drafts"

    def test_plain_subfolder(self):
        """Test plain subfolder path."""
        assert parse_folder_path("INBOX/Projects") == "INBOX/Projects"

    def test_invalid_url_raises(self):
        """Test invalid URL raises error."""
        with pytest.raises(IMAPError):
            parse_folder_path("http://not-imap/folder")


class TestListFolders:
    """Tests for list_folders function."""

    @patch('imap_client.imap_connection')
    def test_list_folders_basic(self, mock_conn):
        """Test basic folder listing."""
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = list_folders()

        assert len(result) == 3
        assert result[0]["name"] == "INBOX"
        assert result[1]["name"] == "Drafts"


class TestListMessages:
    """Tests for list_messages function."""

    @patch('imap_client.imap_connection')
    def test_list_empty_folder(self, mock_conn):
        """Test listing empty folder."""
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = list_messages("INBOX", limit=20)

        assert result == []

    @patch('imap_client.imap_connection')
    def test_list_messages_with_content(self, mock_conn, sample_envelope):
        """Test listing folder with messages."""
        mock_client = MockIMAPClient()
        mock_client.add_message("INBOX", 1, sample_envelope)
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = list_messages("INBOX", limit=20)

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["subject"] == "Test Email Subject"

    @patch('imap_client.imap_connection')
    def test_list_messages_folder_not_found(self, mock_conn):
        """Test listing non-existent folder."""
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(IMAPError, match="Cannot open folder"):
            list_messages("NonExistent", limit=20)


class TestReadMessage:
    """Tests for read_message function."""

    @patch('imap_client.imap_connection')
    def test_read_message_not_found(self, mock_conn):
        """Test reading non-existent message."""
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(IMAPError, match="not found"):
            read_message("INBOX", 999)

    @patch('imap_client.imap_connection')
    def test_read_message_basic(self, mock_conn, sample_envelope, sample_raw_email):
        """Test reading a basic message."""
        mock_client = MockIMAPClient()
        mock_client.add_message(
            "INBOX", 1, sample_envelope,
            body_text="This is the email body.",
            raw_email=sample_raw_email
        )
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = read_message("INBOX", 1)

        assert result["id"] == 1
        assert result["subject"] == "Test Email Subject"
        assert "This is the email body." in result["body_text"]


class TestSearchMessages:
    """Tests for search_messages function."""

    @patch('imap_client.imap_connection')
    def test_search_no_results(self, mock_conn):
        """Test search with no results."""
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = search_messages("INBOX", "nonexistent")

        assert result == []


class TestCreateDraft:
    """Tests for create_draft function."""

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_create_draft_basic(self, mock_creds, mock_conn):
        """Test creating a basic draft."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = create_draft(
            folder="INBOX",
            to="recipient@example.com",
            subject="Test Subject",
            body="Test body content"
        )

        assert result["status"] == "created"
        assert result["to"] == "recipient@example.com"
        assert result["subject"] == "Test Subject"
        assert result["folder"] == "Drafts"

        # Verify draft was appended
        assert len(mock_client.appended_messages) == 1
        appended = mock_client.appended_messages[0]
        assert appended["folder"] == "Drafts"
        assert b"Test Subject" in appended["message"]
        assert b"Test body content" in appended["message"]

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_create_draft_with_html(self, mock_creds, mock_conn):
        """Test creating a draft with HTML content."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = create_draft(
            folder="INBOX",
            to="recipient@example.com",
            subject="HTML Test",
            body="Plain text body",
            html="<html><body><p>HTML body</p></body></html>"
        )

        assert result["status"] == "created"

        # Verify HTML was included
        appended = mock_client.appended_messages[0]
        assert b"multipart/alternative" in appended["message"]
        assert b"text/plain" in appended["message"]
        assert b"text/html" in appended["message"]
        assert b"<html>" in appended["message"]

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_create_draft_with_reply(self, mock_creds, mock_conn):
        """Test creating a draft reply with In-Reply-To."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = create_draft(
            folder="INBOX",
            to="recipient@example.com",
            subject="Re: Original",
            body="Reply content",
            in_reply_to="<original@example.com>"
        )

        assert result["status"] == "created"

        # Verify In-Reply-To and References were added
        appended = mock_client.appended_messages[0]
        assert b"In-Reply-To: <original@example.com>" in appended["message"]
        assert b"References: <original@example.com>" in appended["message"]

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_create_draft_with_cc(self, mock_creds, mock_conn):
        """Test creating a draft with CC."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = create_draft(
            folder="INBOX",
            to="recipient@example.com",
            subject="Test with CC",
            body="Body",
            cc="cc1@example.com, cc2@example.com"
        )

        assert result["status"] == "created"

        appended = mock_client.appended_messages[0]
        assert b"Cc: cc1@example.com, cc2@example.com" in appended["message"]


class TestModifyDraft:
    """Tests for modify_draft function."""

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_modify_draft_not_found(self, mock_creds, mock_conn):
        """Test modifying non-existent draft."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(IMAPError, match="not found"):
            modify_draft("Drafts", 999, body="New body")

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_modify_draft_basic(self, mock_creds, mock_conn):
        """Test modifying a draft with new body."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        # Create original draft in mock
        original_email = b"""From: user@example.com
To: recipient@example.com
Subject: Original Subject
Message-ID: <original@example.com>

Original body content.
"""
        envelope = MockEnvelope(
            subject=b"Original Subject",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"recipient", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=original_email)

        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = modify_draft("Drafts", 1, body="Updated body content")

        assert result["status"] == "modified"
        assert result["subject"] == "Original Subject"
        assert result["to"] == "recipient@example.com"

        # Verify old draft was deleted
        assert 1 in mock_client.deleted_messages

        # Verify new draft was appended
        assert len(mock_client.appended_messages) == 1
        appended = mock_client.appended_messages[0]
        assert b"Updated body content" in appended["message"]

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_modify_draft_preserve_reply_threading(self, mock_creds, mock_conn):
        """Test modifying draft preserves In-Reply-To and References."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        # Create original draft with reply threading
        original_email = b"""From: user@example.com
To: recipient@example.com
Subject: Re: Original Thread
Message-ID: <reply@example.com>
In-Reply-To: <thread@example.com>
References: <thread@example.com>

Reply body.
"""
        envelope = MockEnvelope(
            subject=b"Re: Original Thread",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"recipient", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=original_email)

        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = modify_draft("Drafts", 1, body="Updated reply")

        assert result["preserved_reply_to"] is True

        # Verify threading was preserved
        appended = mock_client.appended_messages[0]
        assert b"In-Reply-To: <thread@example.com>" in appended["message"]
        assert b"References: <thread@example.com>" in appended["message"]

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_modify_draft_change_subject(self, mock_creds, mock_conn):
        """Test modifying draft with new subject."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        original_email = b"""From: user@example.com
To: recipient@example.com
Subject: Old Subject
Message-ID: <original@example.com>

Body.
"""
        envelope = MockEnvelope(
            subject=b"Old Subject",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"recipient", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=original_email)

        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = modify_draft("Drafts", 1, body="New body", subject="New Subject")

        assert result["subject"] == "New Subject"

        appended = mock_client.appended_messages[0]
        assert b"Subject: New Subject" in appended["message"]

    @patch('imap_client.imap_connection')
    @patch('imap_client.get_credentials')
    def test_modify_draft_with_html(self, mock_creds, mock_conn):
        """Test modifying draft with HTML content."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        original_email = b"""From: user@example.com
To: recipient@example.com
Subject: Test
Message-ID: <original@example.com>

Plain text.
"""
        envelope = MockEnvelope(
            subject=b"Test",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"recipient", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=original_email)

        mock_conn.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_conn.return_value.__exit__ = MagicMock(return_value=False)

        result = modify_draft(
            "Drafts", 1,
            body="Plain text",
            html="<p><strong>Bold</strong> text</p>"
        )

        assert result["status"] == "modified"

        appended = mock_client.appended_messages[0]
        assert b"multipart/alternative" in appended["message"]
        assert b"<strong>Bold</strong>" in appended["message"]
