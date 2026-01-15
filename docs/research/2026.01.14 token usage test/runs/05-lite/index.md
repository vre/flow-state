# Test Run: 05-lite-sequential-sonnet

**Date:** 2026-01-18
**Video:** The Assassin's Teapot Is Weird (jJL0XoNBaac)
**Status:** COMPLETE

## Setup

| Parameter | Value |
|-----------|-------|
| Skill variant | Lite (no polish + combined steps) |
| Orchestrator model | Sonnet |
| Subagent models | Sonnet |
| Execution mode | Sequential |

## Results

| Metric | Value |
|--------|-------|
| Total duration | 237s |
| Total cost | **$0.52** |
| Subagents cost | $0.28 |
| Orchestration cost | $0.24 |
| Cache savings | $1.96 |

## Token Breakdown

| Step | Duration | Cost |
|------|----------|------|
| Step 5: Summarize (combined) | 27.9s | $0.11 |
| Step 10: Comments (combined) | 60.6s | $0.17 |

## Key Finding

**Lowest cost achieved: $0.52** (-53% vs full-sonnet)

Savings are additive:
- Polish removal: $1.11 → $0.60 = -$0.51
- Step combining: $0.60 → $0.52 = -$0.08
- Total: -$0.59

## Comparison

| Test | Polish | Combined | Cost | Savings |
|------|--------|----------|------|---------|
| 02-full-sonnet | ✓ | ✗ | $1.11 | baseline |
| 03-no-polish | ✗ | ✗ | $0.60 | -46% |
| 04-combined | ✓ | ✓ | $0.89 | -20% |
| **05-lite** | **✗** | **✓** | **$0.52** | **-53%** |

## Output Quality

- Summary: Complete with all sections
- Transcript: Deduplicated (no polish formatting)
- Comments: ✓ Analyzed and appended
