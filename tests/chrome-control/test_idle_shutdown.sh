#!/usr/bin/env bash
#
# Tests for daemon idle auto-shutdown.
# Uses CHROMECTL_IDLE_TIMEOUT=10 (10 seconds) to avoid waiting 5 minutes.
#
# Three cases:
#   1. Daemon up, command fails → should still shut down after idle timeout
#   2. Daemon up, command succeeds → timer resets, shuts down after idle from last command
#   3. Daemon up, no commands ever → shuts down after idle timeout

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHROMECTL="$SCRIPT_DIR/../../chrome-control/chromectl.py"
SOCK="/tmp/chromectl-$(id -u).sock"
TIMEOUT=10
export CHROMECTL_IDLE_TIMEOUT=$TIMEOUT

PASS=0
FAIL=0

pass() { echo "  PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1 — $2"; FAIL=$((FAIL + 1)); }

wait_daemon_dead() {
    local pid=$1 max_wait=$2 elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [[ $elapsed -ge $max_wait ]]; then
            return 1
        fi
    done
    return 0
}

ensure_no_daemon() {
    if [[ -S "$SOCK" ]]; then
        "$CHROMECTL" stop >/dev/null 2>&1 || true
        sleep 1
    fi
}

# ── Case 3: no commands ──────────────────────────────────────

echo "=== Case 3: daemon up, no commands ==="
echo "  Starting daemon with ${TIMEOUT}s idle timeout..."
ensure_no_daemon

"$CHROMECTL" start &
DAEMON_PID=$!
for i in $(seq 1 15); do
    if [[ -S "$SOCK" ]]; then
        RESULT=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"status"}' 2>/dev/null || echo '{}')
        CONNECTED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('connected',False))" 2>/dev/null)
        if [[ "$CONNECTED" == "True" ]]; then break; fi
    fi
    sleep 1
done

if [[ "$CONNECTED" != "True" ]]; then
    echo "ERROR: Daemon did not connect. Skipping."
    kill "$DAEMON_PID" 2>/dev/null || true
    exit 1
fi
# That status command counts as a request, so wait from now
echo "  Daemon up. Waiting ${TIMEOUT}s + margin for auto-shutdown..."

if wait_daemon_dead "$DAEMON_PID" $((TIMEOUT + 10)); then
    if [[ ! -S "$SOCK" ]]; then
        pass "case 3: daemon died and cleaned up socket after idle timeout"
    else
        pass "case 3: daemon died (socket cleanup may lag)"
        rm -f "$SOCK"
    fi
else
    fail "case 3" "daemon still alive after $((TIMEOUT + 10))s"
    kill "$DAEMON_PID" 2>/dev/null || true
    wait "$DAEMON_PID" 2>/dev/null || true
    rm -f "$SOCK"
fi
echo ""

# ── Case 2: command succeeds, then idle ──────────────────────

echo "=== Case 2: command succeeds, then idle ==="
ensure_no_daemon

"$CHROMECTL" start &
DAEMON_PID=$!
for i in $(seq 1 15); do
    if [[ -S "$SOCK" ]]; then
        RESULT=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"status"}' 2>/dev/null || echo '{}')
        CONNECTED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('connected',False))" 2>/dev/null)
        if [[ "$CONNECTED" == "True" ]]; then break; fi
    fi
    sleep 1
done

# Send a successful command halfway through
sleep $((TIMEOUT / 2))
echo "  Sending command at t+$((TIMEOUT / 2))s..."
/usr/bin/nc -U "$SOCK" <<< '{"cmd":"list"}' >/dev/null 2>&1

# Should NOT have died yet (timer reset)
sleep 2
if kill -0 "$DAEMON_PID" 2>/dev/null; then
    pass "case 2: daemon alive after command (timer reset)"
else
    fail "case 2" "daemon died too early after successful command"
    echo ""; ensure_no_daemon
    # skip to next
    echo "=== Case 1: skipped ==="
    echo ""
    TOTAL=$((PASS + FAIL))
    echo "─────────────────────────────"
    echo "$PASS/$TOTAL passed"
    [[ "$FAIL" -gt 0 ]] && exit 1
    exit 0
fi

# Now wait for idle timeout from last command
echo "  Waiting ${TIMEOUT}s + margin for auto-shutdown..."
if wait_daemon_dead "$DAEMON_PID" $((TIMEOUT + 10)); then
    pass "case 2: daemon died after idle timeout from last command"
else
    fail "case 2" "daemon still alive after $((TIMEOUT + 10))s from last command"
    kill "$DAEMON_PID" 2>/dev/null || true
    wait "$DAEMON_PID" 2>/dev/null || true
fi
rm -f "$SOCK"
echo ""

# ── Case 1: command fails, then idle ─────────────────────────

echo "=== Case 1: command fails, then idle ==="
ensure_no_daemon

"$CHROMECTL" start &
DAEMON_PID=$!
for i in $(seq 1 15); do
    if [[ -S "$SOCK" ]]; then
        RESULT=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"status"}' 2>/dev/null || echo '{}')
        CONNECTED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('connected',False))" 2>/dev/null)
        if [[ "$CONNECTED" == "True" ]]; then break; fi
    fi
    sleep 1
done

# Send a failing command (eval with bogus target ID)
echo "  Sending failing command..."
FAIL_RESULT=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"eval","id":"NONEXISTENT_TARGET_00000000000","expr":"1"}' 2>/dev/null || echo '{}')
HAS_ERROR=$(echo "$FAIL_RESULT" | python3 -c "import sys,json; print('error' in json.loads(sys.stdin.read()))" 2>/dev/null)
if [[ "$HAS_ERROR" == "True" ]]; then
    echo "  Command failed as expected: $(echo "$FAIL_RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('error','')[:60])")"
else
    echo "  WARNING: command did not fail as expected"
fi

# Should still shut down after idle timeout
echo "  Waiting ${TIMEOUT}s + margin for auto-shutdown..."
if wait_daemon_dead "$DAEMON_PID" $((TIMEOUT + 10)); then
    pass "case 1: daemon died after idle timeout despite failed command"
else
    fail "case 1" "daemon still alive after $((TIMEOUT + 10))s"
    kill "$DAEMON_PID" 2>/dev/null || true
    wait "$DAEMON_PID" 2>/dev/null || true
fi
rm -f "$SOCK"
echo ""

# ── Summary ───────────────────────────────────────────────────

TOTAL=$((PASS + FAIL))
echo "─────────────────────────────"
echo "$PASS/$TOTAL passed"
if [[ "$FAIL" -gt 0 ]]; then
    echo "$FAIL FAILED"
    exit 1
else
    echo "All tests passed."
fi
