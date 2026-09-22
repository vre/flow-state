"""What actually goes on the wire for a search.

The search mock in conftest ignores its criteria, so tests that only check the
returned rows say nothing about protocol shape. These check the call itself.
"""

import datetime
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim"))

from imap_client import IMAPError, search_messages  # noqa: E402


def _search(query):
    """Run one search against a mocked connection and return the search call."""
    client = MagicMock()
    client.select_folder.return_value = {}
    client.search.return_value = []

    session = MagicMock()
    session.run_op.side_effect = lambda operation, **kw: operation(client)

    with patch("session.get_session", return_value=session):
        search_messages("INBOX", query)
    return client.search.call_args


class TestDateCriteria:
    def test_since_is_sent_as_a_date_not_a_string(self):
        """IMAP wants 1-Jan-2024; a bare string goes out as 2024-01-01."""
        args, kwargs = _search("since:2024-01-01")

        assert args[0] == ["SINCE", datetime.date(2024, 1, 1)]
        assert kwargs == {"charset": None}

    def test_before_is_sent_as_a_date(self):
        args, _kwargs = _search("before:2024-12-31")

        assert args[0] == ["BEFORE", datetime.date(2024, 12, 31)]

    def test_an_unparseable_date_is_reported_not_forwarded(self):
        with pytest.raises(IMAPError, match="YYYY-MM-DD"):
            _search("since:last tuesday")


class TestCharset:
    def test_non_ascii_search_names_utf8(self):
        """Without a charset the client encodes as ASCII and raises locally."""
        _args, kwargs = _search("subject:järjestelmä")

        assert kwargs == {"charset": "UTF-8"}

    def test_ascii_search_names_no_charset(self):
        _args, kwargs = _search("subject:invoice")

        assert kwargs == {"charset": None}

    def test_a_rejected_charset_is_explained(self):
        client = MagicMock()
        client.select_folder.return_value = {}
        client.search.side_effect = ValueError("BADCHARSET")

        session = MagicMock()
        session.run_op.side_effect = lambda operation, **kw: operation(client)

        with patch("session.get_session", return_value=session), pytest.raises(IMAPError, match="non-ASCII"):
            search_messages("INBOX", "subject:järjestelmä")
