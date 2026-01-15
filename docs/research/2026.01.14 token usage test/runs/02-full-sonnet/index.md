# Test Run: 02-full-sequential-sonnet

**Date:** 2025-01-14
**Video:** The Assassin's Teapot Is Weird (jJL0XoNBaac)
**URL:** https://www.youtube.com/watch?v=jJL0XoNBaac

## Setup

| Parameter | Value |
|-----------|-------|
| Skill mode | Full (7 subagents)* |
| Orchestrator model | **sonnet** |
| Subagent models | sonnet, haiku (per SKILL.md) |
| Execution mode | Sequential |

*Intended to test SKILL_lite.md but agent selected full skill instead.

## Command

```bash
claude --model sonnet -p "Käytä youtube-to-markdown-lite skilliä (SKILL_lite.md): extract https://www.youtube.com/watch?v=jJL0XoNBaac --debug --output /Users/vre/work/flow-state/token-test -- AJA STEPIT YKSI KERRALLAAN, EI RINNAKKAIN"
```

## Purpose

Test whether Sonnet orchestrator produces same quality as Opus at lower cost.

## Results

| Metric | Value |
|--------|-------|
| Total duration | 477s |
| Total cost | **$1.11** |
| Subagents cost | $0.58 |
| Orchestration cost | $0.53 |
| Cache savings | $4.42 |

## Comparison with 01-full-sequential-opus

| Metric | Opus (01) | Sonnet (02) | Δ |
|--------|-----------|-------------|---|
| Total cost | $3.77 | $1.11 | **-70%** |
| Orchestration | $2.68 | $0.53 | -80% |
| Subagents | $1.09 | $0.58 | -47% |
| Duration | 521s | 477s | -8% |
| Quality | ✓✓✓ | ✓✓✓ | **same** |

## Quality Analysis

### Summary comparison
Both versions produced:
- Clear TL;DR
- Well-structured mechanism explanation (What/Why/How)
- Comprehensive comment insights with @user attributions
- Organized sections (Corrections, Applications, etc.)

### Transcript comparison
- Opus: 98 lines
- Sonnet: 96 lines
- Difference: negligible

## Key Finding

**Opus is unnecessary for orchestration.** The orchestration tasks:
- Following SKILL.md instructions
- Running bash scripts
- Dispatching subagents with prompts
- Updating TodoWrite

...require no Opus-level reasoning. Sonnet handles them equally well.

## Recommendation

Use `--model sonnet` for this skill. Add to SKILL.md:
```
NOTE: Works well with --model sonnet. Opus provides no quality benefit.
```

## Files

- `analysis.txt` - Full token analysis
- `agent_trace.log` - Hook trace
- `otel_metrics.log` - Token metrics
- `youtube_jJL0XoNBaac_*` - Intermediate work files
- `youtube - *.md` - Final output files
