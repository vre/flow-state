"""A cached list must answer the question that was asked.

UIDVALIDITY/UIDNEXT/EXISTS say whether the mailbox changed. They say nothing
about the limit or the previews the caller asked for, and nothing at all about
flags, which move without touching any counter.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from imapclient import IMAPClient

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim"))

from session import MESSAGE_CACHE_TTL, AccountSession, MessageListCache  # noqa: E402

SELECT_STATE = {b"UIDVALIDITY": 12345, b"UIDNEXT": 100, b"EXISTS": 50}


@pytest.fixture
def session_with_cache():
    """A session holding one cached list of two messages, fetched for limit=10."""
    session = AccountSession("test")
    session.message_cache["INBOX"] = MessageListCache(
        messages=[{"id": 1, "subject": "Cached", "flags": []}, {"id": 2, "subject": "Also cached", "flags": []}],
        uidvalidity=12345,
        uidnext=100,
        exists=50,
        limit=10,
        preview=False,
        fetched_at=time.time(),
    )
    client = MagicMock(spec=IMAPClient)
    client.select_folder.return_value = SELECT_STATE
    client.search.return_value = []
    session.connection = client
    session.last_activity = time.time()
    return session, client


class TestRequestShapeIsPartOfTheKey:
    def test_same_request_is_served_from_cache(self, session_with_cache):
        session, client = session_with_cache

        messages = session.get_messages("INBOX", limit=10)

        assert messages[0]["subject"] == "Cached"
        client.search.assert_not_called()

    def test_a_larger_limit_refetches(self, session_with_cache):
        """A list cached for 10 cannot answer a request for 50."""
        session, client = session_with_cache

        session.get_messages("INBOX", limit=50)

        client.search.assert_called_once()

    def test_a_smaller_limit_is_served_from_cache(self, session_with_cache):
        session, client = session_with_cache

        messages = session.get_messages("INBOX", limit=1)

        assert len(messages) == 1
        client.search.assert_not_called()

    def test_asking_for_previews_refetches(self, session_with_cache):
        """The cached entry has no snippets to return."""
        session, client = session_with_cache

        session.get_messages("INBOX", limit=10, preview=True)

        client.search.assert_called_once()

    def test_dropping_previews_refetches(self, session_with_cache):
        """Otherwise the answer carries snippets the caller did not ask for."""
        session, client = session_with_cache
        session.message_cache["INBOX"].preview = True

        session.get_messages("INBOX", limit=10, preview=False)

        client.search.assert_called_once()


class TestFlagDrift:
    def test_an_aged_entry_refetches(self, session_with_cache):
        """Another client marking a message read moves no counter."""
        session, client = session_with_cache
        session.message_cache["INBOX"].fetched_at = time.time() - MESSAGE_CACHE_TTL - 1

        session.get_messages("INBOX", limit=10)

        client.search.assert_called_once()
