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
CLEANUP_PIDS=()
TEST_FILES=()
CONTEXT_IDS=()

cleanup() {
    for pid in "${CLEANUP_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
    for f in "${TEST_FILES[@]}"; do
        rm -f "$f"
    done
    # close test tabs
    for ctx in "${CONTEXT_IDS[@]}"; do
        /usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"context\":\"$ctx\",\"expr\":\"window.close()\"}" >/dev/null 2>&1 || true
    done
    "$FIREFOXCTL" stop >/dev/null 2>&1 || true
}
trap cleanup EXIT

pass() { echo "  PASS  $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL  $1 — $2"; FAIL=$((FAIL + 1)); }

check_json_field() {
    local json="$1" field="$2" expected="$3" label="$4"
    local actual
    actual=$(echo "$json" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('$field',''))" 2>/dev/null)
    if [[ "$actual" == "$expected" ]]; then
        pass "$label"
    else
        fail "$label" "expected $field=$expected, got $field=$actual"
    fi
}

# ── Prerequisites ──────────────────────────────────────────────

echo "Checking prerequisites..."

if ! pgrep -x firefox >/dev/null 2>&1; then
    echo "ERROR: Firefox not running."
    echo "Launch with: firefox --remote-debugging-port 9223"
    exit 1
fi

if [[ -S "$SOCK" ]]; then
    echo "ERROR: Daemon already running on $SOCK — stop it first."
    exit 1
fi

echo "Prerequisites OK."
echo ""

# ── Start daemon ───────────────────────────────────────────────

echo "Starting daemon..."

"$FIREFOXCTL" --port 9223 start &
DAEMON_PID=$!
CLEANUP_PIDS+=("$DAEMON_PID")

echo "Waiting for daemon to come up..."
CONNECTED="False"
for i in $(seq 1 30); do
    if [[ -S "$SOCK" ]]; then
        RESULT=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"status"}' 2>/dev/null || echo '{}')
        CONNECTED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('connected',False))" 2>/dev/null)
        if [[ "$CONNECTED" == "True" ]]; then
            break
        fi
    fi
    sleep 1
done

if [[ "$CONNECTED" != "True" ]]; then
    echo "ERROR: Daemon did not connect within 30 seconds."
    exit 1
fi

echo "Daemon connected."
echo ""

# ── Tests ──────────────────────────────────────────────────────

echo "Running integration tests..."
echo ""

# -- status --
echo "[status]"
STATUS=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"status"}')
check_json_field "$STATUS" "connected" "True" "connected is true"
echo ""

# -- list --
echo "[list]"
LIST=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"list"}')
COUNT=$(echo "$LIST" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read()).get('contexts',[])))")
if [[ "$COUNT" -gt 0 ]]; then
    pass "list returns $COUNT contexts"
else
    fail "list" "returned 0 contexts"
fi
echo ""

# -- open --
echo "[open]"
OPEN_RESULT=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"open","url":"data:text/html,<h1>integration test</h1><p id=\"val\">42</p>"}')
CTX=$(echo "$OPEN_RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('context',''))")
if [[ -n "$CTX" ]]; then
    pass "open returned context ID"
    CONTEXT_IDS+=("$CTX")
else
    fail "open" "no context ID returned"
    echo "Cannot continue without a context. Aborting."
    exit 1
fi
echo ""

sleep 0.5

# -- eval --
echo "[eval]"
EVAL1=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"context\":\"$CTX\",\"expr\":\"document.querySelector('h1').innerText\"}")
check_json_field "$EVAL1" "result" "integration test" "eval h1 text"

EVAL2=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"context\":\"$CTX\",\"expr\":\"document.querySelector('#val').innerText\"}")
check_json_field "$EVAL2" "result" "42" "eval paragraph text"

EVAL3=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"context\":\"$CTX\",\"expr\":\"({a: 1, b: 'two'})\"}")
STRUCT=$(echo "$EVAL3" | python3 -c "import sys,json; v=json.loads(sys.stdin.read()).get('result',{}); print(v.get('a',''),v.get('b',''))")
if [[ "$STRUCT" == "1 two" ]]; then
    pass "eval structured return"
else
    fail "eval structured return" "got: $STRUCT"
fi

EVAL4=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"context\":\"$CTX\",\"expr\":\"await Promise.resolve('async-ok')\"}")
check_json_field "$EVAL4" "result" "async-ok" "eval top-level await"
echo ""

# -- navigate --
echo "[navigate]"
NAV=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"navigate\",\"context\":\"$CTX\",\"url\":\"https://example.com\"}")
sleep 1
TITLE=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"context\":\"$CTX\",\"expr\":\"document.title\"}")
check_json_field "$TITLE" "result" "Example Domain" "navigate then eval title"
echo ""

