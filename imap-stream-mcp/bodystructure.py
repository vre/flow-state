"""Utilities for parsing IMAP BODYSTRUCTURE attachment metadata."""

import logging

logger = logging.getLogger(__name__)
_short_tuple_warning_emitted = False


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
