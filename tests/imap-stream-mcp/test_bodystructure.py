"""Tests for BODYSTRUCTURE attachment counting."""

import logging

import bodystructure
from bodystructure import count_attachments

SIMPLE_TEXT = (
    b"TEXT",
    b"PLAIN",
    (b"CHARSET", b"utf-8"),
    None,
    None,
    b"7BIT",
    100,
    5,
    None,
    None,
    None,
    None,
)

MIXED_1ATT = (
    [
        SIMPLE_TEXT,
        (
            b"APPLICATION",
            b"PDF",
            (b"NAME", b"report.pdf"),
            None,
            None,
            b"BASE64",
            5000,
            None,
            (b"attachment", (b"filename", b"report.pdf")),
            None,
            None,
        ),
    ],
    b"MIXED",
    (b"BOUNDARY", b"==abc=="),
    None,
    None,
    None,
)

MIXED_3ATT = (
    [
        SIMPLE_TEXT,
        (
            b"APPLICATION",
            b"PDF",
            (b"NAME", b"a.pdf"),
            None,
            None,
            b"BASE64",
            5000,
            None,
            (b"attachment", (b"filename", b"a.pdf")),
            None,
            None,
        ),
        (
            b"APPLICATION",
            b"ZIP",
            (b"NAME", b"b.zip"),
            None,
            None,
            b"BASE64",
            6000,
            None,
            (b"attachment", (b"filename", b"b.zip")),
            None,
            None,
        ),
        (
            b"IMAGE",
            b"PNG",
            (b"NAME", b"c.png"),
            None,
            None,
            b"BASE64",
            700,
            None,
            (b"inline", (b"filename", b"c.png")),
            None,
            None,
        ),
    ],
    b"MIXED",
    (b"BOUNDARY", b"==xyz=="),
    None,
    None,
    None,
)

INLINE_IMG = (
    b"IMAGE",
    b"PNG",
    (b"NAME", b"logo.png"),
    None,
    None,
    b"BASE64",
    2000,
    None,
    (b"inline", (b"filename", b"logo.png")),
    None,
    None,
)

INLINE_NO_NAME = (
    b"IMAGE",
    b"PNG",
    None,
    None,
    None,
    b"BASE64",
    2000,
    None,
    (b"inline", None),
    None,
    None,
)

INLINE_CT_NAME = (
    b"IMAGE",
    b"PNG",
    (b"NAME", b"chart.png"),
    None,
    None,
    b"BASE64",
    3000,
    None,
    (b"inline", None),
    None,
    None,
)

NESTED_MULTIPART = (
    [
        (
            [
                (
                    b"TEXT",
                    b"HTML",
                    (b"CHARSET", b"utf-8"),
                    None,
                    None,
                    b"7BIT",
                    50,
                    2,
                    None,
                    None,
                    None,
                    None,
                ),
                SIMPLE_TEXT,
            ],
            b"ALTERNATIVE",
            (b"BOUNDARY", b"==alt=="),
            None,
            None,
            None,
        ),
        (
            b"APPLICATION",
            b"PDF",
            (b"NAME", b"nested.pdf"),
            None,
            None,
            b"BASE64",
            9000,
            None,
            (b"attachment", (b"filename", b"nested.pdf")),
            None,
            None,
        ),
    ],
    b"MIXED",
    (b"BOUNDARY", b"==mix=="),
    None,
    None,
    None,
)

MESSAGE_RFC822_ATT = (
    b"MESSAGE",
    b"RFC822",
    None,
    None,
    None,
    b"7BIT",
    1234,
    None,
    SIMPLE_TEXT,
    42,
    None,
    (b"attachment", (b"filename", b"forwarded.eml")),
    None,
    None,
)

MESSAGE_RFC822_SHORT = (
    b"MESSAGE",
    b"RFC822",
    None,
    None,
    None,
    b"7BIT",
    1234,
    None,
    SIMPLE_TEXT,
    42,
)

SHORT_TEXT_NO_EXT = (
    b"TEXT",
    b"PLAIN",
    None,
    None,
    None,
    b"7BIT",
    20,
    1,
)


def test_simple_text_has_zero_attachments():
    """TEXT/PLAIN without disposition should count as zero."""
    assert count_attachments(SIMPLE_TEXT) == 0


def test_multipart_with_one_attachment_counts_one():
    """Multipart/mixed with one attachment should count one."""
    assert count_attachments(MIXED_1ATT) == 1


def test_multipart_with_three_attachments_counts_three():
    """Should count attachment and inline-with-filename leaves recursively."""
    assert count_attachments(MIXED_3ATT) == 3


def test_inline_with_disposition_filename_counts():
    """Inline with filename parameter matches read_message predicate."""
    assert count_attachments(INLINE_IMG) == 1


def test_inline_without_filename_does_not_count():
    """CID inline without filename should not count as attachment."""
    assert count_attachments(INLINE_NO_NAME) == 0


def test_inline_with_content_type_name_counts():
    """Content-Type name= fallback should count inline part."""
    assert count_attachments(INLINE_CT_NAME) == 1


def test_nested_multipart_counts_leaf_attachments():
    """Nested multipart should recurse and count only leaf attachments."""
    assert count_attachments(NESTED_MULTIPART) == 1


def test_message_rfc822_disposition_index_11_counts_attachment():
    """message/rfc822 disposition must be read from index 11."""
    assert count_attachments(MESSAGE_RFC822_ATT) == 1


def test_message_rfc822_short_tuple_without_disposition_is_zero():
    """Missing extension fields should gracefully return zero."""
    assert count_attachments(MESSAGE_RFC822_SHORT) == 0


def test_short_tuple_returns_zero_and_logs_debug_once(caplog):
    """Malformed short tuples should not crash and should emit one debug warning."""
    bodystructure._short_tuple_warning_emitted = False
    caplog.set_level(logging.DEBUG)

    assert count_attachments(SHORT_TEXT_NO_EXT) == 0
    assert count_attachments(SHORT_TEXT_NO_EXT) == 0

    debug_messages = [r.message for r in caplog.records if r.message.startswith("Short BODYSTRUCTURE tuple:")]
    assert len(debug_messages) == 1
