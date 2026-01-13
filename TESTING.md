# Testing Guide

## Test Structure

Tests are organized in `tests/` directory:

```
tests/
├── youtube-comment-analysis/
│   ├── test_extract_comments.py (31 tests: URL parsing, JSON handling, markdown generation)
│   └── test_finalize_comments.py (29 tests: filename cleaning, templating, finalization)
└── youtube-to-markdown/
    ├── test_apply_paragraph_breaks.py (10 tests)
    ├── test_deduplicate_vtt.py (9 tests)
    ├── test_extract_data.py (7 tests)
    ├── test_extract_transcript.py (10 tests)
    ├── test_file_ops.py (9 tests)
    ├── test_finalize.py (12 tests)
    └── test_shared_types.py (17 tests)
```

## Running Tests

```bash
# Run all youtube-comment-analysis tests
cd tests/youtube-comment-analysis && pytest

# Run all youtube-to-markdown tests
cd tests/youtube-to-markdown && pytest

# Run specific test file
cd tests/youtube-comment-analysis && pytest test_extract_comments.py

# Common options
pytest -v              # Verbose
pytest -q              # Quiet
pytest -x              # Stop on first failure
pytest -k "pattern"    # Run tests matching pattern
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
