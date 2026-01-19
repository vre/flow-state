# Plan: Eliminate Permission Prompts from Skills

## Problem
Skills trigger permission prompts because Claude generates compound commands like:
```bash
cd /path && python3 script.py && cut -c 16- ...
```

Even though `Bash(python3:*)` is allowed, the `&&` operator blocks auto-approval (Claude Code is shell-operator aware).

## Root Cause
Scripts import `shared_types` from same directory → Claude adds `cd` to make imports work → compound command → permission prompt.

## Solution: Two Phases

### Phase 1: Minimal Fix (now)

**Goal:** Make all commands simple `python3 /path/script.py args` that match existing `Bash(python3:*)` rule.

#### 1.1 Fix imports in all scripts
Add to each script before other imports:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

**Files:**
- youtube-to-markdown/check_existing.py
- youtube-to-markdown/extract_data.py
- youtube-to-markdown/extract_transcript.py
- youtube-to-markdown/extract_transcript_whisper.py
- youtube-to-markdown/deduplicate_vtt.py
- youtube-to-markdown/apply_paragraph_breaks.py
- youtube-to-markdown/finalize.py

#### 1.2 Move `cut` into deduplicate_vtt.py
Add optional third parameter:
```bash
python3 deduplicate_vtt.py <input.vtt> <output_dedup.md> [<output_no_timestamps.txt>]
```

**File:** youtube-to-markdown/deduplicate_vtt.py

#### 1.3 Create file_ops.py for backup/cleanup
```bash
python3 file_ops.py backup <file>                    # mv to {file}_backup_{date}.md
python3 file_ops.py cleanup <output_dir> <video_id> # rm intermediate files
```

**File:** youtube-to-markdown/file_ops.py (new)

#### 1.4 Update skill docs
- SKILL.md: Use absolute paths, add third param to deduplicate call
- UPDATE_MODE.md: Replace `mv`/`rm` with file_ops.py calls

**Files:**
- youtube-to-markdown/SKILL.md
- youtube-to-markdown/UPDATE_MODE.md

### Phase 2: Orchestrator (future)

Single entry point with subcommands for ultimate simplicity:
```bash
python3 orchestrator.py extract <url> <output_dir> [lang]
python3 orchestrator.py finalize <video_id> <output_dir>
```

Benefits: One permission prompt, modularity, testability, future flexibility (parallel, skip steps).

## Validation

After Phase 1:
1. Run skill on test video
2. Verify no permission prompts for Python script calls
3. Only prompts should be for non-python operations (if any remain)

## References
- [Claude Code IAM Docs](https://code.claude.com/docs/en/iam) - permission pattern matching
- Compound commands with `&&` are blocked even if first command matches pattern
