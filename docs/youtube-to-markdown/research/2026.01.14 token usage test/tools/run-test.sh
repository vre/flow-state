#!/bin/bash
# Token usage test for youtube-to-markdown skill
#
# Usage: ./run-test.sh [OPTIONS] [YOUTUBE_URL]
#
# Options:
#   --model MODEL     Orchestrator model: opus, sonnet, haiku (default: opus)
#   --parallel        Allow parallel subagent execution (default: sequential)
#   --name NAME       Run name for results directory (default: auto-generated)
#   --no-comments     Skip comment analysis
#
# NOTE: Run from flow-state directory, not token-test:
#   cd /Users/vre/work/flow-state && token-test/run-test.sh [OPTIONS]

set -e

# Default test case
DEFAULT_URL="https://www.youtube.com/watch?v=jJL0XoNBaac"
DEFAULT_MODEL="opus"
PARALLEL=false
RUN_NAME=""
SKIP_COMMENTS=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --model)
            DEFAULT_MODEL="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --name)
            RUN_NAME="$2"
            shift 2
            ;;
        --no-comments)
            SKIP_COMMENTS=true
            shift
            ;;
        -h|--help)
            head -15 "$0" | tail -13
            exit 0
            ;;
        http*)
            DEFAULT_URL="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

YOUTUBE_URL="$DEFAULT_URL"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Generate run name if not provided
if [ -z "$RUN_NAME" ]; then
    EXEC_MODE=$([ "$PARALLEL" = true ] && echo "parallel" || echo "sequential")
    RUN_NAME="${EXEC_MODE}-${DEFAULT_MODEL}"
fi

OUTPUT_DIR="$SCRIPT_DIR/runs/$RUN_NAME"
LOG_FILE="$SCRIPT_DIR/agent_trace.log"
OTEL_LOG="$SCRIPT_DIR/otel_metrics.log"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Clean previous logs
rm -f "$LOG_FILE" "$OTEL_LOG"

echo "=== Token Usage Test ==="
echo "URL: $YOUTUBE_URL"
echo "Model: $DEFAULT_MODEL"
echo "Parallel: $PARALLEL"
echo "Output: $OUTPUT_DIR"
echo ""

# Build prompt
PROMPT="extract $YOUTUBE_URL --debug --output $SCRIPT_DIR"
if [ "$PARALLEL" = false ]; then
    PROMPT="$PROMPT -- AJA STEPIT YKSI KERRALLAAN, EI RINNAKKAIN"
fi
if [ "$SKIP_COMMENTS" = true ]; then
    PROMPT="$PROMPT, ÄLÄ AJA KOMMENTTIANALYYSIÄ"
fi

# Run claude with OTel enabled
CLAUDE_CODE_ENABLE_TELEMETRY=1 \
OTEL_METRICS_EXPORTER=console \
OTEL_METRIC_EXPORT_INTERVAL=5000 \
claude --model "$DEFAULT_MODEL" -p "$PROMPT" 2>&1 | tee "$OTEL_LOG"

echo ""
echo "=== Moving results to $OUTPUT_DIR ==="

# Move logs
mv "$LOG_FILE" "$OUTPUT_DIR/" 2>/dev/null || true
mv "$OTEL_LOG" "$OUTPUT_DIR/" 2>/dev/null || true

# Move output files
find "$SCRIPT_DIR" -maxdepth 1 -name "youtube_*" -exec mv {} "$OUTPUT_DIR/" \;
find "$SCRIPT_DIR" -maxdepth 1 -name "youtube - *" -exec mv {} "$OUTPUT_DIR/" \;

echo ""
echo "=== Analysis ==="
if [ -f "$OUTPUT_DIR/agent_trace.log" ] && [ -f "$OUTPUT_DIR/otel_metrics.log" ]; then
    python3 "$SCRIPT_DIR/analyze_steps.py" "$OUTPUT_DIR/agent_trace.log" "$OUTPUT_DIR/otel_metrics.log" | tee "$OUTPUT_DIR/analysis.txt"
fi

# Generate index.md
cat > "$OUTPUT_DIR/index.md" << EOF
# Test Run: $RUN_NAME

**Date:** $(date +%Y-%m-%d)
**Video:** jJL0XoNBaac
**URL:** $YOUTUBE_URL

## Setup

| Parameter | Value |
|-----------|-------|
| Orchestrator model | $DEFAULT_MODEL |
| Execution mode | $([ "$PARALLEL" = true ] && echo "Parallel" || echo "Sequential") |
| Skip comments | $SKIP_COMMENTS |

## Command

\`\`\`bash
claude --model $DEFAULT_MODEL -p "$PROMPT"
\`\`\`

## Results

See \`analysis.txt\` for full breakdown.
EOF

echo ""
echo "=== Done ==="
echo "Results saved to: $OUTPUT_DIR"
