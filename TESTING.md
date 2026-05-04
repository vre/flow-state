# Testing Guide

## Test Structure

Tests are organized in `tests/` directory by project type.

### Skills

```
tests/youtube-to-markdown/
├── test_assembler.py
├── test_channel_listing.py
├── test_check_existing.py
├── test_check_view_growth.py
├── test_checkbox_parsing.py
├── test_comment_extractor.py
├── test_comment_filter.py
├── test_comment_filter_tiers.py
├── test_concat_cleaned_script.py
├── test_content_safety.py
├── test_file_ops.py
├── test_heatmap.py
├── test_insert_headings_from_json_script.py
├── test_list_channel_script.py
├── test_merge_tier2.py
├── test_paragraph_breaker.py
├── test_paragraph_breaker_regression.py
├── test_paragraph_break_planner.py
├── test_parse_channel_entry.py
├── test_prepare_update.py
├── test_run_dispatcher.py
├── test_shared_types.py
├── test_split_for_cleaning_script.py
├── test_transcript_extractor.py
├── test_update_metadata.py
├── test_vtt_deduplicator.py
├── test_watch_guide.py
└── test_youtube_extractor.py
```

### MCP Servers

```
tests/imap-stream-mcp/
├── test_account_param.py
├── test_bodystructure.py
├── test_flag_parsing.py
├── test_imap_client.py
├── test_imap_stream_mcp.py
├── test_markdown_utils.py
├── test_markdown.py
├── test_search_flags.py
└── test_session.py
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

## Release Validation (youtube-to-markdown v2.10.0)

```bash
# From plugin directory
cd youtube-to-markdown
uv run pytest -q
uv run ruff check lib scripts tests

# Optional manual smoke test (network required)
uv run python3 ./scripts/22_list_channel.py "https://www.youtube.com/channel/UCPjNBjflYl0-HQtUvOx0Ibw" /tmp/channel-test --limit 50

# Prompt-only optimization checks (interactive)
# - Run extraction option A and verify subagent TaskOutput stays one-line per step
# - Run 3+ sequential extractions and verify no compaction event in historian
# - Run update flow: Re-extract transcript on existing extraction

# Summary format routing checks (interactive)
# - Run INTERVIEW video: verify Concept Card output (claim headings, core+bullets+implication)
# - Run TIPS video: verify flat-bullets output
# - Run EDUCATIONAL video: verify what-why-how output
# - Verify Step 1 reports [TYPE] in status message
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
