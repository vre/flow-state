# Update Flow

Existing extraction found. Analyze and offer update options.

## Step U1: Analyze

```bash
python3 ./prepare_update.py "<YOUTUBE_URL>" "<output_directory>"
```

If `video_available: false`: Inform user "Video no longer available on YouTube", STOP.

## Step U2: Show status

Show status table based on JSON output:

| Component | Status | Version | Issues |
|-----------|--------|---------|--------|
| Summary | exists/missing | v1/v2 | from issues[] |
| Transcript | exists/missing | - | from issues[] |
| Comments | exists/missing | v1/v2 | from issues[] |

If metadata_changes show significant differences, mention them.

Show recommendation:
> **Recommendation:** {recommendation.reason}
> Suggested: {recommendation.suggested_output or "no action needed"}

Adapt table and wording to what's relevant - omit empty columns, simplify if no issues.

## Step U3: Ask user

AskUserQuestion:
- question: "How do you want to proceed?"
- header: "Update"
- multiSelect: false
- options (show only applicable):
  - "Update metadata only" (if `action: metadata_only`)
  - "Accept: [recommendation.reason]" (if action != none/metadata_only)
  - "Choose different output" (always)
  - "Keep existing files" (always)

## Step U4: Execute

**If "Update metadata only":**
```bash
python3 ./update_metadata.py "<summary_path>" "<output_directory>/${BASE_NAME}_metadata.md"
```
DONE - inform user metadata updated.

**If "Accept" or "Choose different":**
```bash
python3 ./file_ops.py backup <file>  # for each file in files_to_backup
```
Return to main SKILL.md Step 1.

**If "Keep existing":** DONE.
