# YouTube Skills Modularization Plan

## Goal

Merge youtube-to-markdown and youtube-comment-analysis into a single modular plugin. Iterative approach - small steps, test after each.

## Why

- Enable future user choice of output combinations (summary-only, transcript-only, etc.)
- Enable parallel execution of independent modules
- Reduce main SKILL.md size for better maintainability
- Consolidate related functionality into single plugin

## Module Loading Mechanism

Uses existing pattern from UPDATE_MODE.md (line 29 of current SKILL.md):
```
Read and follow ./modules/transcript_extract.md
```

Orchestrator reads module file with Read tool, then follows its instructions.

## Rollback

Git reset to previous commit if any phase fails validation.

## Phases Overview

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Refactor youtube-to-markdown into modules | Pending |
| 2 | Refactor youtube-comment-analysis into modules | Pending |
| 3 | Move comment modules + scripts to youtube-to-markdown | Pending |
| 4 | Cleanup: delete empty skill, update docs | Pending |
| 5 | Add user choices and parallel execution | Future |

---

## Phase 1: Refactor youtube-to-markdown into modules

### Goal
Split current SKILL.md into modules. Same functionality, just reorganized.

### Target Structure
```
youtube-to-markdown/
├── SKILL.md                         # Orchestrator (loads modules)
├── modules/
│   ├── transcript_extract.md        # Steps 1-3: metadata, transcript, deduplicate
│   ├── transcript_summarize.md      # Steps 4-5: summarize, tighten
│   └── transcript_polish.md         # Steps 6-8: paragraphs, clean, headings
├── *.py                             # Scripts (no changes)
└── finalize.py                      # No changes yet
```

### Module Contents

**transcript_extract.md**: Current Steps 1-3
- Step 1: Extract data (metadata, description, chapters)
- Step 2: Extract transcript
- Step 3: Deduplicate transcript

**transcript_summarize.md**: Current Steps 4-5
- Step 4: Summarize transcript
- Step 5: Review and tighten summary

**transcript_polish.md**: Current Steps 6-8
- Step 6: Add paragraph breaks
- Step 7: Clean speech artifacts
- Step 8: Add topic headings

### SKILL.md Changes

Becomes orchestrator:
- Step 0: Check existing (keep as-is)
- Load and execute transcript_extract.md
- Load and execute transcript_summarize.md
- Load and execute transcript_polish.md
- Step 9: Finalize (keep as-is)
- Step 10: Comment analysis (keep reference to separate skill for now)

### Files to Modify

| File | Action |
|------|--------|
| `youtube-to-markdown/SKILL.md` | Refactor to orchestrator |
| `youtube-to-markdown/modules/transcript_extract.md` | New: Steps 1-3 |
| `youtube-to-markdown/modules/transcript_summarize.md` | New: Steps 4-5 |
| `youtube-to-markdown/modules/transcript_polish.md` | New: Steps 6-8 |

### Verification

```bash
# Modules exist
ls youtube-to-markdown/modules/

# Run existing tests (scripts unchanged, tests should pass)
cd tests && uv run pytest youtube-to-markdown/ -v

# Manual test with real YouTube video
# Run skill, verify output matches expected format
```

---

## Phase 2: Refactor youtube-comment-analysis into modules

### Goal
Split youtube-comment-analysis SKILL.md into modules.

### Target Structure
```
youtube-comment-analysis/
├── SKILL.md                         # Orchestrator
├── modules/
│   ├── comment_extract.md           # Steps 1-2: extract, prefilter
│   └── comment_summarize.md         # Steps 3-4: insights, tighten
└── *.py                             # Scripts
```

### Verification

```bash
# Modules exist
ls youtube-comment-analysis/modules/

# Run existing tests
cd tests && uv run pytest youtube-comment-analysis/ -v

# Manual test with real YouTube video
```

---

## Phase 3: Move comment modules to youtube-to-markdown

### Goal
Integrate comment functionality into main skill.

### Actions
1. Move `comment_extract.md` and `comment_summarize.md` to youtube-to-markdown/modules/
2. Move comment scripts (`extract_comments.py`, `prefilter_comments.py`, `finalize_comments.py`) to youtube-to-markdown/
3. Update SKILL.md to include comment modules
4. Update script paths in modules

### Verification

```bash
# All modules in youtube-to-markdown
ls youtube-to-markdown/modules/

# All tests pass (both sets now in one location or referencing new paths)
cd tests && uv run pytest youtube-to-markdown/ -v
cd tests && uv run pytest youtube-comment-analysis/ -v

# Manual test: full pipeline with comments from single skill
```

---

## Phase 4: Cleanup

### Actions
1. Delete empty `youtube-comment-analysis/` folder
2. Update `.claude-plugin/marketplace.json` - remove comment-analysis entry
3. Update README.md

### Verification
```bash
test ! -d youtube-comment-analysis && echo "OK"
cat .claude-plugin/marketplace.json | jq '.plugins | length'  # should be 2
```

---

## Phase 5: User choices and parallel execution (Future)

Add after Phase 4 is complete and stable:
- User choice prompt (5 options)
- Mermaid dependency graphs
- Parallel module execution
