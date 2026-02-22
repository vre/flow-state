"""Tests for imap_client module."""

import email
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import session
from conftest import MockAddress, MockEnvelope, MockIMAPClient
from imap_client import (
    IMAPError,
    _attach_files,
    create_draft,
    decode_header_value,
    format_address,
    format_address_list,
    get_credentials,
    get_default_account,
    list_accounts,
    list_folders,
    list_messages,
    modify_draft,
    parse_folder_path,
    read_message,
    search_messages,
    to_str,
)


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
        result = to_str(b"\xff\xfe")
        assert isinstance(result, str)

    def test_int_to_str(self):
        """Test int conversion."""
        assert to_str(123) == "123"


class TestGetCredentials:
    """Tests for get_credentials function.

    Verifies keychain priority over env vars (keychain is primary).
    """

    @patch("imap_client.keyring.get_password")
    def test_keychain_takes_priority(self, mock_keyring, monkeypatch):
        """Keychain credentials should be used when available."""
        # Set env vars (should be ignored when keychain has credentials)
        monkeypatch.setenv("IMAP_STREAM_SERVER", "env.server.com")
        monkeypatch.setenv("IMAP_STREAM_PORT", "143")
        monkeypatch.setenv("IMAP_STREAM_USERNAME", "envuser")
        monkeypatch.setenv("IMAP_STREAM_PASSWORD", "envpass")

        # Mock keyring to return credentials with prefixed keys
        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["default"]',
            "default_account": "default",
            "default:imap_server": "keychain.server.com",
            "default:imap_port": "993",
            "default:imap_username": "keychainuser",
            "default:imap_password": "keychainpass",
        }.get(key)

        server, port, username, password = get_credentials()

        # Keychain should take priority
        assert server == "keychain.server.com"
        assert port == "993"
        assert username == "keychainuser"
        assert password == "keychainpass"

    @patch("imap_client.keyring.get_password")
    def test_default_port_when_not_set(self, mock_keyring, monkeypatch):
        """Default port should be 993 when not specified."""
        # Clear env vars
        monkeypatch.delenv("IMAP_STREAM_SERVER", raising=False)
        monkeypatch.delenv("IMAP_STREAM_PORT", raising=False)
        monkeypatch.delenv("IMAP_STREAM_USERNAME", raising=False)
        monkeypatch.delenv("IMAP_STREAM_PASSWORD", raising=False)

        # Mock keyring - no port set
        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["work"]',
            "default_account": "work",
            "work:imap_server": "server.com",
            "work:imap_username": "user",
            "work:imap_password": "pass",
        }.get(key)

        server, port, username, password = get_credentials()

        assert port == "993"

    @patch("imap_client.keyring.get_password")
    def test_falls_back_to_env_vars(self, mock_keyring, monkeypatch):
        """Should fall back to env vars when keychain not configured."""
        # Set env vars
        monkeypatch.setenv("IMAP_STREAM_SERVER", "env.server.com")
        monkeypatch.setenv("IMAP_STREAM_PORT", "143")
        monkeypatch.setenv("IMAP_STREAM_USERNAME", "envuser")
        monkeypatch.setenv("IMAP_STREAM_PASSWORD", "envpass")

        # Mock keyring to return None (not configured)
        mock_keyring.return_value = None

        server, port, username, password = get_credentials()

        assert server == "env.server.com"
        assert port == "143"
        assert username == "envuser"
        assert password == "envpass"

    @patch("imap_client.keyring.get_password")
    def test_raises_when_not_configured(self, mock_keyring, monkeypatch):
        """Should raise IMAPError when no credentials available."""
        # Clear env vars
        monkeypatch.delenv("IMAP_STREAM_SERVER", raising=False)
        monkeypatch.delenv("IMAP_STREAM_USERNAME", raising=False)
        monkeypatch.delenv("IMAP_STREAM_PASSWORD", raising=False)

        # Mock keyring returning None
        mock_keyring.return_value = None

        with pytest.raises(IMAPError, match="not configured"):
            get_credentials()

    @patch("imap_client.keyring.get_password")
    def test_multi_account_uses_prefixed_keys(self, mock_keyring, monkeypatch):
        """Should use account-prefixed keys for multi-account config."""
        monkeypatch.delenv("IMAP_STREAM_SERVER", raising=False)

        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["work", "personal"]',
            "default_account": "work",
            "work:imap_server": "mail.company.com",
            "work:imap_port": "993",
            "work:imap_username": "me@company.com",
            "work:imap_password": "workpass",
        }.get(key)

        server, port, username, password = get_credentials("work")

        assert server == "mail.company.com"
        assert port == "993"
        assert username == "me@company.com"
        assert password == "workpass"

    @patch("imap_client.keyring.get_password")
    def test_multi_account_default_when_no_account_specified(self, mock_keyring, monkeypatch):
        """Should use default account when account not specified."""
        monkeypatch.delenv("IMAP_STREAM_SERVER", raising=False)

        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["work", "personal"]',
            "default_account": "personal",
            "personal:imap_server": "imap.gmail.com",
            "personal:imap_port": "993",
            "personal:imap_username": "me@gmail.com",
            "personal:imap_password": "gmailpass",
        }.get(key)

        server, port, username, password = get_credentials()

        assert server == "imap.gmail.com"
        assert username == "me@gmail.com"
        assert password == "gmailpass"

    @patch("imap_client.keyring.get_password")
    def test_multi_account_nonexistent_raises(self, mock_keyring, monkeypatch):
        """Should raise error for nonexistent account."""
        monkeypatch.delenv("IMAP_STREAM_SERVER", raising=False)

        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["work"]',
            "default_account": "work",
        }.get(key)

        with pytest.raises(IMAPError, match="Account 'nonexistent' not found"):
            get_credentials("nonexistent")


