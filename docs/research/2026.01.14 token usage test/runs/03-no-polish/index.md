# Test Run: 03-no-polish-sequential-sonnet

**Date:** 2026-01-17
**Video:** The Assassin's Teapot Is Weird (jJL0XoNBaac)
**Status:** COMPLETE

## Setup

| Parameter | Value |
|-----------|-------|
| Skill variant | No-polish (removes Steps 4, 7, 8) |
| Orchestrator model | Sonnet |
| Subagent models | Sonnet |
| Execution mode | Sequential |

## Results

| Metric | Value |
|--------|-------|
| Total duration | 225s |
| Total cost | **$0.60** |
| Subagents cost | $0.29 |
| Orchestration cost | $0.31 |
| Cache savings | $2.39 |

## Token Breakdown

| Step | Duration | Cost |
|------|----------|------|
| Step 5: Summarize | 29.4s | $0.12 |
| Step 6: Tighten | 15.7s | $0.05 |
| Step 10b: Analyze comments | 40.2s | $0.12 |

## Key Finding

**Same cost as lite version ($0.60)** despite different configurations:
- 03-no-polish: 3 subagents (separate summarize + tighten)
- 05-lite: 2 subagents (combined summarize + tighten)

This proves **polish steps are the main cost driver**, not step separation.

## Comparison

| Test | Polish | Combined | Cost | Savings |
|------|--------|----------|------|---------|
| 02-full-sonnet | ✓ | ✗ | $1.11 | baseline |
| 04-combined | ✓ | ✓ | $0.89 | -20% |
| **03-no-polish** | **✗** | **✗** | **$0.60** | **-46%** |
| 05-lite | ✗ | ✓ | $0.60 | -46% |

**Polish removal = $0.51 savings (46%)**
