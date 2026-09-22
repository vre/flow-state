"""Building a reply around a message the client fetched.

The model supplies the new text and nothing else. Everything here works on an
original that has already been fetched, so it is pure: no IMAP, no rendering,
nothing that needs a connection to test.

The quoted original is never re-interpreted. It is not passed through the
markdown renderer, and it is not rewrapped - both would alter what someone else
wrote, and a quote that has been altered is a misquote.
"""

import email.utils
import html
import re
import secrets

# Thunderbird's attribution, pinned rather than produced by a locale-dependent
# formatter: it renders in the user's locale, while this process inherits
# whatever locale the MCP or CLI happened to start with. The same mailbox would
# otherwise produce "19.8.2026" or "8/19/2026" depending on how it was launched.
ATTRIBUTION = "On {d}.{m}.{y} {hour}.{minute:02d}, {who} wrote:"

_RE_PREFIX = re.compile(r"^\s*re\s*:", re.IGNORECASE)


def attribution_line(date, who: str) -> str | None:
    """Thunderbird's attribution line, or None when there is no usable date."""
    if date is None or not who:
        return None
    try:
        return ATTRIBUTION.format(d=date.day, m=date.month, y=date.year, hour=date.hour, minute=date.minute, who=who)
    except AttributeError:
        return None


def quote_plain(text: str) -> str:
    """Prefix every line with "> ", and nothing else.

    A blank line becomes ">" rather than "> ", which is what mail clients emit
    and what keeps trailing whitespace out of the message. Lines that are
    already quoted simply gain another level, as they should.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(">" if not line.strip() else f"> {line}" for line in lines)


def quote_html_text(text: str) -> str:
    """The original's text as HTML, escaped, with line breaks preserved.

    Cut 2 replaces this with the original's own HTML fragment. Until then the
    quote is text that cannot turn into markup: `<b>` in someone's mail is the
    four characters they typed.
    """
    escaped = html.escape(text.replace("\r\n", "\n").replace("\r", "\n"), quote=False)
    return "<br>\n".join(escaped.split("\n"))


def reply_subject(original_subject: str) -> str:
    """`Re:` once, never twice."""
    subject = (original_subject or "").strip()
    if not subject:
        return "Re:"
    if _RE_PREFIX.match(subject):
        return subject
    return f"Re: {subject}"


def reply_headers(original: dict) -> dict:
    """Recipient, subject and threading for a reply to `original`.

    References chains: the original's own References plus its Message-ID, which
    is what keeps a thread together in every client that groups by it.
    """
    message_id = (original.get("message_id") or "").strip()
    references = (original.get("references") or "").strip()
    chain = " ".join(part for part in (references, message_id) if part)

    return {
        "to": original.get("reply_to") or original.get("from_addr") or "",
        "subject": reply_subject(original.get("subject", "")),
        "in_reply_to": message_id or None,
        "references": chain or None,
    }


def quoted_html(original: dict, domain: str | None = None) -> tuple[str, list[dict]]:
    """What goes inside the blockquote, and the parts it needs alongside it.

    An HTML original is quoted by its own markup, verbatim - that is what the
    sender recognises as their mail, and it is what every client does. The
    inline images it points at are carried with it under fresh Content-IDs;
    real attachments are not, which is also what Thunderbird does.

    An original with no HTML half falls back to its text, escaped.
    """
    fragment = body_fragment(original.get("html") or "")
    if not fragment:
        return quote_html_text(original.get("plain") or ""), []

    available = {part["cid"]: part for part in original.get("inline_parts") or []}
    mapping: dict[str, str] = {}
    related: list[dict] = []
    for index, cid in enumerate(referenced_cids(fragment), start=1):
        part = available.get(cid)
        if part is None:
            # A reference to a part the message does not carry. Leaving it
            # alone keeps the quote unaltered; the image was already broken.
            continue
        assigned = new_cid(index, domain)
        mapping[cid] = assigned
        related.append({**part, "cid": assigned})

    return rewrite_cids(fragment, mapping), related


def assemble_reply(new_plain: str, new_html: str | None, original: dict, domain: str | None = None) -> tuple[str, str | None, list[dict]]:
    """Put the new text above the quoted original, in both parts.

    Returns (plain, html, related). `html` is None when the caller is sending
    plain only, in which case no HTML half is built and nothing is carried.
    """
    quoted_text = original.get("plain") or ""
    attribution = attribution_line(original.get("date"), original.get("from_display") or original.get("from_addr") or "")

    plain_parts = [new_plain.rstrip()]
    if attribution:
        plain_parts.append(attribution)
    plain_parts.append(quote_plain(quoted_text))
    plain = "\n\n".join(part for part in plain_parts if part) + "\n"

    if new_html is None:
        return plain, None, []

    inner, related = quoted_html(original, domain)
    cite = (original.get("message_id") or "").strip().strip("<>")
    cite_attr = f' cite="mid:{html.escape(cite, quote=True)}"' if cite else ""
    html_parts = [new_html]
    if attribution:
        html_parts.append(f'<div class="moz-cite-prefix">{html.escape(attribution, quote=False)}<br></div>')
    html_parts.append(f'<blockquote type="cite"{cite_attr}>\n{inner}\n</blockquote>')
    return plain, "\n".join(html_parts), related


_BODY = re.compile(r"<body[^>]*>(.*)</body>", re.IGNORECASE | re.DOTALL)
_HEAD = re.compile(r"<head[^>]*>.*?</head>", re.IGNORECASE | re.DOTALL)
_DOCTYPE = re.compile(r"<!DOCTYPE[^>]*>|</?html[^>]*>", re.IGNORECASE)
_CID_REF = re.compile(r"""(?P<attr>src|href)=(?P<q>["'])cid:(?P<cid>[^"']+)(?P=q)""", re.IGNORECASE)


def body_fragment(html_document: str) -> str:
    """The quotable inside of an HTML message.

    Thunderbird quotes the body content and leaves the surrounding document
    behind, which is what keeps the original's `<style>` inside the blockquote
    where it belongs instead of restyling the reply around it. A message with no
    `<body>` is already a fragment.
    """
    if not html_document:
        return ""
    match = _BODY.search(html_document)
    if match:
        return match.group(1).strip()
    stripped = _DOCTYPE.sub("", _HEAD.sub("", html_document))
    return stripped.strip()


def referenced_cids(fragment: str) -> list[str]:
    """The Content-IDs a fragment points at, in the order they appear."""
    seen = []
    for match in _CID_REF.finditer(fragment):
        cid = match.group("cid")
        if cid not in seen:
            seen.append(cid)
    return seen


def new_cid(index: int, domain: str | None = None) -> str:
    """A fresh Content-ID, shaped like the ones Thunderbird generates.

    The original's ids are not reused: two quoted messages in one thread can
    carry the same id, and the reply would then have two parts claiming it.
    """
    if not domain:
        domain = email.utils.make_msgid().rsplit("@", 1)[1].rstrip(">")
    return f"part{index}.{secrets.token_hex(4)}.{secrets.token_hex(4)}@{domain}"


def rewrite_cids(fragment: str, mapping: dict[str, str]) -> str:
    """Point the fragment's cid: references at their new Content-IDs."""

    def _swap(match):
        cid = match.group("cid")
        replacement = mapping.get(cid, cid)
        return f"{match.group('attr')}={match.group('q')}cid:{replacement}{match.group('q')}"

    return _CID_REF.sub(_swap, fragment)
