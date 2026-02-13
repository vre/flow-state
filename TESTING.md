# Testing Guide

## Test Structure

Tests are organized in `tests/` directory by project type.

### Skills

```
tests/youtube-to-markdown/
├── test_assembler.py (40 tests)
├── test_channel_listing.py (33 tests)
├── test_check_existing.py (12 tests)
├── test_comment_extractor.py (32 tests)
├── test_comment_filter.py (19 tests)
├── test_content_safety.py (25 tests)
├── test_file_ops.py (9 tests)
├── test_paragraph_breaker.py (20 tests)
├── test_prepare_update.py (33 tests)
├── test_shared_types.py (17 tests)
├── test_transcript_extractor.py (10 tests)
├── test_update_metadata.py (7 tests)
├── test_vtt_deduplicator.py (10 tests)
└── test_youtube_extractor.py (9 tests)
```

### MCP Servers

```
tests/imap-stream-mcp/
├── test_imap_client.py (53 tests: IMAP operations, credentials, folders)
├── test_imap_stream_mcp.py (5 tests: MCP server, action routing)
├── test_markdown_utils.py (25 tests: markdown to HTML conversion)
└── test_markdown.py (27 tests: draft formatting)
```

## Running Tests

```bash
# Run all tests
cd tests && uv run pytest

# Run specific project tests
cd tests && uv run pytest youtube-to-markdown/
cd tests && uv run pytest imap-stream-mcp/

# Common options
uv run pytest -v              # Verbose
uv run pytest -x              # Stop on first failure
uv run pytest -k "pattern"    # Run tests matching pattern
```

## Design Principles

**No External Dependencies**
- All file system, subprocess, and network operations are mocked
- Tests run offline in <100ms
- Deterministic, no flaky tests

**Stateless Fixtures**
- Each test gets clean state via pytest fixtures
- Tests can run in any order or in parallel
- Mock implementations in 'conftest.py'

**Comprehensive Coverage**
- Pure function tests (no I/O)
- Integration tests (mocked I/O)
- Edge cases: empty inputs, invalid data, missing fields
- Error paths: exceptions, command failures, cleanup
- Happy paths: complete workflows, various formats
