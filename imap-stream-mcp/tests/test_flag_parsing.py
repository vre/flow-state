"""Tests for flag parsing and normalization functions."""

import pytest


# Tests for normalize_flag_output (strip backslash from IMAP flags)
class TestNormalizeFlagOutput:
    """Test flag normalization for output (IMAP -> display)."""

    def test_strips_backslash_from_standard_flags(self):
        from imap_client import normalize_flag_output
        assert normalize_flag_output("\\Seen") == "Seen"
        assert normalize_flag_output("\\Flagged") == "Flagged"
        assert normalize_flag_output("\\Answered") == "Answered"
        assert normalize_flag_output("\\Deleted") == "Deleted"
        assert normalize_flag_output("\\Draft") == "Draft"

    def test_preserves_keywords_without_backslash(self):
        from imap_client import normalize_flag_output
        assert normalize_flag_output("$label1") == "$label1"
        assert normalize_flag_output("important") == "important"
        assert normalize_flag_output("$Forwarded") == "$Forwarded"

    def test_handles_empty_and_none(self):
        from imap_client import normalize_flag_output
        assert normalize_flag_output("") == ""


# Tests for normalize_flag_input (prepare flags for IMAP)
class TestNormalizeFlagInput:
    """Test flag normalization for input (user -> IMAP)."""

    def test_adds_backslash_to_standard_flags(self):
        from imap_client import normalize_flag_input
        assert normalize_flag_input("Seen") == "\\Seen"
        assert normalize_flag_input("Flagged") == "\\Flagged"
        assert normalize_flag_input("Answered") == "\\Answered"
        assert normalize_flag_input("Deleted") == "\\Deleted"
        assert normalize_flag_input("Draft") == "\\Draft"

    def test_case_insensitive_standard_flags(self):
        from imap_client import normalize_flag_input
        assert normalize_flag_input("seen") == "\\Seen"
        assert normalize_flag_input("FLAGGED") == "\\Flagged"
        assert normalize_flag_input("SeEn") == "\\Seen"

    def test_handles_existing_backslash(self):
        from imap_client import normalize_flag_input
        assert normalize_flag_input("\\Seen") == "\\Seen"
        assert normalize_flag_input("\\flagged") == "\\Flagged"

    def test_preserves_keywords(self):
        from imap_client import normalize_flag_input
        assert normalize_flag_input("$label1") == "$label1"
        assert normalize_flag_input("important") == "important"
        assert normalize_flag_input("$Forwarded") == "$Forwarded"


# Tests for parse_flag_payload (MCP payload -> parsed components)
class TestParseFlagPayload:
    """Test flag payload parsing from MCP action."""

    def test_single_message_single_add_flag(self):
        from imap_stream_mcp import parse_flag_payload
        msg_ids, add, remove = parse_flag_payload("123:+Flagged")
        assert msg_ids == [123]
        assert add == ["Flagged"]
        assert remove == []

    def test_single_message_single_remove_flag(self):
        from imap_stream_mcp import parse_flag_payload
        msg_ids, add, remove = parse_flag_payload("123:-Seen")
        assert msg_ids == [123]
        assert add == []
        assert remove == ["Seen"]

    def test_single_message_multiple_flags(self):
        from imap_stream_mcp import parse_flag_payload
        msg_ids, add, remove = parse_flag_payload("123:+Flagged,-Seen")
        assert msg_ids == [123]
        assert add == ["Flagged"]
        assert remove == ["Seen"]

    def test_batch_messages_single_flag(self):
        from imap_stream_mcp import parse_flag_payload
        msg_ids, add, remove = parse_flag_payload("123,124,125:+Flagged")
        assert msg_ids == [123, 124, 125]
        assert add == ["Flagged"]
        assert remove == []

    def test_batch_messages_multiple_flags(self):
        from imap_stream_mcp import parse_flag_payload
        msg_ids, add, remove = parse_flag_payload("1,2,3:+Flagged,+Answered,-Seen")
        assert msg_ids == [1, 2, 3]
        assert set(add) == {"Flagged", "Answered"}
        assert remove == ["Seen"]

    def test_keyword_flags(self):
        from imap_stream_mcp import parse_flag_payload
        msg_ids, add, remove = parse_flag_payload("123:+$label1,-$label2")
        assert msg_ids == [123]
        assert add == ["$label1"]
        assert remove == ["$label2"]

    def test_whitespace_handling(self):
        from imap_stream_mcp import parse_flag_payload
        msg_ids, add, remove = parse_flag_payload(" 123 : +Flagged , -Seen ")
        assert msg_ids == [123]
        assert add == ["Flagged"]
        assert remove == ["Seen"]

    def test_invalid_format_no_colon(self):
        from imap_stream_mcp import parse_flag_payload
        with pytest.raises(ValueError, match="Invalid.*format"):
            parse_flag_payload("123+Flagged")

    def test_invalid_format_no_flags(self):
        from imap_stream_mcp import parse_flag_payload
        with pytest.raises(ValueError, match="No flags"):
            parse_flag_payload("123:")

    def test_invalid_message_id(self):
        from imap_stream_mcp import parse_flag_payload
        with pytest.raises(ValueError, match="Invalid message ID"):
            parse_flag_payload("abc:+Flagged")

    def test_invalid_flag_no_prefix(self):
        from imap_stream_mcp import parse_flag_payload
        with pytest.raises(ValueError, match="must start with"):
            parse_flag_payload("123:Flagged")