class TestListAccounts:
    """Tests for list_accounts function."""

    @patch("imap_client.keyring.get_password")
    def test_returns_empty_list_when_no_accounts(self, mock_keyring):
        """Should return empty list when no accounts configured."""
        mock_keyring.return_value = None

        accounts = list_accounts()

        assert accounts == []

    @patch("imap_client.keyring.get_password")
    def test_returns_accounts_from_keychain(self, mock_keyring):
        """Should return list of account names from keychain."""
        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["work", "personal"]',
        }.get(key)

        accounts = list_accounts()

        assert accounts == ["work", "personal"]

    @patch("imap_client.keyring.get_password")
    def test_returns_single_account(self, mock_keyring):
        """Should handle single account."""
        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["default"]',
        }.get(key)

        accounts = list_accounts()

        assert accounts == ["default"]


class TestGetDefaultAccount:
    """Tests for get_default_account function."""

    @patch("imap_client.keyring.get_password")
    def test_returns_none_when_no_accounts(self, mock_keyring):
        """Should return None when no accounts configured."""
        mock_keyring.return_value = None

        default = get_default_account()

        assert default is None

    @patch("imap_client.keyring.get_password")
    def test_returns_default_account_from_keychain(self, mock_keyring):
        """Should return default account name from keychain."""
        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["work", "personal"]',
            "default_account": "work",
        }.get(key)

        default = get_default_account()

        assert default == "work"

    @patch("imap_client.keyring.get_password")
    def test_returns_first_account_when_no_default_set(self, mock_keyring):
        """Should return first account when no default explicitly set."""
        mock_keyring.side_effect = lambda service, key: {
            "accounts": '["personal", "work"]',
        }.get(key)

        default = get_default_account()

        assert default == "personal"


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
            host=b"example.com",
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

    @patch("session._create_connection")
    def test_list_folders_basic(self, mock_create):
        """Test basic folder listing."""
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client

        # Reset session cache
        session._sessions.clear()

        result = list_folders()

        assert len(result) == 3
        assert result[0]["name"] == "INBOX"
        assert result[1]["name"] == "Drafts"


