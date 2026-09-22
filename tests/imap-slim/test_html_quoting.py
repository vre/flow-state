"""Quoting an HTML message: the fragment is the sender's own markup.

Measured against real Thunderbird replies (see the frame). The rules here are
copied from what it does, not from what seemed reasonable.
"""

import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim"))

from quoting import (  # noqa: E402
    assemble_reply,
    body_fragment,
    new_cid,
    referenced_cids,
    rewrite_cids,
)

DOCUMENT = """<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  <style>p { color: red }</style>
</head>
<body text="#000000">
  <p class="elementToProof">Moi,</p>
  <img src="cid:image001@outlook.com" alt="chart">
</body>
</html>"""

ORIGINAL = {
    "uid": 7,
    "folder": "INBOX",
    "subject": "Raportti",
    "message_id": "<abc@example.com>",
    "references": "",
    "from_display": "Maija Meikäläinen",
    "from_addr": "maija@example.com",
    "reply_to": None,
    "date": datetime.datetime(2026, 8, 19, 15, 18),
    "plain": "Moi,",
    "html": DOCUMENT,
    "inline_parts": [
        {"cid": "image001@outlook.com", "maintype": "image", "subtype": "png", "filename": "image.png", "data": b"\x89PNG-data"}
    ],
}


class TestFragmentExtraction:
    def test_only_the_body_content_is_quoted(self):
        fragment = body_fragment(DOCUMENT)
        assert '<p class="elementToProof">Moi,</p>' in fragment
        assert "<html" not in fragment.lower()
        assert "<body" not in fragment.lower()

    def test_the_originals_style_stays_out_of_the_reply_document(self):
        """Thunderbird leaves head behind; a quoted <style> that ends up in our
        head would restyle the reply's own text."""
        assert "color: red" not in body_fragment(DOCUMENT)

    def test_a_bare_fragment_is_already_a_fragment(self):
        assert body_fragment("<div>hello</div>") == "<div>hello</div>"

    def test_a_document_without_a_body_tag_loses_only_its_wrapper(self):
        fragment = body_fragment("<html><head><style>x</style></head><div>hi</div></html>")
        assert fragment == "<div>hi</div>"

    def test_foreign_markup_is_not_cleaned_up(self):
        """The frame decided it: altering the quote is the larger harm."""
        messy = '<div onclick="x()"><script>alert(1)</script>text</div>'
        assert body_fragment(messy) == messy


class TestCidHandling:
    def test_references_are_found_in_order_and_deduplicated(self):
        fragment = '<img src="cid:a@x"><img src="cid:b@x"><img src="cid:a@x">'
        assert referenced_cids(fragment) == ["a@x", "b@x"]

    def test_single_quotes_and_href_count_too(self):
        assert referenced_cids("<a href='cid:c@x'>") == ["c@x"]

    def test_rewriting_points_at_the_new_id(self):
        out = rewrite_cids('<img src="cid:old@x">', {"old@x": "part1.aa.bb@ours"})
        assert out == '<img src="cid:part1.aa.bb@ours">'

    def test_an_unmapped_reference_is_left_alone(self):
        assert rewrite_cids('<img src="cid:gone@x">', {}) == '<img src="cid:gone@x">'

    def test_new_ids_are_unique(self):
        assert new_cid(1, "example.com") != new_cid(1, "example.com")

    def test_new_ids_carry_the_domain_they_are_given(self):
        assert new_cid(3, "example.com").endswith("@example.com")
        assert new_cid(3, "example.com").startswith("part3.")


class TestAssemblyWithHtml:
    def test_the_fragment_is_quoted_verbatim(self):
        _plain, html, _related = assemble_reply("Kiitos", "<p>Kiitos</p>", ORIGINAL, domain="ours.fi")
        assert '<p class="elementToProof">Moi,</p>' in html
        assert "&lt;p class" not in html, "the fragment must not be escaped"

    def test_inline_images_are_carried_with_new_ids(self):
        _plain, html, related = assemble_reply("Kiitos", "<p>Kiitos</p>", ORIGINAL, domain="ours.fi")
        assert len(related) == 1
        assigned = related[0]["cid"]
        assert assigned.endswith("@ours.fi")
        assert assigned != "image001@outlook.com", "reusing the original id collides across quotes"
        assert f'src="cid:{assigned}"' in html
        assert related[0]["data"] == b"\x89PNG-data"

    def test_a_reference_with_no_part_is_left_as_it_was(self):
        original = {**ORIGINAL, "inline_parts": []}
        _plain, html, related = assemble_reply("K", "<p>K</p>", original)
        assert related == []
        assert 'src="cid:image001@outlook.com"' in html

    def test_an_original_without_html_falls_back_to_escaped_text(self):
        original = {**ORIGINAL, "html": None, "plain": "<b>literal</b>"}
        _plain, html, related = assemble_reply("K", "<p>K</p>", original)
        assert "&lt;b&gt;literal&lt;/b&gt;" in html
        assert related == []

    def test_the_plain_half_still_quotes_text(self):
        plain, _html, _related = assemble_reply("Kiitos", "<p>Kiitos</p>", ORIGINAL)
        assert "> Moi," in plain

    def test_plain_format_carries_nothing(self):
        _plain, html, related = assemble_reply("Kiitos", None, ORIGINAL)
        assert html is None and related == []


