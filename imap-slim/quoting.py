"""Building a reply around a message the client fetched.

The model supplies the new text and nothing else. Everything here works on an
original that has already been fetched, so it is pure: no IMAP, no rendering,
nothing that needs a connection to test.

The quoted original is never re-interpreted. It is not passed through the
markdown renderer, and it is not rewrapped - both would alter what someone else
wrote, and a quote that has been altered is a misquote.
"""

import html
import re

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


def assemble_reply(new_plain: str, new_html: str | None, original: dict) -> tuple[str, str | None]:
    """Put the new text above the quoted original, in both parts.

    Returns (plain, html). `html` is None when the caller is sending plain only,
    in which case no HTML half is built at all.
    """
    quoted_text = original.get("plain") or ""
    attribution = attribution_line(original.get("date"), original.get("from_display") or original.get("from_addr") or "")

    plain_parts = [new_plain.rstrip()]
    if attribution:
        plain_parts.append(attribution)
    plain_parts.append(quote_plain(quoted_text))
    plain = "\n\n".join(part for part in plain_parts if part) + "\n"

    if new_html is None:
        return plain, None

    cite = (original.get("message_id") or "").strip().strip("<>")
    cite_attr = f' cite="mid:{html.escape(cite, quote=True)}"' if cite else ""
    html_parts = [new_html]
    if attribution:
        html_parts.append(f'<div class="moz-cite-prefix">{html.escape(attribution, quote=False)}<br></div>')
    html_parts.append(f'<blockquote type="cite"{cite_attr}>\n{quote_html_text(quoted_text)}\n</blockquote>')
    return plain, "\n".join(html_parts)
