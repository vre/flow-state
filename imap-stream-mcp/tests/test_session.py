"""Tests for session caching."""
import socket
import time
from unittest.mock import Mock, patch

import pytest
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError

from session import FolderCache, MessageListCache, AccountSession, get_session, invalidate_message_cache, update_cached_flags, _sessions


class TestDataStructures:
    def test_folder_cache_creation(self):
        cache = FolderCache(
            folders=[{"name": "INBOX", "flags": ["\\HasNoChildren"]}],
            fetched_at=1000.0
        )
        assert cache.folders[0]["name"] == "INBOX"
        assert cache.fetched_at == 1000.0

    def test_message_list_cache_creation(self):
        cache = MessageListCache(
            messages=[{"id": 1, "subject": "Test"}],
            uidvalidity=12345,
            uidnext=100,
            exists=50
        )
        assert cache.uidvalidity == 12345
        assert cache.uidnext == 100
        assert cache.exists == 50

    def test_account_session_initial_state(self):
        session = AccountSession("test@example.com")
        assert session.account == "test@example.com"
        assert session.connection is None
        assert session.folder_cache is None
        assert session.message_cache == {}


class TestConnectionManagement:
    def test_get_connection_creates_new(self):
        """First call creates connection."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)

        with patch('session._create_connection', return_value=mock_client) as create:
            conn = session.get_connection()
            assert conn is mock_client
            assert session.connection is mock_client
            create.assert_called_once_with("test")

    def test_get_connection_reuses_existing(self):
        """Second call within timeout reuses connection."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()

        with patch('session._create_connection') as create:
            conn = session.get_connection()
            assert conn is mock_client
            create.assert_not_called()

    def test_get_connection_recreates_after_timeout(self):
        """Connection recreated after idle timeout."""
        session = AccountSession("test")
        old_client = Mock(spec=IMAPClient)
        new_client = Mock(spec=IMAPClient)
        session.connection = old_client
        session.last_activity = time.time() - 400  # Older than 300s timeout

        with patch('session._create_connection', return_value=new_client):
            conn = session.get_connection()
            assert conn is new_client
            old_client.logout.assert_called_once()

    def test_get_connection_recreates_on_noop_failure(self):
        """Connection recreated if NOOP fails."""
        session = AccountSession("test")
        old_client = Mock(spec=IMAPClient)
        old_client.noop.side_effect = Exception("Connection lost")
        new_client = Mock(spec=IMAPClient)
        session.connection = old_client
        session.last_activity = time.time()

        with patch('session._create_connection', return_value=new_client):
            conn = session.get_connection()
            assert conn is new_client


class TestConnectionContextManager:
    def test_context_manager_yields_connection(self):
        """Context manager yields working connection."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)

        with patch('session._create_connection', return_value=mock_client):
            with session.connection_ctx() as conn:
                assert conn is mock_client

    def test_context_manager_updates_activity(self):
        """Context manager updates last_activity on exit."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        old_time = time.time() - 10  # 10 seconds ago, within timeout
        session.last_activity = old_time

        with session.connection_ctx():
            pass

        assert session.last_activity > old_time

    def test_context_manager_closes_on_error_keeps_cache(self):
        """Connection error closes connection but keeps caches."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()
        session.folder_cache = FolderCache(folders=[{"name": "INBOX"}], fetched_at=1.0)

        with pytest.raises(IMAPClientError):
            with session.connection_ctx() as conn:
                raise IMAPClientError("Test error")

        assert session.connection is None  # Connection closed
        assert session.folder_cache is not None  # Cache preserved


class TestFolderCaching:
    def test_get_folders_fetches_on_miss(self):
        """First call fetches from server."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        mock_client.list_folders.return_value = [
            ([b'\\HasNoChildren'], b'/', b'INBOX'),
            ([b'\\Drafts'], b'/', b'Drafts'),
        ]

        with patch('session._create_connection', return_value=mock_client):
            folders = session.get_folders()

        assert len(folders) == 2
        assert folders[0]["name"] == "INBOX"
        assert folders[1]["name"] == "Drafts"
        mock_client.list_folders.assert_called_once()

    def test_get_folders_returns_cached(self):
        """Second call returns cached data."""
        session = AccountSession("test")
        session.folder_cache = FolderCache(
            folders=[{"name": "INBOX", "flags": []}],
            fetched_at=time.time()
        )
        mock_client = Mock(spec=IMAPClient)
        session.connection = mock_client
        session.last_activity = time.time()

        folders = session.get_folders()

        assert folders[0]["name"] == "INBOX"
        mock_client.list_folders.assert_not_called()


