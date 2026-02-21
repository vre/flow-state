# DONE: Summary Integrity Validation

## Problem

`check_existing.py` only identifies v1 vs v2 format (`detect_v1_summary`), but does NOT detect:
1. Empty summary (only `## Summary` heading without content)
2. Missing required elements (TL;DR, metadata fields)
3. Failed processing (interrupted, crashed)

Consequence: User sees "v2.0 - Up to date" even though the file is broken.

## Solution

Add `validate_summary_integrity()` function that checks if file was successfully processed.

### Elements to Validate

**Summary file** (`youtube - {title} ({VIDEO_ID}).md`):
```
REQUIRED:
- ## Video section
  - **Title:** (not empty)
  - **Engagement:** (views, likes, comments)
  - **Published:** and Extracted:
- ## Summary section
  - **TL;DR**: (at least 20 characters)
  - Content after heading (at least 100 characters)

OPTIONAL:
- **Tags:**
- ## Hidden Gems
```

**Transcript file** (`youtube - {title} - transcript ({VIDEO_ID}).md`):
```
REQUIRED:
- ## Description section (can be empty)
- ## Transcription section (at least 500 characters)
```

**Comments file** (`youtube - {title} - comments ({VIDEO_ID}).md`):
```
REQUIRED:
- ## Comment Insights section (at least 100 characters)
```

### Return Value

`check_existing()` returns expanded:
```python
{
    "video_id": "xxx",
    "exists": true,
    "summary_file": "/path/to/file.md",
    "comment_file": null,
    "transcript_file": "/path/to/transcript.md",

    # Existing
    "summary_v1": false,
    "comments_v1": null,
    "stored_metadata": {...},

    # NEW
    "summary_valid": true,      # All required elements OK
    "summary_issues": [],       # List of missing/broken items
    "transcript_valid": true,
    "transcript_issues": [],
    "comments_valid": null,     # null if file doesn't exist
    "comments_issues": null
}
```

## Implementation

### Phase 1: Add validation functions to `check_existing.py`

```python
def validate_summary_integrity(content: str) -> tuple[bool, list[str]]:
    """
    Validate that summary file has all required elements.
    Returns (is_valid, list_of_issues).
    """
    issues = []

    # Check ## Video section
    if "## Video" not in content:
        issues.append("missing_video_section")
    else:
        if "**Title:**" not in content or re.search(r'\*\*Title:\*\*\s*\n', content):
            issues.append("empty_title")
        if "**Engagement:**" not in content:
            issues.append("missing_engagement")
        if "**Published:**" not in content:
            issues.append("missing_published")

    # Check ## Summary section
    summary_match = re.search(r'## Summary\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
    if not summary_match:
        issues.append("missing_summary_section")
    else:
        summary_text = summary_match.group(1).strip()
        if len(summary_text) < 100:
            issues.append("summary_too_short")
        if "**TL;DR**" not in summary_text:
            issues.append("missing_tldr")

    return (len(issues) == 0, issues)


def validate_transcript_integrity(content: str) -> tuple[bool, list[str]]:
    """Validate transcript file has required elements."""
    issues = []

    if "## Transcription" not in content:
        issues.append("missing_transcription_section")
    else:
        trans_match = re.search(r'## Transcription\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if trans_match and len(trans_match.group(1).strip()) < 500:
            issues.append("transcription_too_short")

    return (len(issues) == 0, issues)


def validate_comments_integrity(content: str) -> tuple[bool, list[str]]:
    """Validate comments file has required elements."""
    issues = []

    if "## Comment Insights" not in content:
        issues.append("missing_insights_section")
    else:
        insights_match = re.search(r'## Comment Insights\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if insights_match and len(insights_match.group(1).strip()) < 100:
            issues.append("insights_too_short")

    return (len(issues) == 0, issues)
```

### Phase 2: Extend `check_existing()` function

Add validation calls after lines 155-165:

```python
# Validate summary integrity
if files["summary_file"]:
    content = Path(files["summary_file"]).read_text()
    result["summary_v1"] = detect_v1_summary(content)
    result["stored_metadata"] = extract_metadata_from_file(content)
    # NEW: Integrity check
    valid, issues = validate_summary_integrity(content)
    result["summary_valid"] = valid
    result["summary_issues"] = issues

# Validate transcript integrity
if files["transcript_file"]:
    content = Path(files["transcript_file"]).read_text()
    valid, issues = validate_transcript_integrity(content)
    result["transcript_valid"] = valid
    result["transcript_issues"] = issues

# Validate comments integrity
if files["comment_file"]:
    content = Path(files["comment_file"]).read_text()
    result["comments_v1"] = detect_v1_comments(content)
    # NEW: Integrity check
    valid, issues = validate_comments_integrity(content)
    result["comments_valid"] = valid
    result["comments_issues"] = issues
```

### Phase 3: Update SKILL.md to use new fields

Add logic after Step 0:
```markdown
If `summary_valid: false`:
- Show issues list to user
- Suggest: "File is incomplete. Do you want to reprocess?"
```

## Files

| File | Change |
|------|--------|
| `check_existing.py` | +3 validation functions, extended check_existing() |
| `SKILL.md` | Updated logic to handle summary_valid/issues |

## Testing

```bash
# Test with empty summary
python3 check_existing.py "https://www.youtube.com/watch?v=Udc19q1o6Mg" "/Users/vre/Sync/Obsidian/Joplinpoplin"

# Expected result:
{
  "video_id": "Udc19q1o6Mg",
  "exists": true,
  "summary_valid": false,
  "summary_issues": ["summary_too_short", "missing_tldr"],
  ...
}
```
