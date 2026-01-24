#!/bin/bash
# Run a token usage test for youtube-to-markdown skill
#
# Usage: ./run-test.sh <test-name> <skill-directory> [youtube-url] [option]
#
# Arguments:
#   test-name       Name for this test run (creates runs/<test-name>/ directory)
#   skill-directory Path to skill directory containing SKILL.md
#   youtube-url     YouTube video URL (default: https://www.youtube.com/watch?v=jJL0XoNBaac)
#   option          Skill option A-E (default: E for Full)
#
# Example:
#   ./run-test.sh 07-new-version ../code/new-version
#   ./run-test.sh 07-new-version ../code/new-version "https://www.youtube.com/watch?v=xyz" B

set -e

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <test-name> <skill-directory> [youtube-url] [option]"
    echo ""
    echo "Arguments:"
    echo "  test-name       Name for this test run"
    echo "  skill-directory Path to skill directory containing SKILL.md"
    echo "  youtube-url     YouTube video URL (default: Assassin's Teapot video)"
    echo "  option          Skill option A-E (default: E)"
    exit 1
fi

TEST_NAME="$1"
SKILL_DIR="$2"
YOUTUBE_URL="${3:-https://www.youtube.com/watch?v=jJL0XoNBaac}"
OPTION="${4:-E}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNS_DIR="$(dirname "$SCRIPT_DIR")/runs"
RUN_DIR="$RUNS_DIR/$TEST_NAME"

# Validate skill directory
if [ ! -f "$SKILL_DIR/SKILL.md" ]; then
    echo "Error: SKILL.md not found in $SKILL_DIR"
    exit 1
fi

# Create run directory from template
echo "=== Setting up test: $TEST_NAME ==="
rm -rf "$RUN_DIR"
cp -r "$SCRIPT_DIR/template" "$RUN_DIR"
mkdir -p "$RUN_DIR/output"

# Link skill directory
SKILL_ABS="$(cd "$SKILL_DIR" && pwd)"
ln -sf "$SKILL_ABS" "$RUN_DIR/.claude/skills/youtube-to-markdown"

# Generate settings.json with absolute path to trace log (quoted for spaces)
TRACE_LOG="$RUN_DIR/agent_trace.log"
cat > "$RUN_DIR/.claude/settings.json" << EOF
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "echo \"PRE_TOOL \$(date +%s.%N) \$CLAUDE_TOOL_NAME\" >> \"$TRACE_LOG\""
      }]
    }],
    "PostToolUse": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "echo \"POST_TOOL \$(date +%s.%N) \$CLAUDE_TOOL_NAME\" >> \"$TRACE_LOG\""
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "echo \"SESSION_END \$(date +%s.%N)\" >> \"$TRACE_LOG\""
      }]
    }]
  },
  "permissions": {
    "allow": [
      "Bash(python3:*)",
      "Bash(yt-dlp:*)"
    ]
  }
}
EOF

echo "Skill linked: $SKILL_ABS"
echo "Run directory: $RUN_DIR"
echo "YouTube URL: $YOUTUBE_URL"
echo "Option: $OPTION ($(case $OPTION in A) echo "Summary only";; B) echo "Transcript only";; C) echo "Comments only";; D) echo "Summary + Comments";; E) echo "Full";; esac))"
echo ""

# Initialize trace log
cd "$RUN_DIR"
echo "SESSION_START $(date +%s.%N)" > agent_trace.log

# Run test
echo "=== Running test ==="
CLAUDE_CODE_ENABLE_TELEMETRY=1 \
OTEL_METRICS_EXPORTER=console \
OTEL_METRIC_EXPORT_INTERVAL=5000 \
claude --model sonnet -p "extract $YOUTUBE_URL to ./output/, use option $OPTION" 2>&1 | tee otel_metrics.log

echo ""
echo "=== Test Complete ==="
echo "Trace log: $RUN_DIR/agent_trace.log"
echo "OTel log: $RUN_DIR/otel_metrics.log"
echo "Output: $RUN_DIR/output/"
echo ""

# Extract cost summary
echo "=== Cost Summary ==="
tail -500 otel_metrics.log | grep -A 30 "claude_code.cost.usage" | grep "value:" | tail -2 || echo "Cost data not found in metrics"
