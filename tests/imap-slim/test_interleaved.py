"""Answering point by point, with the quote checked rather than trusted.

Interleaving is the one flow where the caller assembles the quoted text itself,
so it is the one flow where the quote has to be verified against the original.
"""

import datetime
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim"))

from actions import Failure, MailAction, run_action  # noqa: E402
from quoting import quote_block, validate_quoted_lines  # noqa: E402

ORIGINAL = {
    "uid": 1253,
    "folder": "INBOX",
    "subject": "Kolme kysymystä",
    "message_id": "<abc@example.com>",
    "references": "",
    "from_display": "Maija Meikäläinen",
    "from_addr": "maija@example.com",
    "reply_to": None,
    "date": datetime.datetime(2026, 8, 19, 15, 18),
    "plain": "Moi,\n\nmilloin raportti valmistuu?\n\nentä lasku?\n\nMaija",
    "html": None,
    "inline_parts": [],
}

CREATED = {
    "status": "created",
    "folder": "Drafts",
    "to": "maija@example.com",
    "subject": "Re: Kolme kysymystä",
    "message_id": "<new@example.com>",
    "uid": 78,
    "size": 1024,
}

INTERLEAVED = """On 19.8.2026 15.18, Maija Meikäläinen wrote:
> Moi,
>
> milloin raportti valmistuu?

Perjantaina.

> entä lasku?

Lähti jo.
"""


def _create(body, fmt="plain"):
    import json

    with (
        patch("actions.fetch_quotable", return_value=ORIGINAL),
        patch("actions.create_draft", return_value=CREATED) as create,
        patch("actions.get_from_address", return_value="me@example.com"),
    ):
        result = run_action(MailAction(action="create", format=fmt, payload=json.dumps({"body": body}), quote="INBOX:1253"))
    return result, create


class TestTheBlockYouWriteInto:
    def test_it_carries_the_attribution_and_the_quote(self):
        block = quote_block(ORIGINAL)
        assert block.splitlines()[0] == "On 19.8.2026 15.18, Maija Meikäläinen wrote:"
        assert "> milloin raportti valmistuu?" in block

    def test_read_hands_it_over(self):
        with patch("actions.fetch_quotable", return_value=ORIGINAL):
            result = run_action(MailAction(action="read", folder="INBOX", payload="1253:quote"))

        assert "> milloin raportti valmistuu?" in result
        assert "[EXTERNAL_EMAIL_" in result, "it is still someone else's text"

    def test_an_unknown_modifier_still_names_the_real_ones(self):
        result = run_action(MailAction(action="read", folder="INBOX", payload="1253:sideways"))
        assert isinstance(result, Failure)
        assert ":quote" in result


class TestValidation:
    def test_a_faithful_body_passes(self):
        assert validate_quoted_lines(INTERLEAVED, ORIGINAL) is None

    def test_an_invented_line_is_caught(self):
        body = INTERLEAVED.replace("> entä lasku?", "> ja maksatko heti?")
        assert validate_quoted_lines(body, ORIGINAL) == "> ja maksatko heti?"

    def test_an_edited_line_is_caught(self):
        body = INTERLEAVED.replace("> milloin raportti valmistuu?", "> milloin raportti valmistuu???")
        assert validate_quoted_lines(body, ORIGINAL) is not None

    def test_reordering_someones_words_is_caught(self):
        body = "> entä lasku?\n\nx\n\n> milloin raportti valmistuu?\n"
        assert validate_quoted_lines(body, ORIGINAL) == "> milloin raportti valmistuu?"

    def test_dropping_lines_is_allowed(self):
        """Quoting selectively is normal; inventing is not."""
        assert validate_quoted_lines("> entä lasku?\n\nLähti jo.\n", ORIGINAL) is None

    def test_the_callers_own_prose_is_not_checked(self):
        assert validate_quoted_lines("Anything at all.\n\n> entä lasku?\n", ORIGINAL) is None


class TestThroughTheDispatcher:
    def test_an_interleaved_body_is_written_as_it_stands(self):
        result, create = _create(INTERLEAVED)

        assert not isinstance(result, Failure)
        body = create.call_args.kwargs["body"]
        assert body == INTERLEAVED, "the client must not append a second quote"

    def test_an_unfaithful_quote_is_refused_before_anything_is_written(self):
        with (
            patch("actions.fetch_quotable", return_value=ORIGINAL),
            patch("actions.create_draft") as create,
            patch("actions.get_from_address", return_value="me@example.com"),
        ):
            result = run_action(
                MailAction(
                    action="create",
                    format="plain",
                    payload='{"body": "> jotain aivan muuta\\n\\nvastaus"}',
                    quote="INBOX:1253",
                )
            )

        assert isinstance(result, Failure)
        assert "not in INBOX:1253" in result
        create.assert_not_called()

    def test_interleaving_is_refused_for_markdown(self):
        """Splicing into someone else's HTML is out of scope by decision."""
        result, _unused = _create(INTERLEAVED, fmt="markdown")
        assert isinstance(result, Failure)
        assert "plain" in result

    def test_a_plain_top_post_still_gets_its_quote_appended(self):
        result, create = _create("Kiitos, hoidan.")

        assert not isinstance(result, Failure)
        body = create.call_args.kwargs["body"]
        assert body.startswith("Kiitos, hoidan.")
        assert "> milloin raportti valmistuu?" in body

    def test_a_markdown_top_post_is_unaffected(self):
        result, create = _create("**Kiitos**, hoidan.", fmt="markdown")

        assert not isinstance(result, Failure)
        assert create.call_args.kwargs["html"] is not None