class TestListMessages:
    """Tests for list_messages function."""

    @patch("session._create_connection")
    def test_list_empty_folder(self, mock_create):
        """Test listing empty folder."""
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        result = list_messages("INBOX", limit=20)

        assert result == []

    @patch("session._create_connection")
    def test_list_messages_with_content(self, mock_create, sample_envelope):
        """Test listing folder with messages."""
        mock_client = MockIMAPClient()
        mock_client.add_message("INBOX", 1, sample_envelope)
        mock_create.return_value = mock_client
        session._sessions.clear()

        result = list_messages("INBOX", limit=20)

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["subject"] == "Test Email Subject"

    @patch("session._create_connection")
    def test_list_messages_folder_not_found(self, mock_create):
        """Test listing non-existent folder."""
        mock_client = MockIMAPClient()
        # Mock select_folder to raise when folder doesn't exist
        # Wait, MockIMAPClient might not simulate this automatically?
        # In the original test, it just works?
        # IMAPClient usually raises if select fails.
        # I need to ensure MockIMAPClient behaves correctly or I configure it.
        # Original test didn't configure it.
        mock_create.return_value = mock_client
        session._sessions.clear()

        # Configure mock to raise error for select_folder("NonExistent")
        # Assuming MockIMAPClient implementation handles it, or we mock the method.
        # But MockIMAPClient probably mimics 'INBOX' and 'Drafts' only.

        # If I look at the failure, it was connecting to REAL server.
        # Now I am patching _create_connection, so it won't connect to real server.
        # But MockIMAPClient needs to simulate failure.

        with pytest.raises(IMAPError, match="Cannot open folder"):
            list_messages("NonExistent", limit=20)


class TestReadMessage:
    """Tests for read_message function."""

    @patch("session._create_connection")
    def test_read_message_not_found(self, mock_create):
        """Test reading non-existent message."""
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        with pytest.raises(IMAPError, match="not found"):
            read_message("INBOX", 999)

    @patch("session._create_connection")
    def test_read_message_basic(self, mock_create, sample_envelope, sample_raw_email):
        """Test reading a basic message."""
        mock_client = MockIMAPClient()
        mock_client.add_message("INBOX", 1, sample_envelope, body_text="This is the email body.", raw_email=sample_raw_email)
        mock_create.return_value = mock_client
        session._sessions.clear()

        result = read_message("INBOX", 1)

        assert result["id"] == 1
        assert result["subject"] == "Test Email Subject"
        assert "This is the email body." in result["body_text"]


class TestSearchMessages:
    """Tests for search_messages function."""

    @patch("session._create_connection")
    def test_search_no_results(self, mock_create):
        """Test search with no results."""
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        result = search_messages("INBOX", "nonexistent")

        assert result == []


class TestCreateDraft:
    """Tests for create_draft function."""

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_create_draft_basic(self, mock_creds, mock_create):
        """Test creating a basic draft."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        result = create_draft(folder="INBOX", to="recipient@example.com", subject="Test Subject", body="Test body content")

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

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_create_draft_with_html(self, mock_creds, mock_create):
        """Test creating a draft with HTML content."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        result = create_draft(
            folder="INBOX",
            to="recipient@example.com",
            subject="HTML Test",
            body="Plain text body",
            html="<html><body><p>HTML body</p></body></html>",
        )

        assert result["status"] == "created"

        # Verify HTML was included
        appended = mock_client.appended_messages[0]
        assert b"multipart/alternative" in appended["message"]
        assert b"text/plain" in appended["message"]
        assert b"text/html" in appended["message"]
        assert b"<html>" in appended["message"]

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_create_draft_with_reply(self, mock_creds, mock_create):
        """Test creating a draft reply with In-Reply-To."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        result = create_draft(
            folder="INBOX", to="recipient@example.com", subject="Re: Original", body="Reply content", in_reply_to="<original@example.com>"
        )

        assert result["status"] == "created"

        # Verify In-Reply-To and References were added
        appended = mock_client.appended_messages[0]
        assert b"In-Reply-To: <original@example.com>" in appended["message"]
        assert b"References: <original@example.com>" in appended["message"]

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_create_draft_with_cc(self, mock_creds, mock_create):
        """Test creating a draft with CC."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        result = create_draft(
            folder="INBOX", to="recipient@example.com", subject="Test with CC", body="Body", cc="cc1@example.com, cc2@example.com"
        )

        assert result["status"] == "created"

        appended = mock_client.appended_messages[0]
        assert b"Cc: cc1@example.com, cc2@example.com" in appended["message"]


