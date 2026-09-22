"""Quoting is the client's job, and it must not alter what it quotes.

Everything here is pure: `quoting` works on an already-fetched original, so the
rules can be checked without a server.
"""

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim"))

from quoting import (  # noqa: E402
    assemble_reply,
    attribution_line,
    quote_html_text,
    quote_plain,
    reply_headers,
    reply_subject,
)

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
    "plain": "Hei,\n\nliitteenä raportit.\n\nterveisin\nMaija",
    "html": None,
}


class TestAttribution:
    def test_copies_thunderbirds_line(self):
        line = attribution_line(datetime.datetime(2026, 8, 19, 15, 18), "Maija Meikäläinen")
        assert line == "On 19.8.2026 15.18, Maija Meikäläinen wrote:"

    def test_no_leading_zeros_on_day_month_or_hour(self):
        line = attribution_line(datetime.datetime(2026, 4, 1, 4, 34), "Name")
        assert line == "On 1.4.2026 4.34, Name wrote:"

    def test_minutes_keep_their_zero(self):
        line = attribution_line(datetime.datetime(2026, 4, 1, 4, 5), "Name")
        assert line.endswith("4.05, Name wrote:")

    def test_does_not_depend_on_the_process_locale(self):
        """Thunderbird renders in the user's locale; this process inherits
        whatever locale it was launched with, so the format is a constant."""
        import locale

        before = locale.setlocale(locale.LC_TIME)
        try:
            for candidate in ("C", "en_US.UTF-8", "fi_FI.UTF-8"):
                try:
                    locale.setlocale(locale.LC_TIME, candidate)
                except locale.Error:
                    continue
                assert attribution_line(datetime.datetime(2026, 8, 19, 15, 18), "N") == "On 19.8.2026 15.18, N wrote:"
        finally:
            locale.setlocale(locale.LC_TIME, before)

    def test_no_date_means_no_attribution(self):
        assert attribution_line(None, "Name") is None
        assert attribution_line(datetime.datetime(2026, 1, 1), "") is None


class TestPlainQuoting:
    def test_every_line_is_prefixed(self):
        assert quote_plain("one\ntwo") == "> one\n> two"

    def test_a_blank_line_becomes_a_bare_marker(self):
        """ "> " on an empty line is trailing whitespace; clients emit ">"."""
        assert quote_plain("one\n\ntwo") == "> one\n>\n> two"

    def test_already_quoted_lines_gain_a_level(self):
        assert quote_plain("> theirs") == "> > theirs"

    def test_nothing_is_rewrapped(self):
        long_line = "x" * 200
        assert quote_plain(long_line) == f"> {long_line}"

    def test_markdown_in_the_original_stays_literal(self):
        """The quote is never passed through the renderer: asterisks in someone
        else's mail are asterisks."""
        assert quote_plain("*not emphasis* and # not a heading") == "> *not emphasis* and # not a heading"

    def test_crlf_is_normalised(self):
        assert quote_plain("one\r\ntwo") == "> one\n> two"


