# Permission Prompts Fix

**Goal:** Eliminate permission prompts by making commands match `Bash(python3:*)` pattern.

**Root cause:** Scripts import `shared_types` → Claude adds `cd` → compound command → blocked.

**Test location:** `tests/youtube-to-markdown/` (not inside package)

---

## Task 1: Test infrastructure ✓
Already exists at `tests/youtube-to-markdown/conftest.py`

## Task 2: Timestamp stripping in deduplicate_vtt.py
- Add `sys.path.insert(0, str(Path(__file__).parent))` for imports
- Add optional third param `no_timestamps_path` to strip `[HH:MM:SS.mmm] ` prefix
- Update CLI to accept third arg
- Add test in `tests/youtube-to-markdown/test_deduplicate_vtt.py`

## Task 3: Fix imports in 6 scripts
Add sys.path fix to: check_existing.py, extract_data.py, extract_transcript.py, extract_transcript_whisper.py, apply_paragraph_breaks.py, finalize.py

## Task 4: Create file_ops.py
Commands: `backup <file>`, `cleanup <output_dir> <video_id>`
- backup: copy to `{file}_backup_{YYYYMMDD}.md`
- cleanup: remove intermediate files (patterns from finalize.py)
- Add test in `tests/youtube-to-markdown/test_file_ops.py`

## Task 5: Update SKILL.md
Step 3: Replace `cut -c 16-` with third param to deduplicate_vtt.py

## Task 6: Update UPDATE_MODE.md
Replace `mv`/`rm` with `file_ops.py backup`/`cleanup`

## Task 7: Verify
Run tests, verify scripts work from /tmp without ImportError
