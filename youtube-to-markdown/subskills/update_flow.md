# Update Flow

Existing extraction found. Analyze and offer update options.

## Step U1: Analyze

```bash
python3 ./scripts/21_prepare_update.py "<YOUTUBE_URL>" "<output_directory>"
```

If `video_available: false`: Inform user "Video no longer available on YouTube", STOP.

## Step U2: Show status

Show component status based on JSON output:

| Component | Status | Version | Issues |
|-----------|--------|---------|--------|
| Summary | exists/missing | v1/v2 | from issues[] |
| Transcript | exists/missing | - | from issues[] |
| Comments | exists/missing | v1/v2 | from issues[] |

If stored_metadata and current_metadata differ, show comparison:

| Metric | Stored | Current |
|--------|--------|---------|
| Views | {stored_metadata.views} | {current_metadata.views} |
| Likes | {stored_metadata.likes} | {current_metadata.likes} |
| Comments | {stored_metadata.comments} | {current_metadata.comments} |

Omit rows where values are identical. Omit tables/columns when not relevant.

Show recommendation:
> **Recommendation:** {reason}

## Step U3: Ask user

AskUserQuestion:
- question: "How do you want to proceed?"
- header: "Update"
- multiSelect: false
- options (show only applicable):
  - "Re-extract comments" (if existing_files.comments exists)
  - "Re-extract transcript" (if existing_files.transcript exists)
  - "Update metadata only" (if action=metadata_only)
  - "Add comments" (if existing_files.comments missing, existing_files.summary exists)
  - "Full refresh" (always)
  - "Keep existing" (always)

## Step U4: Execute

**If "Re-extract comments":**
```bash
python3 ./scripts/40_backup.py backup "<existing_files.comments>"
```
Run: comment_extract.md → comment_summarize.md
```bash
python3 ./scripts/50_assemble.py --comments-only "${BASE_NAME}" "<output_directory>"
```
DONE

**If "Re-extract transcript":**
```bash
python3 ./scripts/40_backup.py backup "<existing_files.transcript>"
```
Run: transcript_extract.md → transcript_polish.md
```bash
python3 ./scripts/50_assemble.py --transcript-only "${BASE_NAME}" "<output_directory>"
```
DONE

**If "Update metadata only":**
```bash
python3 ./scripts/41_update_metadata.py "<existing_files.summary>" "<output_directory>/${BASE_NAME}_metadata.md"
```
DONE

**If "Add comments":**
Run: comment_extract.md → comment_summarize.md
```bash
python3 ./scripts/50_assemble.py --comments-only "${BASE_NAME}" "<output_directory>"
```
DONE

**If "Full refresh":**
Backup each existing file (skip if null):
```bash
python3 ./scripts/40_backup.py backup "<existing_files.summary>"
python3 ./scripts/40_backup.py backup "<existing_files.transcript>"
python3 ./scripts/40_backup.py backup "<existing_files.comments>"
```
Return to main SKILL.md Step 1.

**If "Keep existing":** DONE.