class TestMessageListCaching:
    def test_get_messages_fetches_on_miss(self):
        """First call fetches from server."""
        session = AccountSession("test")
        mock_client = Mock(spec=IMAPClient)
        mock_client.folder_status.return_value = {
            b'UIDVALIDITY': 12345,
            b'UIDNEXT': 100,
            b'MESSAGES': 50
        }
        mock_client.search.return_value = [1, 2, 3]
        mock_client.fetch.return_value = {
            3: {b'ENVELOPE': Mock(subject=b'Test', from_=[Mock(name=None, mailbox=b'a', host=b'b.com')], date=None), b'FLAGS': []},
            2: {b'ENVELOPE': Mock(subject=b'Test2', from_=[Mock(name=None, mailbox=b'c', host=b'd.com')], date=None), b'FLAGS': []},
        }

        with patch('session._create_connection', return_value=mock_client):
            messages = session.get_messages("Drafts", limit=10)

        assert len(messages) == 2
        assert session.message_cache["Drafts"].uidvalidity == 12345

    def test_get_messages_returns_cached_on_match(self):
        """Returns cache if UIDVALIDITY/UIDNEXT/EXISTS unchanged."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"uid": 1, "subject": "Cached"}],
            uidvalidity=12345,
            uidnext=100,
            exists=50
        )
        mock_client = Mock(spec=IMAPClient)
        mock_client.folder_status.return_value = {
            b'UIDVALIDITY': 12345,
            b'UIDNEXT': 100,
            b'MESSAGES': 50
        }
        session.connection = mock_client
        session.last_activity = time.time()

        messages = session.get_messages("Drafts", limit=10)

        assert messages[0]["subject"] == "Cached"
        mock_client.search.assert_not_called()

    def test_get_messages_refetches_on_uidnext_change(self):
        """Refetches if UIDNEXT changed (new message)."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"uid": 1, "subject": "Old"}],
            uidvalidity=12345,
            uidnext=100,
            exists=50
        )
        mock_client = Mock(spec=IMAPClient)
        mock_client.folder_status.return_value = {
            b'UIDVALIDITY': 12345,
            b'UIDNEXT': 101,  # Changed!
            b'MESSAGES': 51
        }
        mock_client.search.return_value = [1, 2]
        mock_client.fetch.return_value = {
            2: {b'ENVELOPE': Mock(subject=b'New', from_=[Mock(name=None, mailbox=b'a', host=b'b.com')], date=None), b'FLAGS': []},
            1: {b'ENVELOPE': Mock(subject=b'Old', from_=[Mock(name=None, mailbox=b'a', host=b'b.com')], date=None), b'FLAGS': []},
        }
        session.connection = mock_client
        session.last_activity = time.time()

        messages = session.get_messages("Drafts", limit=10)

        mock_client.search.assert_called()  # Refetched
        assert session.message_cache["Drafts"].uidnext == 101


class TestSessionManagement:
    def setup_method(self):
        """Clear sessions before each test."""
        _sessions.clear()

    def test_get_session_creates_new(self):
        """Creates session for new account."""
        with patch('session.get_default_account', return_value="default@test.com"):
            session = get_session()
        assert session.account == "default@test.com"

    def test_get_session_reuses_existing(self):
        """Returns same session for same account."""
        with patch('session.get_default_account', return_value="test@test.com"):
            session1 = get_session()
            session2 = get_session()
        assert session1 is session2

    def test_get_session_with_explicit_account(self):
        """Uses explicit account when provided."""
        session = get_session("explicit@test.com")
        assert session.account == "explicit@test.com"

    def test_invalidate_message_cache(self):
        """Invalidates specific folder cache."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache([], 1, 1, 1)
        session.message_cache["INBOX"] = MessageListCache([], 2, 2, 2)
        _sessions["test"] = session

        invalidate_message_cache("test", "Drafts")

        assert "Drafts" not in session.message_cache
        assert "INBOX" in session.message_cache


class TestCacheUpdateOnFlags:
    def setup_method(self):
        _sessions.clear()

    def test_update_cached_flags(self):
        """Updates flags in cache without refetch."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[
                {"id": 1, "subject": "A", "flags": ["Seen"]},
                {"id": 2, "subject": "B", "flags": []},
            ],
            uidvalidity=1, uidnext=3, exists=2
        )
        _sessions["test"] = session

        update_cached_flags("test", "Drafts", 2, ["Seen", "Flagged"])

        assert session.message_cache["Drafts"].messages[1]["flags"] == ["Seen", "Flagged"]
        assert session.message_cache["Drafts"].messages[0]["flags"] == ["Seen"]  # Unchanged

    def test_update_cached_flags_nonexistent_message(self):
        """Does nothing if message not in cache."""
        session = AccountSession("test")
        session.message_cache["Drafts"] = MessageListCache(
            messages=[{"id": 1, "subject": "A", "flags": []}],
            uidvalidity=1, uidnext=2, exists=1
        )
        _sessions["test"] = session

        update_cached_flags("test", "Drafts", 999, ["Seen"])  # No error

        assert session.message_cache["Drafts"].messages[0]["flags"] == []
