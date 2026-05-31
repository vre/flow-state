"""Tests for BODYSTRUCTURE attachment counting."""

import base64
import logging
import quopri

import bodystructure
from bodystructure import _extract_charset, _strip_html_tags, count_attachments, extract_snippet, find_html_part, find_text_part

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

HTML_ONLY = (
    b"TEXT",
    b"HTML",
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

TEXT_ATTACHMENT = (
    b"TEXT",
    b"PLAIN",
    (b"CHARSET", b"utf-8"),
    None,
    None,
    b"7BIT",
    100,
    5,
    None,
    (b"attachment", (b"filename", b"note.txt")),
    None,
    None,
)

HTML_ATTACHMENT = (
    b"TEXT",
    b"HTML",
    (b"CHARSET", b"utf-8"),
    None,
    None,
    b"7BIT",
    100,
    5,
    None,
    (b"attachment", (b"filename", b"snippet.html")),
    None,
    None,
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


def test_find_text_part_none_returns_none():
    """None BODYSTRUCTURE should return None."""
    assert find_text_part(None) is None


def test_find_html_part_none_returns_none():
    """None BODYSTRUCTURE should return None."""
    assert find_html_part(None) is None


def test_find_text_part_simple_text():
    """Simple text body should resolve to part 1."""
    assert find_text_part(SIMPLE_TEXT) == ("1", b"utf-8", b"7BIT")


def test_find_text_part_nested_multipart():
    """Nested multipart should return text/plain at part 1.2."""
    assert find_text_part(NESTED_MULTIPART) == ("1.2", b"utf-8", b"7BIT")


def test_find_text_part_skips_text_attachment():
    """text/plain attachment should not be used as snippet source."""
    assert find_text_part(TEXT_ATTACHMENT) is None


def test_find_text_part_html_only_returns_none():
    """HTML-only body should not match text/plain lookup."""
    assert find_text_part(HTML_ONLY) is None


def test_find_html_part_html_only():
    """HTML-only body should resolve to part 1."""
    assert find_html_part(HTML_ONLY) == ("1", b"utf-8", b"7BIT")


def test_find_html_part_nested_multipart():
    """Nested multipart should return text/html at part 1.1."""
    assert find_html_part(NESTED_MULTIPART) == ("1.1", b"utf-8", b"7BIT")


def test_find_html_part_skips_html_attachment():
    """text/html attachment should not be used as snippet source."""
    assert find_html_part(HTML_ATTACHMENT) is None


def test_extract_charset_with_params():
    """Charset should be read from params tuple."""
    assert _extract_charset(SIMPLE_TEXT) == b"utf-8"


def test_extract_charset_without_params_defaults_utf8():
    """Missing params should default to utf-8."""
    no_params = (b"TEXT", b"PLAIN", None, None, None, b"7BIT")
    assert _extract_charset(no_params) == b"utf-8"


def test_extract_charset_non_tuple_params_defaults_utf8():
    """Non-tuple params should default to utf-8."""
    non_tuple_params = (b"TEXT", b"PLAIN", b"CHARSET", None, None, b"7BIT")
    assert _extract_charset(non_tuple_params) == b"utf-8"


def test_extract_charset_odd_params_tuple_defaults_utf8():
    """Odd-length tuple should not raise and should default to utf-8."""
    odd_params = (b"TEXT", b"PLAIN", (b"CHARSET",), None, None, b"7BIT")
    assert _extract_charset(odd_params) == b"utf-8"


def test_extract_snippet_invalid_charset_returns_empty():
    """Invalid charset should fail gracefully."""
    assert extract_snippet(b"hello", b"INVALID-XYZ", b"7BIT") == ""


def test_extract_snippet_7bit_utf8_truncates():
    """7BIT snippet should truncate and append ellipsis."""
    raw = ("Lorem ipsum dolor sit amet consectetur adipiscing elit " * 6).encode("utf-8")
    snippet = extract_snippet(raw, b"utf-8", b"7BIT")
    assert snippet.endswith("...")
    assert len(snippet) <= 103
    assert "Lorem ipsum" in snippet


def test_extract_snippet_truncates_on_word_boundary():
    """Truncation should use previous whitespace instead of splitting words."""
    snippet = extract_snippet(b"alpha beta gamma delta", b"utf-8", b"7BIT", max_chars=13)
    assert snippet == "alpha beta..."


def test_extract_snippet_base64_decodes_and_truncates():
    """BASE64 snippet should decode before truncation."""
    raw = base64.b64encode(("Base64 content line " * 20).encode("utf-8"))
    snippet = extract_snippet(raw, b"utf-8", b"BASE64")
    assert snippet.endswith("...")
    assert "Base64 content line" in snippet


def test_extract_snippet_quoted_printable_decodes_and_truncates():
    """Quoted-printable snippet should decode before truncation."""
    encoded = quopri.encodestring(("Quoted printable content " * 20).encode("utf-8"))
    snippet = extract_snippet(encoded, b"utf-8", b"QUOTED-PRINTABLE")
    assert snippet.endswith("...")
    assert "Quoted printable content" in snippet


def test_extract_snippet_html_strips_tags():
    """HTML snippet should remove tags and collapse whitespace."""
    raw = (
        b"<html><body><h1>Title</h1><p>Hello <b>world</b> and <i>friends</i>.</p>"
        b"<style>.x{color:red}</style><script>alert('x')</script></body></html>"
    )
    snippet = extract_snippet(raw, b"utf-8", b"7BIT", is_html=True, max_chars=200)
    assert "Title" in snippet
    assert "Hello world and friends." in snippet
    assert "alert('x')" not in snippet
    assert "color:red" not in snippet
    assert "<h1>" not in snippet


def test_extract_snippet_truncated_utf8_boundary_no_crash():
    """Truncated multibyte UTF-8 should not raise."""
    raw = "Price € per item".encode()[:-1]
    snippet = extract_snippet(raw, b"utf-8", b"7BIT", max_chars=50)
    assert isinstance(snippet, str)
    assert "Price" in snippet


def test_extract_snippet_unknown_encoding_returns_empty():
    """Unknown transfer encoding should return empty string."""
    assert extract_snippet(b"hello", b"utf-8", b"X-UNKNOWN") == ""


def test_extract_snippet_empty_bytes_returns_empty():
    """Empty raw bytes should return empty string."""
    assert extract_snippet(b"", b"utf-8", b"7BIT") == ""


def test_strip_html_tags_removes_style_and_script_content():
    """_strip_html_tags should drop style/script content and tags."""
    html = "<style>.hidden{display:none}</style><script>hack()</script><p>Hello &amp; welcome</p>"
    text = _strip_html_tags(html)
    assert ".hidden" not in text
    assert "hack()" not in text
    assert "Hello & welcome" in text
