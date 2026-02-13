# Plan: Add Date Prefix to Final Filenames

**Status:** COMPLETE
**Created:** 2026-02-13

## Intent

Change final output filenames from:
```
youtube - Title (VIDEO_ID).md
youtube - Title - transcript (VIDEO_ID).md
youtube - Title - comments (VIDEO_ID).md
```

To:
```
2026-02-05 - youtube - Title (VIDEO_ID).md
2026-02-05 - youtube - Title - transcript (VIDEO_ID).md
2026-02-05 - youtube - Title - comments (VIDEO_ID).md
```

The date is the video's **upload date** (Published), not the extraction date.

## Goal

Files sort chronologically by upload date in file browsers. This makes the output directory scannable and meaningful.

## Analysis

### Current state

Filename generation in `lib/assembler.py`:
- `get_filenames()` returns `(cleaned_title, video_id)`, reads title from `_title.txt`
- Each `finalize_*` method builds filenames inline — 6 places
- `finalize_comments_only` is an outlier: reads `_name.txt` with own logic instead of `get_filenames()` (anti-DRY)

Upload date is in `{base_name}_metadata.md` as `**Published:** 2026-02-05 | ...` but not as a separate file.

### File discovery

`check_existing.py` `find_existing_files()` glob: `youtube - * ({video_id}).md`

### Update flow

When updating a previously extracted video, `_upload_date.txt` won't exist (intermediate files cleaned up). `prepare_update.py` already parses `stored_metadata.published` from the existing summary file — it can write `_upload_date.txt` so the assembler has it available.

## Constraints

- Upload date "Unknown" → no date prefix
- Backward compatible: `check_existing` must find old files (no prefix) and new files (with prefix)
- Intermediate work files unchanged
- No new API calls — date from existing metadata or summary file

## Tasks

### 1. Unify title file: `_name.txt` → `_title.txt`

**File:** `lib/comment_extractor.py` `extract_and_save()`

Change `{base_name}_name.txt` → `{base_name}_title.txt`. Write only if file doesn't exist (`if not self.filesystem.exists(title_file)`) — avoids overwriting in flows D/E where metadata extraction already created it.

**File:** `lib/intermediate_files.py`

Replace `{base_name}_name.txt` with `{base_name}_title.txt` in `get_comments_work_files()`.

### 2. Save upload date to intermediate file

**File:** `lib/youtube_extractor.py` `create_metadata_file()`

Save formatted `upload_date` (YYYY-MM-DD) to `{base_name}_upload_date.txt` alongside `{base_name}_title.txt`.

**File:** `lib/intermediate_files.py`

Add `{base_name}_upload_date.txt` to `get_summary_work_files()`.

### 3. Write `_upload_date.txt` in update flow

**File:** `lib/prepare_update.py` `prepare_update()`

When `existing["exists"]` is true, write `{base_name}_upload_date.txt` from `stored_metadata["published"]` (already parsed from the existing summary file). Skip if `None` or missing.

This ensures `_upload_date.txt` is available before the assembler runs in update scenarios, without the assembler needing to search for files itself.

### 4. Centralize filename construction

**File:** `lib/assembler.py`

Expand `get_filenames()` to:
- Read `{base_name}_upload_date.txt` (return `None` if missing or "Unknown")
- Return `(cleaned_title, video_id, upload_date)`

Add helper `build_filename(upload_date, cleaned_title, video_id, suffix="")` that returns the full filename string. `suffix` is e.g. `" - transcript"`, `" - comments"`.

Eliminate `finalize_comments_only`'s separate `_name.txt` logic — use `get_filenames()` (works because Task 1 unified to `_title.txt`).

### 5. Update all `finalize_*` methods to use `build_filename()`

**File:** `lib/assembler.py`

Replace inline filename construction in all 6 places with `build_filename()` calls.

Pattern: `{upload_date} - youtube - {title}{suffix} ({video_id}).md`
No date: `youtube - {title}{suffix} ({video_id}).md`

### 6. Update `find_existing_files()` glob pattern

**File:** `lib/check_existing.py`

```python
all_files = list(output_dir.glob(f"*youtube - * ({video_id}).md"))
```

`*` before "youtube" matches both `"2026-02-05 - "` and empty string.

### 7. Update tests

**File:** `tests/youtube-to-markdown/test_assembler.py`
- Add `{base_name}_upload_date.txt` to mock_fs fixtures
- Update filename assertions to include date prefix
- Test missing `_upload_date.txt` → no prefix (backward compat)
- Test `build_filename()` helper directly

**File:** `tests/youtube-to-markdown/test_check_existing.py`
- Test `find_existing_files` finds files with date prefix
- Test `find_existing_files` finds files without date prefix

**File:** `tests/youtube-to-markdown/test_youtube_extractor.py`
- Test `create_metadata_file()` writes `_upload_date.txt`

**File:** `tests/youtube-to-markdown/test_comment_extractor.py`
- Update `_name.txt` references to `_title.txt`

**File:** `tests/youtube-to-markdown/test_prepare_update.py`
- Test that `prepare_update()` writes `_upload_date.txt` when video exists

## Acceptance Criteria

- [x] Final files: `{upload_date} - youtube - {title} ({video_id}).md`
- [x] Missing/Unknown upload_date → current format (no prefix)
- [x] `_name.txt` → `_title.txt` in comment_extractor (DRY)
- [x] `finalize_comments_only` uses `get_filenames()` (DRY fix)
- [x] `build_filename()` centralizes filename construction
- [x] `check_existing` finds both old and new format files
- [x] Update flow: `prepare_update()` writes `_upload_date.txt` from stored_metadata
- [x] All tests pass, new tests for date prefix + backward compat
- [x] `_upload_date.txt` in work file cleanup lists

## Reflection

### Mikä meni hyvin
- TDD per task: jokaisen taskin testit ensin, toteutus perään. 17 uutta testiä.
- DRY-löydökset suunnitteluvaiheessa (\_name.txt / \_title.txt duplikaatio, inline-filenamejen toisto) korjattiin samalla.
- Manuaalitesti oikealla videolla vahvisti toimivuuden.

### Mikä muuttui suunnitelmasta
- Alkuperäinen suunnitelma ei huomioinut \_upload\_date.txt:n puuttumista update-flowssa. Katselmoinnissa löytyi → lisättiin Task 3 (prepare_update kirjoittaa tiedoston).
- `finalize_comments_only`:n oma \_name.txt-logiikka oli alun perin "eri syystä" → käyttäjä osoitti sen olevan anti-DRY → yhtenäistettiin Task 1:ssä.
- Title-tiedoston ylikirjoitusriski flows D/E:ssä → ratkaistiin if-not-exists -guardilla.

### Opitut asiat
- Assembler-tason muutokset vaativat kaikkien finalize\_\*-metodien läpikäyntiä — keskittäminen build\_filename()-helperiin tekee jatkossa muutoksista yhden paikan operaation.
- Suunnitelman katselmointi "tyhjällä mielellä" kolmesti löysi eri ongelmia joka kerralla. Arvokas käytäntö.
