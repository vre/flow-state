"""What replace must carry over, and what it must refuse to write.

replace appends a new message and expunges the old one. Everything the old
message held that the caller did not resupply has to survive that, because the
expunge is not reversible.
"""

import email
import email.message
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "imap-slim"))

from imap_client import IMAPError, appended_uid, modify_draft  # noqa: E402


def _draft_with_attached_email() -> email.message.EmailMessage:
    """A draft carrying a forwarded .eml, which is how the loss was found."""
    inner = email.message.EmailMessage()
    inner["Subject"] = "the forwarded thing"
    inner["From"] = "sender@example.com"
    inner.set_content("body of the forwarded message")

    outer = email.message.EmailMessage()
    outer["Subject"] = "carrier"
    outer.set_content("draft body")
    outer.add_attachment(inner, filename="forwarded.eml")
    # Parsed from bytes, as it arrives from the server.
    return email.message_from_bytes(outer.as_bytes())


def _draft_with_pdf() -> email.message.EmailMessage:
    msg = email.message.EmailMessage()
    msg["Subject"] = "carrier"
    msg.set_content("draft body")
    msg.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="report.pdf")
    return email.message_from_bytes(msg.as_bytes())


def _run_modify(original_msg, appended=None, **kwargs):
    """Call modify_draft against a mocked connection, returning (result, appended_bytes).

    `appended` is filled in by the fake APPEND, so a caller expecting a refusal
    can check that nothing was written.
    """
    appended = {} if appended is None else appended

    def _append(folder, payload, flags=None):
        appended["folder"] = folder
        appended["payload"] = payload
        return b"[APPENDUID 1 77] APPEND completed"

    client = MagicMock()
    client.select_folder.return_value = {}
    client.append.side_effect = _append
    client.list_folders.return_value = [([b"\\Drafts"], b"/", "Drafts")]
    client.capabilities.return_value = [b"IMAP4REV1", b"UIDPLUS"]

    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=client)
    ctx.__exit__ = MagicMock(return_value=False)

    envelope = MagicMock()
    envelope.subject = b"carrier"
    envelope.to = None
    envelope.cc = None

    with (
        patch("session.get_session") as mock_session,
        patch("imap_client.get_credentials", return_value=("s", 993, "me@example.com", "pw")),
        patch("imap_client.is_drafts_folder", return_value=True),
    ):
        mock_session.return_value.connection_ctx.return_value = ctx
        result = modify_draft(
            folder="Drafts",
            message_id=1,
            prefetched_draft=(envelope, original_msg),
            **kwargs,
        )
    return result, appended.get("payload")


class TestAttachmentsSurviveReplace:
    def test_attached_email_is_carried_over(self):
        """message/rfc822 has no decoded payload; skipping it lost the file."""
        result, payload = _run_modify(_draft_with_attached_email(), body="new body")

        assert b"body of the forwarded message" in payload
        names = [a["name"] for a in result["attachments"]]
        assert names == ["forwarded.eml"]

    def test_attached_email_is_not_unpacked_into_its_parts(self):
        """The carrier keeps one attachment, not the inner message's parts."""
        result, _payload = _run_modify(_draft_with_attached_email(), body="new body")

        assert len(result["attachments"]) == 1

    def test_ordinary_attachment_still_survives(self):
        result, payload = _run_modify(_draft_with_pdf(), body="new body")

        rebuilt = email.message_from_bytes(payload)
        kept = [p.get_payload(decode=True) for p in rebuilt.walk() if p.get_filename() == "report.pdf"]
        assert kept == [b"%PDF-1.4 fake"]
        assert [a["name"] for a in result["attachments"]] == ["report.pdf"]

    def test_unpreservable_attachment_refuses_before_writing(self):
        """Nothing is appended and nothing deleted when a part cannot be copied."""
        # A multipart attachment: get_payload(decode=True) is None for it, and
        # it is not an attached message either, so there is nothing to copy.
        bundle = email.message.EmailMessage()
        bundle["Subject"] = "carrier"
        bundle.set_content("draft body")
        bundle.add_attachment(b"x", maintype="application", subtype="octet-stream", filename="placeholder")
        raw = email.message_from_bytes(bundle.as_bytes())
        for part in raw.walk():
            if part.get_filename() == "placeholder":
                part.set_type("multipart/related")
                part.set_payload([email.message_from_string("Content-Type: text/plain\n\nx")])

        appended = {}
        with pytest.raises(IMAPError, match="placeholder"):
            _run_modify(raw, appended=appended, body="new body")
        assert appended == {}, "the replace wrote before it refused"


class TestFieldsAreClearedWhenAsked:
    def test_cc_empty_string_clears_the_header(self):
        msg = _draft_with_pdf()
        envelope_cc = MagicMock()
        envelope_cc.mailbox = b"old"
        envelope_cc.host = b"example.com"

        appended = {}

        def _append(folder, payload, flags=None):
            appended["payload"] = payload
            return b"[APPENDUID 1 77] APPEND completed"

        client = MagicMock()
        client.select_folder.return_value = {}
        client.append.side_effect = _append
        client.list_folders.return_value = [([b"\\Drafts"], b"/", "Drafts")]
        client.capabilities.return_value = [b"UIDPLUS"]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=client)
        ctx.__exit__ = MagicMock(return_value=False)

        envelope = MagicMock()
        envelope.subject = b"carrier"
        envelope.to = None
        envelope.cc = [envelope_cc]

        with (
            patch("session.get_session") as mock_session,
            patch("imap_client.get_credentials", return_value=("s", 993, "me@example.com", "pw")),
            patch("imap_client.is_drafts_folder", return_value=True),
        ):
            mock_session.return_value.connection_ctx.return_value = ctx
            modify_draft(folder="Drafts", message_id=1, body="new", cc="", prefetched_draft=(envelope, msg))

        assert b"old@example.com" not in appended["payload"]

    def test_cc_not_supplied_keeps_the_original(self):
        msg = _draft_with_pdf()
        envelope_cc = MagicMock()
        envelope_cc.mailbox = b"old"
        envelope_cc.host = b"example.com"

        appended = {}

        def _append(folder, payload, flags=None):
            appended["payload"] = payload
            return b"[APPENDUID 1 77] APPEND completed"

        client = MagicMock()
        client.select_folder.return_value = {}
        client.append.side_effect = _append
        client.list_folders.return_value = [([b"\\Drafts"], b"/", "Drafts")]
        client.capabilities.return_value = [b"UIDPLUS"]
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=client)
        ctx.__exit__ = MagicMock(return_value=False)

        envelope = MagicMock()
        envelope.subject = b"carrier"
        envelope.to = None
        envelope.cc = [envelope_cc]

        with (
            patch("session.get_session") as mock_session,
            patch("imap_client.get_credentials", return_value=("s", 993, "me@example.com", "pw")),
            patch("imap_client.is_drafts_folder", return_value=True),
        ):
            mock_session.return_value.connection_ctx.return_value = ctx
            modify_draft(folder="Drafts", message_id=1, body="new", prefetched_draft=(envelope, msg))

        assert b"old@example.com" in appended["payload"]


class TestAppendedUid:
    def test_uid_is_parsed_from_the_append_response(self):
        assert appended_uid(b"[APPENDUID 1234567 4242] APPEND completed") == 4242

    def test_uid_is_none_without_uidplus(self):
        assert appended_uid(b"APPEND completed") is None
        assert appended_uid(None) is None

    def test_replace_reports_the_new_uid(self):
        result, _payload = _run_modify(_draft_with_pdf(), body="new body")
        assert result["uid"] == 77