# -- screenshot --
echo "[screenshot]"
SHOT_FILE="/tmp/firefoxctl-inttest-$$.png"
TEST_FILES+=("$SHOT_FILE")
SHOT=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"screenshot\",\"context\":\"$CTX\",\"output\":\"$SHOT_FILE\"}")
if [[ -f "$SHOT_FILE" ]] && file "$SHOT_FILE" | grep -q "PNG image"; then
    SIZE=$(stat -f%z "$SHOT_FILE")
    pass "screenshot saved (${SIZE} bytes, PNG)"
else
    fail "screenshot" "file missing or not PNG"
fi
echo ""

# -- console-tail --
echo "[console-tail]"
(
    sleep 1
    /usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"context\":\"$CTX\",\"expr\":\"console.log('int-log'); console.warn('int-warn'); console.error('int-err'); 'done'\"}" >/dev/null
) &
INJECT_PID=$!
CLEANUP_PIDS+=("$INJECT_PID")

TAIL=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"console-tail\",\"context\":\"$CTX\",\"for\":3}")
wait "$INJECT_PID" 2>/dev/null || true

MSG_COUNT=$(echo "$TAIL" | python3 -c "import sys,json; msgs=json.loads(sys.stdin.read()).get('messages',[]); print(len(msgs))")
if [[ "$MSG_COUNT" -ge 3 ]]; then
    pass "console-tail captured $MSG_COUNT messages"
else
    fail "console-tail" "expected >=3 messages, got $MSG_COUNT"
fi

HAS_LOG=$(echo "$TAIL" | python3 -c "import sys,json; msgs=json.loads(sys.stdin.read()).get('messages',[]); print(any('int-log' in str(m) for m in msgs))")
if [[ "$HAS_LOG" == "True" ]]; then
    pass "console-tail captured log message"
else
    fail "console-tail log" "int-log not found"
fi
echo ""

# -- targets --
echo "[targets]"
TARGETS=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"targets"}')
T_COUNT=$(echo "$TARGETS" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read()).get('targets',[])))")
if [[ "$T_COUNT" -gt 0 ]]; then
    pass "targets returns $T_COUNT targets"
else
    fail "targets" "returned 0 targets"
fi
echo ""

# -- bidi --
echo "[bidi]"
BIDI=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"bidi","method":"session.status"}')
READY=$(echo "$BIDI" | python3 -c "import sys,json; r=json.loads(sys.stdin.read()).get('result',{}); print(r.get('ready',''))")
if [[ "$READY" == "True" ]] || [[ "$READY" == "False" ]]; then
    pass "bidi session.status → ready=$READY"
else
    fail "bidi" "unexpected ready: $READY"
fi
echo ""

# -- helpers (socket) --
echo "[helpers]"
GETTEXT=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"get-text\",\"context\":\"$CTX\",\"selector\":\"h1\"}")
check_json_field "$GETTEXT" "result" "Example Domain" "get-text h1"

EXISTS=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"exists\",\"context\":\"$CTX\",\"selector\":\"h1\"}")
check_json_field "$EXISTS" "result" "True" "exists h1"

EXISTS_NO=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"exists\",\"context\":\"$CTX\",\"selector\":\".nonexistent\"}")
check_json_field "$EXISTS_NO" "result" "False" "exists nonexistent"

CNT=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"count\",\"context\":\"$CTX\",\"selector\":\"*\"}")
CNT_VAL=$(echo "$CNT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('result',0))")
if [[ "$CNT_VAL" -gt 0 ]]; then
    pass "count returns $CNT_VAL elements"
else
    fail "count" "expected >0, got $CNT_VAL"
fi
echo ""

# -- CLI (quick check) --
echo "[cli]"
CLI_EVAL=$("$FIREFOXCTL" --json "$CTX" eval "1+1" 2>&1)
check_json_field "$CLI_EVAL" "result" "2" "cli eval"

CLI_GETTEXT=$("$FIREFOXCTL" --json "$CTX" get-text "h1" 2>&1)
check_json_field "$CLI_GETTEXT" "result" "Example Domain" "cli get-text"

CLI_LIST=$("$FIREFOXCTL" --json list 2>&1)
CTX_COUNT=$(echo "$CLI_LIST" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read()).get('contexts',[])))")
if [[ "$CTX_COUNT" -gt 0 ]]; then
    pass "cli --json list returns $CTX_COUNT contexts"
else
    fail "cli --json list" "expected >0 contexts, got $CTX_COUNT"
fi
echo ""

# -- stop --
echo "[stop]"
"$FIREFOXCTL" stop >/dev/null 2>&1
CLEANUP_PIDS=()
sleep 0.5
if [[ ! -S "$SOCK" ]]; then
    pass "stop removed socket"
else
    fail "stop" "socket still exists"
fi
if ! kill -0 "$DAEMON_PID" 2>/dev/null; then
    pass "stop terminated daemon process"
else
    fail "stop" "daemon process still running"
fi
echo ""

# ── Summary ────────────────────────────────────────────────────

TOTAL=$((PASS + FAIL))
echo "─────────────────────────────"
echo "$PASS/$TOTAL passed"
if [[ "$FAIL" -gt 0 ]]; then
    echo "$FAIL FAILED"
    exit 1
else
    echo "All tests passed."
fi