class TestModifyDraft:
    """Tests for modify_draft function."""

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_draft_not_found(self, mock_creds, mock_create):
        """Test modifying non-existent draft."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        with pytest.raises(IMAPError, match="not found"):
            modify_draft("Drafts", 999, body="New body")

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_draft_basic(self, mock_creds, mock_create):
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

        mock_create.return_value = mock_client
        session._sessions.clear()

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

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_draft_preserve_reply_threading(self, mock_creds, mock_create):
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

        mock_create.return_value = mock_client
        session._sessions.clear()

        result = modify_draft("Drafts", 1, body="Updated reply")

        assert result["preserved_reply_to"] is True

        # Verify threading was preserved
        appended = mock_client.appended_messages[0]
        assert b"In-Reply-To: <thread@example.com>" in appended["message"]
        assert b"References: <thread@example.com>" in appended["message"]

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_draft_change_subject(self, mock_creds, mock_create):
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

        mock_create.return_value = mock_client
        session._sessions.clear()

        result = modify_draft("Drafts", 1, body="New body", subject="New Subject")

        assert result["subject"] == "New Subject"

        appended = mock_client.appended_messages[0]
        assert b"Subject: New Subject" in appended["message"]

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_draft_with_html(self, mock_creds, mock_create):
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

        mock_create.return_value = mock_client
        session._sessions.clear()

        result = modify_draft("Drafts", 1, body="Plain text", html="<p><strong>Bold</strong> text</p>")

        assert result["status"] == "modified"

        appended = mock_client.appended_messages[0]
        assert b"multipart/alternative" in appended["message"]
        assert b"<strong>Bold</strong>" in appended["message"]


class TestAttachFiles:
    """Tests for _attach_files helper."""

    def test_single_pdf_attachment(self, tmp_path):
        """Attach a PDF file — correct MIME type."""
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake content")

        msg = email.message.EmailMessage()
        msg.set_content("body")
        result = _attach_files(msg, [str(pdf)])

        assert len(result) == 1
        assert result[0]["name"] == "report.pdf"
        assert result[0]["size"] == pdf.stat().st_size
        # Verify MIME structure
        parts = list(msg.walk())
        att_part = [p for p in parts if p.get_content_disposition() == "attachment"]
        assert len(att_part) == 1
        assert att_part[0].get_content_type() == "application/pdf"

    def test_unknown_extension_falls_back_to_octet_stream(self, tmp_path):
        """Unknown extension → application/octet-stream."""
        f = tmp_path / "data.xyz123"
        f.write_bytes(b"unknown data")

        msg = email.message.EmailMessage()
        msg.set_content("body")
        _attach_files(msg, [str(f)])

        parts = list(msg.walk())
        att_part = [p for p in parts if p.get_content_disposition() == "attachment"]
        assert att_part[0].get_content_type() == "application/octet-stream"

    def test_multiple_attachments(self, tmp_path):
        """Multiple files attached in order."""
        f1 = tmp_path / "a.txt"
        f1.write_text("text content")
        f2 = tmp_path / "b.png"
        f2.write_bytes(b"\x89PNG fake")

        msg = email.message.EmailMessage()
        msg.set_content("body")
        result = _attach_files(msg, [str(f1), str(f2)])

        assert len(result) == 2
        assert result[0]["name"] == "a.txt"
        assert result[1]["name"] == "b.png"

    def test_missing_file_raises(self, tmp_path):
        """Missing file → IMAPError."""
        msg = email.message.EmailMessage()
        msg.set_content("body")

        with pytest.raises(IMAPError, match="not found"):
            _attach_files(msg, [str(tmp_path / "nonexistent.pdf")])

    def test_relative_path_rejected(self, tmp_path):
        """Relative path → IMAPError."""
        f = tmp_path / "file.txt"
        f.write_text("content")

        msg = email.message.EmailMessage()
        msg.set_content("body")

        with pytest.raises(IMAPError, match="absolute"):
            _attach_files(msg, ["relative/file.txt"])

    def test_directory_rejected(self, tmp_path):
        """Directory path → IMAPError."""
        msg = email.message.EmailMessage()
        msg.set_content("body")

        with pytest.raises(IMAPError, match="not a file"):
            _attach_files(msg, [str(tmp_path)])

    def test_oversize_file_rejected(self, tmp_path):
        """File >25 MB → IMAPError with size info."""
        big = tmp_path / "huge.bin"
        big.write_bytes(b"x" * (25 * 1024 * 1024 + 1))

        msg = email.message.EmailMessage()
        msg.set_content("body")

        with pytest.raises(IMAPError, match="too large"):
            _attach_files(msg, [str(big)])

    def test_fail_fast_no_message_modification(self, tmp_path):
        """If second file is invalid, message is not modified at all."""
        good = tmp_path / "ok.txt"
        good.write_text("fine")

        msg = email.message.EmailMessage()
        msg.set_content("body")

        with pytest.raises(IMAPError):
            _attach_files(msg, [str(good), str(tmp_path / "missing.txt")])

        # Message should have no attachments
        parts = list(msg.walk())
        att_parts = [p for p in parts if p.get_content_disposition() == "attachment"]
        assert len(att_parts) == 0

    def test_unreadable_file_raises_imap_error(self, tmp_path):
        """Permission error → IMAPError, not raw OSError."""
        f = tmp_path / "secret.txt"
        f.write_text("content")
        f.chmod(0o000)

        msg = email.message.EmailMessage()
        msg.set_content("body")

        try:
            with pytest.raises(IMAPError, match="Cannot read"):
                _attach_files(msg, [str(f)])
        finally:
            f.chmod(0o644)


class TestCreateDraftWithAttachments:
    """Tests for create_draft with file attachments."""

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_single_attachment(self, mock_creds, mock_create, tmp_path):
        """Draft with attachment → multipart/mixed."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF-1.4 test")

        result = create_draft(
            folder="INBOX",
            to="r@example.com",
            subject="See attached",
            body="Here is the file",
            attachments=[str(pdf)],
        )

        assert result["status"] == "created"
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["name"] == "doc.pdf"

        appended = mock_client.appended_messages[0]
        parsed = email.message_from_bytes(appended["message"])
        assert parsed.is_multipart()
        att_parts = [p for p in parsed.walk() if p.get_content_disposition() == "attachment"]
        assert len(att_parts) == 1

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_plain_text_plus_attachment_is_multipart_mixed(self, mock_creds, mock_create, tmp_path):
        """Plain text (no HTML) + attachment → multipart/mixed, not multipart/alternative."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3")

        create_draft(
            folder="INBOX",
            to="r@example.com",
            subject="Data",
            body="Attached CSV",
            attachments=[str(f)],
        )

        appended = mock_client.appended_messages[0]
        parsed = email.message_from_bytes(appended["message"])
        assert parsed.get_content_type() == "multipart/mixed"

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_invalid_attachment_prevents_draft(self, mock_creds, mock_create):
        """Invalid file path → no draft created."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        with pytest.raises(IMAPError):
            create_draft(
                folder="INBOX",
                to="r@example.com",
                subject="Bad",
                body="body",
                attachments=["/nonexistent/file.pdf"],
            )

        assert len(mock_client.appended_messages) == 0


