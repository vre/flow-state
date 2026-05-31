"""Tests that account parameter is wired through from use_mail to imap_client."""

from unittest.mock import MagicMock, patch

import pytest
from imap_stream_mcp import MailAction


class TestMailActionAccount:
    def test_account_field_exists(self):
        action = MailAction(action="list", folder="INBOX", account="work", preview=True)
        assert action.account == "work"

    def test_account_defaults_to_none(self):
        action = MailAction(action="list", folder="INBOX", preview=True)
        assert action.account is None


class TestAccountPassthrough:
    """Verify use_mail passes account to every imap_client call."""

    ACCOUNT = "work"

    @pytest.fixture
    def _patch_accounts(self):
        with (
            patch("imap_stream_mcp.list_accounts", return_value=["default", "work"]),
            patch("imap_stream_mcp.get_default_account", return_value="default"),
        ):
            yield

    @patch("imap_stream_mcp.list_messages")
    def test_list_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = []
        import asyncio

        from imap_stream_mcp import use_mail

        params = MailAction(action="list", folder="INBOX", account=self.ACCOUNT, preview=True)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT

    @patch("imap_stream_mcp.read_message")
    def test_read_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = {
            "from": ["a@b.com"],
            "to": ["c@d.com"],
            "cc": [],
            "subject": "test",
            "date": "2026-01-01",
            "message_id": "<1>",
            "in_reply_to": None,
            "body_text": "hi",
            "body_html": None,
            "attachments": [],
            "inline_images": [],
        }
        import asyncio

        from imap_stream_mcp import use_mail

        params = MailAction(action="read", folder="INBOX", payload="1", account=self.ACCOUNT)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT

    @patch("imap_stream_mcp.search_messages")
    def test_search_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = []
        import asyncio

        from imap_stream_mcp import use_mail

        params = MailAction(action="search", folder="INBOX", payload="test", account=self.ACCOUNT, preview=True)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT

    @patch("imap_stream_mcp.create_draft")
    def test_create_draft_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = {
            "to": "a@b.com",
            "subject": "test",
            "folder": "Drafts",
            "attachments": [],
        }
        import asyncio
        import json

        from imap_stream_mcp import use_mail

        payload = json.dumps({"to": "a@b.com", "subject": "test", "body": "hi"})
        params = MailAction(action="draft", folder="INBOX", payload=payload, account=self.ACCOUNT)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT

    @patch("imap_stream_mcp.modify_draft")
    def test_modify_draft_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = {
            "to": "a@b.com",
            "subject": "test",
            "folder": "Drafts",
            "preserved_reply_to": False,
            "attachments": [],
        }
        import asyncio
        import json

        from imap_stream_mcp import use_mail

        payload = json.dumps({"id": 1, "body": "updated"})
        params = MailAction(action="draft", folder="Drafts", payload=payload, account=self.ACCOUNT)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT

    @patch("imap_stream_mcp.edit_draft")
    def test_edit_draft_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = {
            "subject": "test",
            "folder": "Drafts",
            "changes": [{"old": "foo", "new": "bar"}],
        }
        import asyncio
        import json

        from imap_stream_mcp import use_mail

        payload = json.dumps({"id": 1, "replacements": [{"old": "foo", "new": "bar"}]})
        params = MailAction(action="edit", folder="Drafts", payload=payload, account=self.ACCOUNT)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT

    @patch("imap_stream_mcp.modify_flags")
    def test_flag_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = {
            "modified": 1,
            "flags_added": ["\\Flagged"],
            "flags_removed": [],
            "failed": [],
        }
        import asyncio

        from imap_stream_mcp import use_mail

        params = MailAction(action="flag", folder="INBOX", payload="1:+Flagged", account=self.ACCOUNT)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT

    @patch("imap_stream_mcp.download_attachment")
    def test_attachment_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = {
            "filename": "test.pdf",
            "content_type": "application/pdf",
            "size": 1024,
            "saved_to": "/tmp/test.pdf",
        }
        import asyncio

        from imap_stream_mcp import use_mail

        params = MailAction(action="attachment", folder="INBOX", payload="1:0", account=self.ACCOUNT)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT

    @patch("imap_stream_mcp.list_folders")
    def test_folders_passes_account(self, mock_fn, _patch_accounts):
        mock_fn.return_value = [{"name": "INBOX", "flags": []}]
        import asyncio

        from imap_stream_mcp import use_mail

        params = MailAction(action="folders", account=self.ACCOUNT)
        asyncio.run(use_mail(params))
        mock_fn.assert_called_once()
        assert mock_fn.call_args.kwargs.get("account") == self.ACCOUNT


class TestGetCredentialsPassthrough:
    """Verify create_draft and modify_draft pass account to get_credentials."""

    @patch("session.get_session")
    @patch("imap_client.get_credentials")
    def test_create_draft_passes_account(self, mock_creds, mock_session):
        mock_creds.return_value = ("server", 993, "work@example.com", "pass")
        mock_ctx = MagicMock()
        mock_session.return_value.connection_ctx.return_value = mock_ctx
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock(append=MagicMock(return_value=("OK", [b"1"]))))
        mock_ctx.__exit__ = MagicMock(return_value=False)

        from imap_client import create_draft

        try:
            create_draft(
                folder="INBOX",
                to="a@b.com",
                subject="test",
                body="hi",
                account="work",
            )
        except Exception:
            pass
        mock_creds.assert_called_with("work")

    @patch("session.get_session")
    @patch("imap_client.get_credentials")
    def test_modify_draft_passes_account(self, mock_creds, mock_session):
        mock_creds.return_value = ("server", 993, "work@example.com", "pass")
        mock_client = MagicMock()
        mock_client.select_folder.return_value = {}
        mock_client.append.return_value = ("OK", [b"2"])
        mock_client.delete_messages.return_value = {}
        mock_client.expunge.return_value = []
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_client)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_session.return_value.connection_ctx.return_value = mock_ctx

        import email.message

        fake_envelope = MagicMock()
        fake_envelope.subject = b"test"
        fake_envelope.to = None
        fake_envelope.cc = None
        fake_msg = email.message.EmailMessage()

        from imap_client import modify_draft

        try:
            modify_draft(
                folder="Drafts",
                message_id=1,
                body="updated",
                account="work",
                prefetched_draft=(fake_envelope, fake_msg),
            )
        except Exception:
            pass
        mock_creds.assert_called_with("work")