class TestMimeAssembly:
    """The shape the parts end up in, built the way create_draft builds it."""

    def _build(self, related):
        import email.message

        from imap_client import DRAFT_POLICY

        msg = email.message.EmailMessage(policy=DRAFT_POLICY)
        msg["To"] = "a@b.c"
        msg["Subject"] = "Re: Raportti"
        msg.set_content("plain half")
        msg.add_alternative("<p>html half</p>", subtype="html")
        if related:
            html_part = msg.get_payload()[-1]
            for part in related:
                html_part.add_related(
                    part["data"],
                    maintype=part["maintype"],
                    subtype=part["subtype"],
                    cid=f"<{part['cid']}>",
                    filename=part.get("filename") or None,
                )
        return email.message_from_bytes(msg.as_bytes())

    def test_related_wraps_the_html_alternative_alone(self):
        _plain, _html, related = assemble_reply("K", "<p>K</p>", ORIGINAL, domain="ours.fi")
        parsed = self._build(related)

        types = [p.get_content_type() for p in parsed.walk()]
        assert types[0] == "multipart/alternative"
        assert "multipart/related" in types
        assert types.index("text/plain") < types.index("multipart/related")

    def test_the_image_travels_inside_the_related_part(self):
        _plain, _html, related = assemble_reply("K", "<p>K</p>", ORIGINAL, domain="ours.fi")
        parsed = self._build(related)

        for part in parsed.walk():
            if part.get_content_type() == "multipart/related":
                inner = [p.get_content_type() for p in part.get_payload()]
                assert inner == ["text/html", "image/png"]
                break
        else:
            raise AssertionError("no multipart/related in the message")

    def test_without_images_there_is_no_related_part(self):
        parsed = self._build([])
        assert "multipart/related" not in [p.get_content_type() for p in parsed.walk()]

    def test_the_content_id_is_the_one_the_markup_points_at(self):
        _plain, html, related = assemble_reply("K", "<p>K</p>", ORIGINAL, domain="ours.fi")
        parsed = self._build(related)

        ids = [(p.get("Content-ID") or "").strip("<>") for p in parsed.walk() if p.get("Content-ID")]
        assert ids == [related[0]["cid"]]
        assert f"cid:{ids[0]}" in html


class TestTheSenderAddress:
    """`From` must be an address. The IMAP login is not always one - on a real
    account here it is "vre" - and every draft built from it carried
    `From: vre`, which no client can send from."""

    def test_an_explicit_address_is_used(self, fake_keyring):
        from imap_client import get_from_address

        fake_keyring.set_password("imap-slim", "acc:from_address", "me@example.com")
        fake_keyring.set_password("imap-slim", "acc:imap_username", "vre")
        assert get_from_address("acc") == "me@example.com"

    def test_a_login_that_is_an_address_is_used(self, fake_keyring):
        from imap_client import get_from_address

        fake_keyring.set_password("imap-slim", "acc:imap_username", "me@example.com")
        assert get_from_address("acc") == "me@example.com"

    def test_the_account_name_is_the_last_resort(self, fake_keyring):
        """Accounts are named by address here; a bare login is not one."""
        from imap_client import get_from_address

        fake_keyring.set_password("imap-slim", "acc@example.com:imap_username", "vre")
        assert get_from_address("acc@example.com") == "acc@example.com"


class TestInlineDisposition:
    """Thunderbird marks carried images inline. With `attachment` a client lists
    them at the bottom instead of showing them inside the quote."""

    def test_carried_images_are_inline(self):
        import email.message

        from imap_client import DRAFT_POLICY

        msg = email.message.EmailMessage(policy=DRAFT_POLICY)
        msg["To"] = "a@b.c"
        msg.set_content("plain")
        msg.add_alternative("<p>html</p>", subtype="html")
        msg.get_payload()[-1].add_related(b"data", maintype="image", subtype="png", cid="<x@y>", filename="image.png", disposition="inline")
        parsed = email.message_from_bytes(msg.as_bytes())

        images = [p for p in parsed.walk() if p.get_content_type() == "image/png"]
        assert [p.get_content_disposition() for p in images] == ["inline"]
        assert images[0].get_filename() == "image.png"