class TestHtmlQuoting:
    def test_markup_in_the_original_is_escaped(self):
        assert quote_html_text("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"

    def test_line_breaks_are_preserved(self):
        assert quote_html_text("one\ntwo") == "one<br>\ntwo"


class TestReplyHeaders:
    def test_subject_gains_one_re(self):
        assert reply_subject("Raportti valmis") == "Re: Raportti valmis"

    def test_subject_does_not_gain_a_second_re(self):
        assert reply_subject("Re: Raportti") == "Re: Raportti"
        assert reply_subject("RE: Raportti") == "RE: Raportti"
        assert reply_subject("re:Raportti") == "re:Raportti"

    def test_references_chains_rather_than_replaces(self):
        headers = reply_headers(ORIGINAL)
        assert headers["references"] == "<older@example.com> <abc123@example.com>"
        assert headers["in_reply_to"] == "<abc123@example.com>"

    def test_a_first_reply_has_only_the_original(self):
        headers = reply_headers({**ORIGINAL, "references": ""})
        assert headers["references"] == "<abc123@example.com>"

    def test_reply_to_wins_over_from(self):
        headers = reply_headers({**ORIGINAL, "reply_to": "list@example.com"})
        assert headers["to"] == "list@example.com"

    def test_from_is_used_without_a_reply_to(self):
        assert reply_headers(ORIGINAL)["to"] == "maija@example.com"


class TestAssembly:
    def test_new_text_comes_first_then_attribution_then_quote(self):
        plain, _html = assemble_reply("Kiitos!", None, ORIGINAL)
        lines = plain.splitlines()
        assert lines[0] == "Kiitos!"
        assert lines[1] == ""
        assert lines[2] == "On 19.8.2026 15.18, Maija Meikäläinen wrote:"
        assert lines[4].startswith("> Hei,")

    def test_the_original_survives_intact(self):
        plain, _html = assemble_reply("Kiitos!", None, ORIGINAL)
        stripped = "\n".join(line[2:] if line.startswith("> ") else "" for line in plain.splitlines()[4:])
        assert stripped.strip("\n") == ORIGINAL["plain"]

    def test_plain_only_builds_no_html_half(self):
        _plain, html = assemble_reply("Kiitos!", None, ORIGINAL)
        assert html is None

    def test_html_half_cites_the_original_message_id(self):
        _plain, html = assemble_reply("Kiitos!", "<p>Kiitos!</p>", ORIGINAL)
        assert '<blockquote type="cite" cite="mid:abc123@example.com">' in html
        assert '<div class="moz-cite-prefix">On 19.8.2026 15.18, Maija Meikäläinen wrote:<br></div>' in html

    def test_html_half_puts_the_new_text_above_the_quote(self):
        """An unbalanced tag in the quote can then only break the quote."""
        _plain, html = assemble_reply("Kiitos!", "<p>Kiitos!</p>", ORIGINAL)
        assert html.index("<p>Kiitos!</p>") < html.index("<blockquote")

    def test_a_message_without_an_id_still_quotes(self):
        _plain, html = assemble_reply("K", "<p>K</p>", {**ORIGINAL, "message_id": ""})
        assert '<blockquote type="cite">' in html


class TestHeaderEncoding:
    """A Message-ID that does not fit the fold width must not be encoded.

    Python's default policy RFC 2047-encodes any token it cannot fold, and an
    encoded Message-ID matches nothing - so a References chain holding one long
    id (Outlook's run about 80 characters) silently breaks threading. Found on
    a real reply, not in the suite.
    """

    LONG_ID = "<AM0PR01MB1234ABCDEF0123456789ABCDEF012@AM0PR01MB1234.eurprd01.prod.outlook.com>"

    def _built(self, **headers):
        import email.message

        from imap_client import DRAFT_POLICY

        msg = email.message.EmailMessage(policy=DRAFT_POLICY)
        for name, value in headers.items():
            msg[name.replace("_", "-")] = value
        msg.set_content("body")
        return msg.as_bytes().decode()

    def test_a_long_message_id_survives_verbatim(self):
        raw = self._built(References=f"{self.LONG_ID} <short@example.com>")
        assert self.LONG_ID in raw
        assert "=?utf-8?q?=3C" not in raw

    def test_in_reply_to_survives_too(self):
        assert self.LONG_ID in self._built(In_Reply_To=self.LONG_ID)

    def test_a_non_ascii_subject_is_still_encoded(self):
        """Widening the fold must not stop legitimate encoding."""
        raw = self._built(Subject="Re: Tarjouspyyntö")
        assert "=?utf-8?" in raw

    def test_no_line_exceeds_the_rfc_limit(self):
        raw = self._built(References=" ".join([self.LONG_ID] * 12))
        assert max(len(line) for line in raw.split("\n")) <= 998
