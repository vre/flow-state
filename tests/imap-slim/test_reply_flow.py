"""`create` with a quote target, from the dispatcher down."""

import datetime
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim"))

from actions import Failure, MailAction, run_action  # noqa: E402

ORIGINAL = {
    "uid": 1253,
    "folder": "INBOX",
    "subject": "Raportti valmis",
    "message_id": "<abc123@example.com>",
    "references": "<older@example.com>",
    "from_display": "Maija Meikäläinen",
    "from_addr": "maija@example.com",
    "reply_to": None,
    "date": datetime.datetime(2026, 8, 19, 15, 18),
    "plain": "Hei,\n\nliitteenä raportit.",
    "html": None,
}

CREATED = {
    "status": "created",
    "folder": "Drafts",
    "to": "maija@example.com",
    "subject": "Re: Raportti valmis",
    "message_id": "<new@example.com>",
    "uid": 77,
    "size": 2048,
}


def _reply(payload='{"body": "Kiitos!"}', fmt="plain", quote="INBOX:1253"):
    with (
        patch("actions.fetch_quotable", return_value=ORIGINAL) as fetch,
        patch("actions.create_draft", return_value=CREATED) as create,
        patch("actions.get_from_address", return_value="me@example.com"),
    ):
        result = run_action(MailAction(action="create", format=fmt, payload=payload, quote=quote))
    return result, fetch, create


class TestTheTargetIsValidated:
    def test_quote_is_rejected_for_replace(self):
        with pytest.raises(ValidationError, match="only valid for create"):
            MailAction(action="replace", format="plain", payload="{}", folder="Drafts", quote="INBOX:1")

    def test_a_malformed_target_is_rejected(self):
        with pytest.raises(ValidationError, match="FOLDER:UID"):
            MailAction(action="create", format="plain", payload="{}", quote="INBOX")

    def test_a_folder_with_a_colon_still_parses(self):
        action = MailAction(action="create", format="plain", payload="{}", quote="INBOX:Sub:1253")
        assert action.quote == "INBOX:Sub:1253"


class TestWhatTheCallerHasToSupply:
    def test_only_the_body_is_required(self):
        """Recipient and subject come from the message being replied to."""
        result, _fetch, create = _reply()
        assert not isinstance(result, Failure)
        assert create.call_args.kwargs["to"] == "maija@example.com"
        assert create.call_args.kwargs["subject"] == "Re: Raportti valmis"

    def test_a_missing_body_is_still_an_error(self):
        result, _fetch, _create = _reply(payload='{"to": "x@y.z"}')
        assert isinstance(result, Failure)

    def test_an_explicit_recipient_wins(self):
        _result, _fetch, create = _reply(payload='{"body": "K", "to": "other@example.com"}')
        assert create.call_args.kwargs["to"] == "other@example.com"

    def test_an_explicit_subject_wins(self):
        _result, _fetch, create = _reply(payload='{"body": "K", "subject": "Something else"}')
        assert create.call_args.kwargs["subject"] == "Something else"


class TestWhatGetsWritten:
    def test_threading_headers_come_from_the_original(self):
        _result, _fetch, create = _reply()
        assert create.call_args.kwargs["in_reply_to"] == "<abc123@example.com>"
        assert create.call_args.kwargs["references"] == "<older@example.com> <abc123@example.com>"

    def test_the_quote_is_below_the_new_text(self):
        _result, _fetch, create = _reply()
        body = create.call_args.kwargs["body"]
        assert body.index("Kiitos!") < body.index("On 19.8.2026 15.18") < body.index("> Hei,")

    def test_plain_format_writes_no_html_part(self):
        _result, _fetch, create = _reply(fmt="plain")
        assert create.call_args.kwargs["html"] is None

    def test_markdown_format_quotes_in_both_parts(self):
        _result, _fetch, create = _reply(fmt="markdown")
        html = create.call_args.kwargs["html"]
        assert '<blockquote type="cite" cite="mid:abc123@example.com">' in html
        assert "> Hei," in create.call_args.kwargs["body"]

    def test_the_response_names_what_was_quoted(self):
        result, _fetch, _create = _reply()
        assert "INBOX:1253" in result
        assert "Maija Meikäläinen" in result

    def test_a_fetch_failure_stops_before_anything_is_written(self):
        from imap_client import IMAPError

        with (
            patch("actions.fetch_quotable", side_effect=IMAPError("Message 9 not found in 'INBOX'")),
            patch("actions.create_draft") as create,
        ):
            result = run_action(MailAction(action="create", format="plain", payload='{"body": "K"}', quote="INBOX:9"))

        assert isinstance(result, Failure)
        create.assert_not_called()


class TestWithoutAQuote:
    def test_an_ordinary_create_still_requires_recipient_and_subject(self):
        with patch("actions.create_draft", return_value=CREATED):
            result = run_action(MailAction(action="create", format="plain", payload='{"body": "hello"}'))
        assert isinstance(result, Failure)
        assert "to" in result and "subject" in result

    def test_an_ordinary_create_does_not_fetch_anything(self):
        with (
            patch("actions.fetch_quotable") as fetch,
            patch("actions.create_draft", return_value=CREATED),
        ):
            run_action(
                MailAction(
                    action="create",
                    format="plain",
                    payload='{"to": "a@b.c", "subject": "s", "body": "hello"}',
                )
            )
        fetch.assert_not_called()


class TestSizeWarning:
    def test_a_large_draft_is_reported(self):
        with (
            patch("actions.fetch_quotable", return_value=ORIGINAL),
            patch("actions.create_draft", return_value={**CREATED, "size": 900 * 1024}),
            patch("actions.get_from_address", return_value="me@example.com"),
        ):
            result = run_action(MailAction(action="create", format="plain", payload='{"body": "K"}', quote="INBOX:1253"))
        assert "900 kB" in result
        assert "nothing was truncated" in result

    def test_an_ordinary_draft_says_nothing_about_size(self):
        result, _fetch, _create = _reply()
        assert "kB" not in result
