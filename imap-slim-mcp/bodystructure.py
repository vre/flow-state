"""Utilities for parsing IMAP BODYSTRUCTURE attachment metadata."""

import base64
import logging
import quopri
import re
from html import unescape
from html.parser import HTMLParser

logger = logging.getLogger(__name__)
_short_tuple_warning_emitted = False


class _MLStripper(HTMLParser):
    """Minimal HTML tag stripper for snippet extraction."""

    def __init__(self) -> None:
        """Initialize parser and data buffer."""
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        """Collect plain text chunks."""
        self._parts.append(data)

    def get_data(self) -> str:
        """Return concatenated text."""
        return "".join(self._parts)


def _warn_short_tuple(body: tuple, disposition_index: int) -> None:
    """Log a single debug warning for short BODYSTRUCTURE tuples.

    Args:
        body: BODYSTRUCTURE tuple.
        disposition_index: Expected index for Content-Disposition.
    """
    global _short_tuple_warning_emitted
    if _short_tuple_warning_emitted:
        return
    _short_tuple_warning_emitted = True
    logger.debug(
        "Short BODYSTRUCTURE tuple: len=%s expected_disposition_index=%s value=%r",
        len(body),
        disposition_index,
        body,
    )


def _has_filename(body: tuple, disp: tuple | None) -> bool:
    """Check attachment filename from disposition or Content-Type params.

    Args:
        body: Single-part BODYSTRUCTURE tuple.
        disp: Content-Disposition tuple, if present.

    Returns:
        True when filename/name parameter exists.
    """
    if disp and len(disp) > 1 and isinstance(disp[1], tuple):
        disp_params = disp[1]
        for index in range(0, len(disp_params), 2):
            key = disp_params[index]
            if isinstance(key, bytes) and key.lower() == b"filename":
                return True

    if len(body) > 2 and isinstance(body[2], tuple):
        ct_params = body[2]
        for index in range(0, len(ct_params), 2):
            key = ct_params[index]
            if isinstance(key, bytes) and key.lower() == b"name":
                return True

    return False


def _is_attachment(body: tuple, disp: tuple | None) -> bool:
    """Match read_message attachment predicate.

    Args:
        body: Single-part BODYSTRUCTURE tuple.
        disp: Content-Disposition tuple, if present.

    Returns:
        True for `attachment` or `inline` with filename.
    """
    if not isinstance(disp, tuple) or not disp:
        return False

    disp_type = disp[0]
    if not isinstance(disp_type, bytes):
        return False

    disp_type_lower = disp_type.lower()
    if disp_type_lower == b"attachment":
        return True
    if disp_type_lower == b"inline" and _has_filename(body, disp):
        return True
    return False


def _get_disposition(body: tuple) -> tuple | None:
    """Get Content-Disposition using type-specific BODYSTRUCTURE index.

    Args:
        body: Single-part BODYSTRUCTURE tuple.

    Returns:
        Disposition tuple or None.
    """
    if len(body) < 2:
        _warn_short_tuple(body, 8)
        return None

    maintype = body[0]
    subtype = body[1]
    if not isinstance(maintype, bytes):
        return None

    maintype_lower = maintype.lower()
    if maintype_lower == b"message" and isinstance(subtype, bytes) and subtype.lower() == b"rfc822":
        disposition_index = 11
    elif maintype_lower == b"text":
        disposition_index = 9
    else:
        disposition_index = 8

    if len(body) <= disposition_index:
        _warn_short_tuple(body, disposition_index)
        return None

    disposition = body[disposition_index]
    return disposition if isinstance(disposition, tuple) else None


def _extract_charset(body: tuple) -> bytes:
    """Extract charset from BODYSTRUCTURE params, default utf-8.

    Args:
        body: Single-part BODYSTRUCTURE tuple.

    Returns:
        Charset bytes.
    """
    params = body[2] if len(body) > 2 else None
    if isinstance(params, tuple):
        for index in range(0, len(params), 2):
            key = params[index]
            if not isinstance(key, bytes) or key.lower() != b"charset":
                continue
            if index + 1 >= len(params):
                break
            value = params[index + 1]
            if isinstance(value, bytes):
                return value
            if isinstance(value, str):
                return value.encode("utf-8", errors="ignore")
    return b"utf-8"


def _find_text_subtype(body: tuple | None, subtype: bytes, prefix: str = "") -> tuple[str, bytes, bytes] | None:
    """Find first text/* part matching subtype and not marked as attachment.

    Args:
        body: BODYSTRUCTURE tuple (or None).
        subtype: MIME subtype to match.
        prefix: Part number prefix for recursion.

    Returns:
        (part_number, charset, transfer_encoding) or None.
    """
    if not isinstance(body, tuple) or not body:
        return None

    if isinstance(body[0], list):
        for index, part in enumerate(body[0], 1):
            part_num = f"{prefix}.{index}" if prefix else str(index)
            result = _find_text_subtype(part, subtype, part_num)
            if result:
                return result
        return None

    if len(body) < 2 or not isinstance(body[0], bytes) or not isinstance(body[1], bytes):
        return None

    if body[0].lower() != b"text" or body[1].lower() != subtype:
        return None

    disposition = _get_disposition(body)
    if _is_attachment(body, disposition):
        return None

    charset = _extract_charset(body)
    encoding = body[5] if len(body) > 5 and isinstance(body[5], bytes) else b"7BIT"
    return (prefix or "1", charset, encoding)


