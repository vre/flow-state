# Test Run: 04-combined-sequential-sonnet

**Date:** 2026-01-17
**Video:** The Assassin's Teapot Is Weird (jJL0XoNBaac)
**Status:** COMPLETE

## Setup

| Parameter | Value |
|-----------|-------|
| Skill variant | Combined (Steps 5+6 merged, 10a+10b merged) |
| Orchestrator model | Sonnet |
| Subagent models | Sonnet (Haiku for Step 7) |
| Execution mode | Sequential |

## Results

| Metric | Value |
|--------|-------|
| Total duration | 380s |
| Total cost | **$0.89** |
| Subagents cost | $0.57 |
| Orchestration cost | $0.32 |
| Cache savings | $3.33 |

## Token Breakdown

| Step | Duration | Cost |
|------|----------|------|
| Step 4: Paragraph breaks | 23.1s | $0.11 |
| Step 5: Summarize (combined) | 56.8s | $0.14 |
| Step 7: Clean speech | 32.7s | $0.03 |
| Step 8: Add headings | 35.9s | $0.10 |
| Step 10: Comments (combined) | 59.8s | $0.18 |

## Key Finding

**Step combining saves 20%** when polish steps are included.

However, combining provides NO additional savings when polish is removed:
- 03-no-polish (separate): $0.60
- 05-lite (combined): $0.60

## Comparison

| Test | Polish | Combined | Cost | Savings |
|------|--------|----------|------|---------|
| 02-full-sonnet | ✓ | ✗ | $1.11 | baseline |
| **04-combined** | **✓** | **✓** | **$0.89** | **-20%** |
| 03-no-polish | ✗ | ✗ | $0.60 | -46% |
| 05-lite | ✗ | ✓ | $0.60 | -46% |

**Step combining = $0.22 savings (20%) - only with polish steps**
