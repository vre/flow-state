# Sequential Opus Test Run

**Date:** 2025-01-14
**Video:** The Assassin's Teapot Is Weird (jJL0XoNBaac)
**URL:** https://www.youtube.com/watch?v=jJL0XoNBaac

## Test Setup

| Parameter | Value |
|-----------|-------|
| Orchestrator model | opus (default) |
| Subagent models | sonnet, haiku (per SKILL.md) |
| Execution mode | Sequential (--non-parallel) |
| Debug mode | Yes (intermediate files preserved) |

## Command

```bash
CLAUDE_CODE_ENABLE_TELEMETRY=1 \
OTEL_METRICS_EXPORTER=console \
OTEL_METRIC_EXPORT_INTERVAL=5000 \
claude -p "extract https://www.youtube.com/watch?v=jJL0XoNBaac --debug --output /Users/vre/work/flow-state/token-test -- AJA STEPIT YKSI KERRALLAAN, EI RINNAKKAIN"
```

## Results Summary

| Metric | Value |
|--------|-------|
| Total duration | 521s |
| Total cost | $3.77 |
| Subagents cost | $1.09 (29%) |
| Orchestration cost | $2.68 (71%) |
| Cache savings | $18.45 |

## Token Breakdown

### By Step (Subagents)

| Step | Duration | Cost |
|------|----------|------|
| Step 4: Paragraph breaks | 22.0s | $0.19 |
| Step 5: Summarize transcript | 23.7s | $0.14 |
| Step 6: Review/tighten summary | 23.5s | $0.13 |
| Step 7: Clean speech artifacts | 33.9s | $0.09 |
| Step 8: Add topic headings | 36.6s | $0.18 |
| Step 10a: Extract comments | 60.2s | $0.22 |
| Step 10b: Analyze comments | 23.7s | $0.15 |

### Orchestration Phases

| Phase | Opus Output | % of Total |
|-------|-------------|------------|
| Before Step 5 | 1,058 | 11% |
| Before Step 6 | 753 | 8% |
| Before Step 7 | 672 | 7% |
| Before Step 8 | 694 | 7% |
| Before comment analysis | 4,317 | **44%** |
| Before Step 10b | 898 | 9% |
| Finalize | 1,442 | 15% |

## Key Findings

1. **Orchestration dominates cost** - 71% of total spend
2. **Largest single cost** - transition to comment analysis (44% of orchestration)
3. **Subagents are efficient** - only $1.09 for all 7 steps
4. **Cache works well** - $18.45 saved (5x the session cost)

## Optimization Recommendations

1. **Use Sonnet for orchestration** - potential savings ~$2.00
2. **Reduce TodoWrite calls** - 18 → 7 (one per step)
3. **Consider separating comment analysis** - runs as separate session

## Files

- `analysis.txt` - Full analysis output
- `agent_trace.log` - Hook trace (tool calls, subagent boundaries)
- `otel_metrics.log` - OpenTelemetry token metrics
- `youtube_jJL0XoNBaac_*` - Intermediate work files
- `youtube - *.md` - Final output files
