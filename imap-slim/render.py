"""Rendering shared by every front-end.

Pure functions: results and exceptions in, display text out. No IMAP, no MCP.
The CLI in a later cut needs the same output, and duplicating it would let the
two drift apart silently.

The inline response bodies inside use_mail's branches deliberately stay there
until that second consumer exists - shaping an interface around a caller that
does not exist yet is guessing.
"""

import re

from imap_client import ConnectionFailure, is_transport_failure
from imapclient.exceptions import LoginError


def format_attachment_line(attachments: list[dict]) -> str:
    """Format attachment info for draft response."""
    if not attachments:
        return ""
    parts = []
    for att in attachments:
        size = att["size"]
        if size >= 1024 * 1024:
            size_str = f"{size / (1024 * 1024):.1f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = f"{size} B"
        parts.append(f"{att['name']} ({size_str})")
    return f"\n**Attachments:** {', '.join(parts)}"


# Quota messages must mention connections. "Maximum login attempts exceeded"
# contains both "maximum" and "exceeded" and is not a quota message.
_QUOTA_PATTERN = re.compile(
    r"too many connections|maximum number of connections|connection limit|too many concurrent",
    re.IGNORECASE,
)


def _find_cause(exc: BaseException, wanted: type) -> BaseException | None:
    """First exception of the wanted type in the chain, or None."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, wanted):
            return current
        current = current.__cause__ or current.__context__
    return None


def classify_connection_error(exc: BaseException) -> str | None:
    """Name a connection failure for the caller, or None if it is not one.

    Three causes need three different actions, and today they all arrive as one
    opaque string. Called from both exception handlers in use_mail, because
    `except IMAPError` precedes `except Exception` and would otherwise consume
    the wrapped failures this exists to catch.
    """
    where = ""
    if isinstance(exc, ConnectionFailure):
        where = f" (stage: {exc.stage}, after {exc.elapsed:.1f}s)"

    login_error = _find_cause(exc, LoginError)
    if login_error is not None:
        text = str(login_error)
        if _QUOTA_PATTERN.search(text):
            return (
                f"**Connection limit reached**{where}. The server refused a new connection because "
                "the account's quota is in use - other Claude sessions or your mail client are "
                f"holding it. Close one and retry.\n\nServer said: {text}"
            )
        return (
            f"**Login rejected by the server**{where}. This can be wrong credentials, but also a "
            "disabled account, a policy block, or a required second factor - the server does not "
            f"say which.\n\nServer said: {text}"
        )

    if is_transport_failure(exc):
        return (
            f"**Connection to the mail server was lost**{where}. The cached connection was dropped "
            "and will be rebuilt on the next call. If this repeats on every call, the network path "
            "to the server is down."
        )

    return None


def format_description(format_type: str) -> str:
    """One line naming what the body was actually turned into."""
    if format_type == "plain":
        return "plain text only"
    return "markdown \u2192 HTML + plain text"


def format_flags(flags: list[str]) -> str:
    """Format IMAP flags for display: [seen,flagged] #keyword."""
    std_flags = []
    tags = []
    for f in flags:
        if f.startswith("\\"):
            std_flags.append(f[1:].lower())
        else:
            tags.append(f)
    parts = []
    if std_flags:
        parts.append(f"[{','.join(std_flags)}]")
    if tags:
        parts.append(" ".join(f"#{t}" for t in tags))
    return " ".join(parts)


# Context poisoning protection - see injection_defense module
POTENTIAL_INJECTION_WARNING = "**SECURITY NOTICE:** Potential prompt injection patterns detected; suspicious content removed or escaped."
