#!/usr/bin/env bash
#
# Integration tests for firefoxctl against a real Firefox instance.
#
# Prerequisites:
#   1. Firefox running with: firefox --remote-debugging-port 9223
#   2. No firefoxctl daemon already running

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIREFOXCTL="$SCRIPT_DIR/../../firefox-control/firefoxctl.py"
SOCK="/tmp/firefoxctl-$(id -u).sock"
PASS=0
FAIL=0
TEST_FILES=()

cleanup() {
    "$FIREFOXCTL" stop 2>/dev/null || true
    for f in "${TEST_FILES[@]}"; do
        rm -f "$f"
    done
}
trap cleanup EXIT

pass() { echo "  PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1 — $2"; FAIL=$((FAIL + 1)); }

echo "=== firefoxctl integration tests ==="
echo ""

# --- Direct mode (no daemon) ---

echo "-- Direct mode --"

OUT=$("$FIREFOXCTL" --port 9223 list 2>&1) || { fail "direct list" "exit $?"; }
if echo "$OUT" | grep -q 'context'; then
    pass "direct list"
else
    fail "direct list" "no context in output"
fi

# --- Daemon mode ---

echo "-- Daemon mode --"

"$FIREFOXCTL" --port 9223 start &
DAEMON_PID=$!
sleep 2

if [ -S "$SOCK" ]; then
    pass "daemon start (socket exists)"
else
    fail "daemon start" "socket not found at $SOCK"
fi

# list
OUT=$("$FIREFOXCTL" list 2>&1) || { fail "daemon list" "exit $?"; }
if echo "$OUT" | grep -q 'context'; then
    pass "daemon list"
else
    fail "daemon list" "no context in output"
fi

# Get first context ID
CTX=$(echo "$OUT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())[0]['context'])" 2>/dev/null) || {
    fail "parse context" "could not extract context ID"
    echo ""; echo "=== $PASS passed, $FAIL failed ==="; exit 1
}

# navigate
OUT=$("$FIREFOXCTL" "$CTX" navigate https://example.com 2>&1) || { fail "navigate" "exit $?"; }
pass "navigate"
sleep 1

# eval
OUT=$("$FIREFOXCTL" "$CTX" eval "document.title" 2>&1) || { fail "eval" "exit $?"; }
if echo "$OUT" | grep -q 'Example Domain'; then
    pass "eval document.title"
else
    fail "eval document.title" "got: $OUT"
fi

# DOM helpers
OUT=$("$FIREFOXCTL" "$CTX" exists h1 2>&1) || { fail "exists" "exit $?"; }
if echo "$OUT" | grep -qi 'true'; then
    pass "exists h1"
else
    fail "exists h1" "got: $OUT"
fi

OUT=$("$FIREFOXCTL" "$CTX" get-text h1 2>&1) || { fail "get-text" "exit $?"; }
if echo "$OUT" | grep -q 'Example Domain'; then
    pass "get-text h1"
else
    fail "get-text h1" "got: $OUT"
fi

OUT=$("$FIREFOXCTL" "$CTX" count p 2>&1) || { fail "count" "exit $?"; }
if echo "$OUT" | grep -qE '[0-9]+'; then
    pass "count p"
else
    fail "count p" "got: $OUT"
fi

# screenshot
SHOT=$(mktemp /tmp/firefoxctl-test-XXXXXX.png)
TEST_FILES+=("$SHOT")
OUT=$("$FIREFOXCTL" "$CTX" screenshot -o "$SHOT" 2>&1) || { fail "screenshot" "exit $?"; }
if [ -s "$SHOT" ]; then
    pass "screenshot"
else
    fail "screenshot" "file empty or missing"
fi

# stop
"$FIREFOXCTL" stop 2>&1 || { fail "stop" "exit $?"; }
sleep 1
if [ ! -S "$SOCK" ]; then
    pass "daemon stop (socket removed)"
else
    fail "daemon stop" "socket still exists"
fi

echo ""
echo "=== $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