class TestModifyDraftWithAttachments:
    """Tests for modify_draft attachment handling."""

    def _make_multipart_draft(self):
        """Build a raw email with an existing attachment."""
        msg = email.message.EmailMessage()
        msg["From"] = "user@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Draft with file"
        msg["Message-ID"] = "<draft1@example.com>"
        msg["In-Reply-To"] = "<thread@example.com>"
        msg["References"] = "<thread@example.com>"
        msg.set_content("Original body")
        msg.add_attachment(
            b"existing PDF content",
            maintype="application",
            subtype="pdf",
            filename="existing.pdf",
        )
        return msg.as_bytes()

    def _make_inline_attachment_draft(self):
        """Build a raw email with an inline attachment (has filename)."""
        msg = email.message.EmailMessage()
        msg["From"] = "user@example.com"
        msg["To"] = "recipient@example.com"
        msg["Subject"] = "Draft with inline"
        msg["Message-ID"] = "<draft2@example.com>"
        msg.set_content("Body text")
        msg.add_attachment(
            b"inline image data",
            maintype="image",
            subtype="png",
            filename="screenshot.png",
        )
        # Change disposition to inline
        for part in msg.walk():
            if part.get_filename() == "screenshot.png":
                part.replace_header("Content-Disposition", 'inline; filename="screenshot.png"')
        return msg.as_bytes()

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_preserves_existing_attachments(self, mock_creds, mock_create):
        """Existing attachments should survive modify."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        raw = self._make_multipart_draft()
        envelope = MockEnvelope(
            subject=b"Draft with file",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"recipient", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=raw)
        mock_create.return_value = mock_client
        session._sessions.clear()

        modify_draft("Drafts", 1, body="Updated body")

        appended = mock_client.appended_messages[0]
        parsed = email.message_from_bytes(appended["message"])
        att_parts = [p for p in parsed.walk() if p.get_content_disposition() == "attachment"]
        assert len(att_parts) == 1
        assert att_parts[0].get_filename() == "existing.pdf"

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_preserves_inline_with_filename(self, mock_creds, mock_create):
        """Inline attachments with filename should be preserved."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        raw = self._make_inline_attachment_draft()
        envelope = MockEnvelope(
            subject=b"Draft with inline",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"recipient", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=raw)
        mock_create.return_value = mock_client
        session._sessions.clear()

        modify_draft("Drafts", 1, body="New body")

        appended = mock_client.appended_messages[0]
        parsed = email.message_from_bytes(appended["message"])
        # Should have the inline attachment preserved
        att_parts = [p for p in parsed.walk() if p.get_content_disposition() in ("attachment", "inline") and p.get_filename()]
        assert len(att_parts) == 1
        assert att_parts[0].get_filename() == "screenshot.png"

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_adds_new_attachment(self, mock_creds, mock_create, tmp_path):
        """Adding new attachments to existing draft."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        raw = self._make_multipart_draft()
        envelope = MockEnvelope(
            subject=b"Draft with file",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"recipient", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=raw)
        mock_create.return_value = mock_client
        session._sessions.clear()

        new_file = tmp_path / "extra.txt"
        new_file.write_text("extra content")

        modify_draft("Drafts", 1, body="Updated body", attachments=[str(new_file)])

        appended = mock_client.appended_messages[0]
        parsed = email.message_from_bytes(appended["message"])
        att_parts = [p for p in parsed.walk() if p.get_content_disposition() == "attachment"]
        filenames = [p.get_filename() for p in att_parts]
        assert "existing.pdf" in filenames
        assert "extra.txt" in filenames

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_preserves_threading(self, mock_creds, mock_create, tmp_path):
        """Threading headers preserved when adding attachments."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        raw = self._make_multipart_draft()
        envelope = MockEnvelope(
            subject=b"Draft with file",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"recipient", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=raw)
        mock_create.return_value = mock_client
        session._sessions.clear()

        f = tmp_path / "file.txt"
        f.write_text("content")

        modify_draft("Drafts", 1, body="Updated", attachments=[str(f)])

        appended = mock_client.appended_messages[0]
        assert b"In-Reply-To: <thread@example.com>" in appended["message"]
        assert b"References: <thread@example.com>" in appended["message"]

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_append_before_delete(self, mock_creds, mock_create):
        """New draft appended before old one is deleted."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        raw = b"From: user@example.com\r\nTo: r@example.com\r\nSubject: Test\r\nMessage-ID: <x@y>\r\n\r\nBody"
        envelope = MockEnvelope(
            subject=b"Test",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"r", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=raw)
        mock_create.return_value = mock_client
        session._sessions.clear()

        # Track operation order
        ops = []
        orig_append = mock_client.append
        orig_delete = mock_client.delete_messages

        def track_append(*args, **kwargs):
            ops.append("append")
            return orig_append(*args, **kwargs)

        def track_delete(*args, **kwargs):
            ops.append("delete")
            return orig_delete(*args, **kwargs)

        mock_client.append = track_append
        mock_client.delete_messages = track_delete

        modify_draft("Drafts", 1, body="New body")

        assert ops.index("append") < ops.index("delete")

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_modify_preserves_zero_byte_attachment(self, mock_creds, mock_create):
        """Zero-byte attachment should not be dropped."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()

        msg = email.message.EmailMessage()
        msg["From"] = "user@example.com"
        msg["To"] = "r@example.com"
        msg["Subject"] = "Empty file"
        msg["Message-ID"] = "<z@y>"
        msg.set_content("Body")
        msg.add_attachment(b"", maintype="application", subtype="octet-stream", filename="empty.dat")
        raw = msg.as_bytes()

        envelope = MockEnvelope(
            subject=b"Empty file",
            from_=[MockAddress(mailbox=b"user", host=b"example.com")],
            to=[MockAddress(mailbox=b"r", host=b"example.com")],
        )
        mock_client.add_message("Drafts", 1, envelope, raw_email=raw)
        mock_create.return_value = mock_client
        session._sessions.clear()

        modify_draft("Drafts", 1, body="Updated")

        appended = mock_client.appended_messages[0]
        parsed = email.message_from_bytes(appended["message"])
        att_parts = [p for p in parsed.walk() if p.get_content_disposition() == "attachment"]
        assert len(att_parts) == 1
        assert att_parts[0].get_filename() == "empty.dat"
        assert att_parts[0].get_payload(decode=True) == b""


class TestAttachmentRoundtrip:
    """Test download → create_draft roundtrip."""

    @patch("session._create_connection")
    @patch("imap_client.get_credentials")
    def test_downloaded_attachment_reattached(self, mock_creds, mock_create, tmp_path):
        """File downloaded from one message can be attached to a new draft."""
        mock_creds.return_value = ("server", "993", "user@example.com", "pass")
        mock_client = MockIMAPClient()
        mock_create.return_value = mock_client
        session._sessions.clear()

        # Simulate download_attachment result
        downloaded = tmp_path / "report.pdf"
        downloaded.write_bytes(b"%PDF-1.4 real pdf content here")

        result = create_draft(
            folder="INBOX",
            to="forward@example.com",
            subject="Fwd: Report",
            body="Forwarding the report",
            attachments=[str(downloaded)],
        )

        assert result["status"] == "created"
        appended = mock_client.appended_messages[0]
        parsed = email.message_from_bytes(appended["message"])
        att_parts = [p for p in parsed.walk() if p.get_content_disposition() == "attachment"]
        assert len(att_parts) == 1
        assert att_parts[0].get_payload(decode=True) == b"%PDF-1.4 real pdf content here"
