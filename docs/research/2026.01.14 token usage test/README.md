# Token Usage Optimization Research

**Date:** 2026-01-14 to 2026-01-18
**Subject:** youtube-to-markdown skill cost optimization

## Summary

Systematic testing of token usage across different skill configurations to find optimal cost/quality tradeoffs.

### Key Findings

| Test | Cost | Savings | Configuration |
|------|------|---------|---------------|
| 01-full-opus | $3.77 | baseline | Opus orchestrator, all steps |
| 02-full-sonnet | $1.11 | -70% | Sonnet orchestrator |
| 03-no-polish | $0.60 | -46% | Remove polish steps |
| 04-combined | $0.89 | -20% | Combine workflow steps |
| **05-lite** | **$0.52** | **-53%** | Both optimizations |

### Validated Hypotheses

1. **Sonnet is sufficient as orchestrator** - 70% cost reduction, same quality
2. **Polish steps unnecessary for AI consumption** - 46% savings
3. **Step combining provides additional savings** - Additive with polish removal

## Directory Structure

```
.
├── code/                    # Skill variants
│   ├── full/SKILL.md       # 7 subagents - baseline
│   ├── no-polish/SKILL.md  # 3 subagents - no steps 4,7,8
│   ├── combined/SKILL.md   # 5 subagents - merged workflows
│   └── lite/SKILL.md       # 2 subagents - both optimizations
├── tools/
│   ├── analyze_steps.py    # Token analysis from OTel metrics
│   └── run-test.sh         # Test runner script
└── runs/                    # Test results (not committed)
    ├── 01-full-opus/
    ├── 02-full-sonnet/
    ├── 03-no-polish/
    ├── 04-combined/
    └── 05-lite/
```

## Skill Variants

### Full (7 subagents) - `code/full/`
All steps including transcript polish:
- Step 4: Paragraph breaks
- Step 5: Summarize
- Step 6: Tighten summary
- Step 7: Clean speech artifacts
- Step 8: Add topic headings
- Step 10a: Extract comments
- Step 10b: Analyze comments

### No-Polish (3 subagents) - `code/no-polish/`
Removes transcript refinement steps (4, 7, 8):
- Step 5: Summarize
- Step 6: Tighten summary
- Step 10b: Analyze comments

### Combined (5 subagents) - `code/combined/`
Merges multi-step workflows:
- Step 4: Paragraph breaks
- Step 5: Summarize + tighten (combined)
- Step 7: Clean artifacts
- Step 8: Add headings
- Step 10: Comments (combined)

### Lite (2 subagents) - `code/lite/`
Both optimizations - minimum cost:
- Step 5: Summarize + tighten (combined)
- Step 10: Comments (combined)

## Cost Analysis

### Isolated Variable Effects

| Optimization | Savings | Evidence |
|--------------|---------|----------|
| Opus → Sonnet | -$2.66 (-70%) | 02 vs 01 |
| Remove polish | -$0.51 (-46%) | 03 vs 02 |
| Combine steps | -$0.22 (-20%) | 04 vs 02 |
| **Both** | **-$0.59 (-53%)** | **05 vs 02** |

### Cost Breakdown (Lite variant)

```
Step 5:  Summarize (combined)    $0.11  ████░░░░░░░░  21%
Step 10: Comments (combined)     $0.17  ██████░░░░░░  33%
Orchestration                    $0.24  █████████░░░  46%
```

## Recommendations

| Use Case | Variant | Cost |
|----------|---------|------|
| AI consumption (RAG) | lite | $0.52 |
| Balanced | no-polish | $0.60 |
| Human-readable | combined | $0.89 |
| Maximum quality | full | $1.11 |

## Running Tests

```bash
# From repo root
cd docs/research/2026.01.14\ token\ usage\ test/

# Copy desired variant to plugin
cp code/lite/SKILL.md ~/.claude/plugins/cache/flow-state/youtube-to-markdown/2.1.1/

# Run test
./tools/run-test.sh --model sonnet --name test-name

# Analyze results
python3 tools/analyze_steps.py runs/test-name/agent_trace.log runs/test-name/otel_metrics.log
```

## Hook Configuration (for reference)

The tests used Claude Code hooks to capture timing data. Add to `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "echo \"SESSION_START $(date +%s.%N)\" >> /path/to/agent_trace.log"
      }]
    }],
    "PreToolUse": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 /path/to/log_tool.py PRE_TOOL"
      }]
    }],
    "PostToolUse": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 /path/to/log_tool.py POST_TOOL"
      }]
    }],
    "SubagentStop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "echo \"SUBAGENT_END $(date +%s.%N)\" >> /path/to/agent_trace.log"
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "echo \"SESSION_END $(date +%s.%N)\" >> /path/to/agent_trace.log"
      }]
    }]
  }
}
```

The `log_tool.py` script logs tool invocations with timestamps to `agent_trace.log`.

## Raw Data

| Metric | 01-opus | 02-sonnet | 03-no-polish | 04-combined | 05-lite |
|--------|---------|-----------|--------------|-------------|---------|
| Cost | $3.77 | $1.11 | $0.60 | $0.89 | $0.52 |
| Duration | 521s | 477s | 225s | 380s | 237s |
| Subagents | 7 | 7 | 3 | 5 | 2 |