def find_text_part(body: tuple | None, prefix: str = "") -> tuple[str, bytes, bytes] | None:
    """Find first text/plain body part (not attachment).

    Args:
        body: BODYSTRUCTURE tuple (or None).
        prefix: Part number prefix for recursion.

    Returns:
        (part_number, charset, transfer_encoding) or None.
    """
    return _find_text_subtype(body, b"plain", prefix)


def find_html_part(body: tuple | None, prefix: str = "") -> tuple[str, bytes, bytes] | None:
    """Find first text/html body part (not attachment).

    Args:
        body: BODYSTRUCTURE tuple (or None).
        prefix: Part number prefix for recursion.

    Returns:
        (part_number, charset, transfer_encoding) or None.
    """
    return _find_text_subtype(body, b"html", prefix)


def _strip_html_tags(text: str) -> str:
    """Strip style/script blocks and HTML tags from text.

    Args:
        text: HTML text.

    Returns:
        Plain text content.
    """
    no_blocks = re.sub(r"(?is)<(style|script)\b[^>]*>.*?</\1>", " ", text)
    stripper = _MLStripper()
    stripper.feed(no_blocks)
    stripper.close()
    return unescape(stripper.get_data())


def _decode_transfer_bytes(raw_bytes: bytes, encoding: bytes) -> bytes | None:
    """Decode transfer-encoded message bytes.

    Args:
        raw_bytes: Raw bytes from IMAP BODY.PEEK fetch.
        encoding: Transfer encoding token from BODYSTRUCTURE.

    Returns:
        Decoded bytes, or None for unknown encoding.
    """
    normalized = encoding.upper() if isinstance(encoding, bytes) else str(encoding).upper().encode("ascii", errors="ignore")

    if normalized in {b"", b"7BIT", b"8BIT", b"BINARY"}:
        return raw_bytes
    if normalized == b"BASE64":
        compact = re.sub(rb"\s+", b"", raw_bytes)
        usable = len(compact) - (len(compact) % 4)
        if usable <= 0:
            return b""
        return base64.b64decode(compact[:usable])
    if normalized == b"QUOTED-PRINTABLE":
        return quopri.decodestring(raw_bytes)
    return None


def extract_snippet(raw_bytes: bytes, charset: bytes, encoding: bytes, is_html: bool = False, max_chars: int = 100) -> str:
    """Decode raw IMAP body bytes and return truncated snippet.

    Args:
        raw_bytes: Raw bytes from BODY.PEEK partial fetch.
        charset: Character set from BODYSTRUCTURE.
        encoding: Transfer encoding from BODYSTRUCTURE.
        is_html: Whether to strip HTML tags before truncation.
        max_chars: Truncation length.

    Returns:
        Decoded, truncated text. Empty string on decode failures.
    """
    if not raw_bytes or max_chars <= 0:
        return ""

    try:
        decoded_bytes = _decode_transfer_bytes(raw_bytes, encoding)
        if decoded_bytes is None:
            return ""

        charset_text = charset.decode("ascii", errors="ignore") if isinstance(charset, bytes) else str(charset)
        if not charset_text:
            charset_text = "utf-8"
        text = decoded_bytes.decode(charset_text, errors="ignore")

        if is_html:
            text = _strip_html_tags(text)

        text = " ".join(text.split())
        if not text:
            return ""
        if len(text) <= max_chars:
            return text

        cut = text.rfind(" ", 0, max_chars + 1)
        if cut <= 0:
            cut = max_chars
        return text[:cut].rstrip() + "..."
    except Exception:
        return ""


def get_body_peek(msg_data: dict, section: str) -> bytes | None:
    """Get BODY.PEEK bytes from server-dependent response keys.

    Args:
        msg_data: Message fetch response payload.
        section: IMAP section id, such as ``1`` or ``1.2``.

    Returns:
        Raw body bytes when found.
    """
    prefix = f"BODY[{section}]".encode()
    for key, value in msg_data.items():
        if isinstance(key, bytes) and key.startswith(prefix) and isinstance(value, bytes):
            return value
    return None


def count_attachments(body: tuple | None) -> int:
    """Count attachments from IMAP BODYSTRUCTURE.

    Args:
        body: BODYSTRUCTURE tuple (or None).

    Returns:
        Number of attachments.
    """
    if not isinstance(body, tuple) or not body:
        return 0

    if isinstance(body[0], list):
        return sum(count_attachments(part) for part in body[0])

    disp = _get_disposition(body)
    return 1 if _is_attachment(body, disp) else 0
