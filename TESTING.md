# Testing Guide

## Test Structure

Tests are organized in `tests/` directory by project type.

### Skills

```
tests/youtube-to-markdown/
├── test_apply_paragraph_breaks.py (20 tests)
├── test_deduplicate_vtt.py (10 tests)
├── test_extract_comments.py (31 tests)
├── test_extract_data.py (7 tests)
├── test_extract_transcript.py (10 tests)
├── test_file_ops.py (9 tests)
├── test_finalize.py (32 tests)
├── test_prefilter_comments.py (18 tests)
└── test_shared_types.py (17 tests)
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
- Mock implementations in `conftest.py`

**Comprehensive Coverage**
- Pure function tests (no I/O)
- Integration tests (mocked I/O)
- Edge cases: empty inputs, invalid data, missing fields
- Error paths: exceptions, command failures, cleanup
- Happy paths: complete workflows, various formats
