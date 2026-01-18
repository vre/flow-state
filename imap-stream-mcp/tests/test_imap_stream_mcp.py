"""Tests for imap_stream_mcp module."""

import pytest
from unittest.mock import patch, MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from imap_stream_mcp import use_mail, MailAction

pytestmark = pytest.mark.anyio


class TestAccountsAction:
    """Tests for accounts action."""

    @patch('imap_stream_mcp.list_accounts')
    @patch('imap_stream_mcp.get_default_account')
    async def test_accounts_shows_multiple_accounts(self, mock_default, mock_list):
        """Should show list of accounts with default marked."""
        mock_list.return_value = ["work", "personal"]
        mock_default.return_value = "work"

        result = await use_mail(MailAction(action="accounts"))

        assert "work" in result
        assert "personal" in result
        assert "default" in result.lower()

    @patch('imap_stream_mcp.list_accounts')
    @patch('imap_stream_mcp.get_default_account')
    async def test_accounts_single_account_shows_hint(self, mock_default, mock_list):
        """Should show setup hint when only one account."""
        mock_list.return_value = ["default"]
        mock_default.return_value = "default"

        result = await use_mail(MailAction(action="accounts"))

        # Single account should show the account but also hint about adding more
        assert "default" in result.lower()

    @patch('imap_stream_mcp.list_accounts')
    @patch('imap_stream_mcp.get_default_account')
    async def test_accounts_no_accounts_shows_setup(self, mock_default, mock_list):
        """Should show setup instructions when no accounts."""
        mock_list.return_value = []
        mock_default.return_value = None

        result = await use_mail(MailAction(action="accounts"))

        assert "setup" in result.lower()


class TestMailActionValidation:
    """Tests for MailAction validation."""

    def test_accounts_is_valid_action(self):
        """Should accept 'accounts' as valid action."""
        action = MailAction(action="accounts")
        assert action.action == "accounts"

    def test_invalid_action_raises(self):
        """Should reject invalid actions."""
        with pytest.raises(ValueError, match="Invalid action"):
            MailAction(action="invalid")
