# Test Harness for youtube-to-markdown

Reusable test harness for measuring token usage of different skill versions.

## Quick Start

```bash
# Test a skill variant
./run-test.sh <test-name> <skill-directory> [youtube-url] [option]

# Examples
./run-test.sh 07-new-version ../code/new-version
./run-test.sh 07-new-version ../code/new-version "https://www.youtube.com/watch?v=xyz" B
```

## Options

| Option | Description |
|--------|-------------|
| A | Summary only |
| B | Transcript only |
| C | Comments only |
| D | Summary + Comments |
| E | Full (default) |

## What the Script Does

1. Creates `runs/<test-name>/` from template
2. Links your skill directory to `.claude/skills/youtube-to-markdown`
3. Initializes trace and metrics logging
4. Runs `claude -p` with telemetry enabled
5. Outputs cost summary

## Directory Structure

```
harness/
├── run-test.sh         # Main test runner
├── template/           # Template copied for each test
│   ├── .claude/
│   │   └── skills/        # Skill symlink goes here
│   └── CLAUDE.md          # Test instructions
└── README.md
```

Note: `settings.json` is generated dynamically with absolute paths to ensure hooks work correctly with parallel subagents.

## Metrics Captured

- **agent_trace.log**: Tool call timestamps (PRE_TOOL, POST_TOOL, SESSION_END)
- **otel_metrics.log**: Full OpenTelemetry metrics including cost data
- **output/**: Generated markdown files

## Adding a New Skill Variant

1. Create skill directory in `code/<variant-name>/`
2. Add SKILL.md and any modules/scripts
3. Run test: `./run-test.sh <variant-name> ../code/<variant-name>`
4. Update README.md with results

## Cost Extraction

Final costs appear at end of otel_metrics.log:

```bash
tail -500 runs/<test>/otel_metrics.log | grep -A 30 "claude_code.cost.usage" | grep "value:" | tail -2
```

Output shows Sonnet and Haiku costs separately. Sum for total.
