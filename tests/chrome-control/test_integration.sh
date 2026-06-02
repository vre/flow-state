#!/usr/bin/env bash
#
# Integration tests for chromectl against a real Chrome instance.
#
# Prerequisites:
#   1. Chrome running with remote debugging enabled:
#      chrome://inspect/#remote-debugging → toggle ON
#   2. No chromectl daemon already running
#
# On first connect, Chrome shows a permission dialog — click "Allow"
# when prompted. The script waits for you to do this.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHROMECTL="$SCRIPT_DIR/../../chrome-control/chromectl.py"
SOCK="/tmp/chromectl-$(id -u).sock"
PASS=0
FAIL=0
CLEANUP_PIDS=()
TEST_FILES=()
TARGET_IDS=()

cleanup() {
    for pid in "${CLEANUP_PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    done
    for f in "${TEST_FILES[@]}"; do
        rm -f "$f"
    done
    # close test tabs
    for id in "${TARGET_IDS[@]}"; do
        /usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"id\":\"$id\",\"expr\":\"window.close()\"}" >/dev/null 2>&1 || true
    done
    "$CHROMECTL" stop >/dev/null 2>&1 || true
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

DEVTOOLS_PORT_FILE="$HOME/Library/Application Support/Google/Chrome/DevToolsActivePort"
if [[ ! -f "$DEVTOOLS_PORT_FILE" ]]; then
    echo "ERROR: DevToolsActivePort not found."
    echo "Enable remote debugging: chrome://inspect/#remote-debugging → toggle ON"
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
echo ">>> Chrome will show a permission dialog — click Allow <<<"
echo ""

"$CHROMECTL" start &
DAEMON_PID=$!
CLEANUP_PIDS+=("$DAEMON_PID")

echo "Waiting for daemon to come up (accept the Chrome dialog)..."
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
check_json_field "$STATUS" "mode" "auto-connect" "mode is auto-connect"
echo ""

# -- list --
echo "[list]"
LIST=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"list"}')
COUNT=$(echo "$LIST" | python3 -c "import sys,json; print(len(json.loads(sys.stdin.read()).get('targets',[])))")
if [[ "$COUNT" -gt 0 ]]; then
    pass "list returns $COUNT targets"
else
    fail "list" "returned 0 targets"
fi
echo ""

# -- open --
echo "[open]"
OPEN_RESULT=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"open","url":"data:text/html,<h1>integration test</h1><p id=\"val\">42</p>"}')
TARGET=$(echo "$OPEN_RESULT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('id',''))")
if [[ -n "$TARGET" ]]; then
    pass "open returned target ID"
    TARGET_IDS+=("$TARGET")
else
    fail "open" "no target ID returned"
    echo "Cannot continue without a target. Aborting."
    exit 1
fi
echo ""

sleep 0.5

# -- eval --
echo "[eval]"
EVAL1=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"id\":\"$TARGET\",\"expr\":\"document.querySelector('h1').innerText\"}")
check_json_field "$EVAL1" "value" "integration test" "eval h1 text"

EVAL2=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"id\":\"$TARGET\",\"expr\":\"document.querySelector('#val').innerText\"}")
check_json_field "$EVAL2" "value" "42" "eval paragraph text"

EVAL3=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"id\":\"$TARGET\",\"expr\":\"({a: 1, b: 'two'})\"}")
STRUCT=$(echo "$EVAL3" | python3 -c "import sys,json; v=json.loads(sys.stdin.read()).get('value',{}); print(v.get('a',''),v.get('b',''))")
if [[ "$STRUCT" == "1 two" ]]; then
    pass "eval structured return"
else
    fail "eval structured return" "got: $STRUCT"
fi

EVAL4=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"id\":\"$TARGET\",\"expr\":\"await Promise.resolve('async-ok')\"}")
check_json_field "$EVAL4" "value" "async-ok" "eval top-level await"
echo ""

# -- navigate --
echo "[navigate]"
/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"id\":\"$TARGET\",\"expr\":\"void 0\"}" >/dev/null
NAV=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"navigate\",\"id\":\"$TARGET\",\"url\":\"https://example.com\"}")
sleep 1
NAV_TITLE=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"id\":\"$TARGET\",\"expr\":\"document.title\"}")
check_json_field "$NAV_TITLE" "value" "Example Domain" "navigate then eval title"
echo ""

# -- screenshot --
echo "[screenshot]"
SHOT_FILE="/tmp/chromectl-inttest-$$.png"
TEST_FILES+=("$SHOT_FILE")
SHOT=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"screenshot\",\"id\":\"$TARGET\",\"output\":\"$SHOT_FILE\"}")
if [[ -f "$SHOT_FILE" ]] && file "$SHOT_FILE" | grep -q "PNG image"; then
    SIZE=$(stat -f%z "$SHOT_FILE")
    pass "screenshot saved (${SIZE} bytes, PNG)"
else
    fail "screenshot" "file missing or not PNG"
fi

SHOT_FULL="/tmp/chromectl-inttest-full-$$.png"
TEST_FILES+=("$SHOT_FULL")
SHOT2=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"screenshot\",\"id\":\"$TARGET\",\"output\":\"$SHOT_FULL\",\"full_page\":true}")
if [[ -f "$SHOT_FULL" ]] && file "$SHOT_FULL" | grep -q "PNG image"; then
    pass "screenshot full-page saved"
else
    fail "screenshot full-page" "file missing or not PNG"
fi
echo ""

# -- console-tail --
echo "[console-tail]"
# inject console messages after a short delay
(
    sleep 1
    /usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"eval\",\"id\":\"$TARGET\",\"expr\":\"console.log('int-log'); console.warn('int-warn'); console.error('int-err'); 'done'\"}" >/dev/null
) &
INJECT_PID=$!
CLEANUP_PIDS+=("$INJECT_PID")

TAIL=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"console-tail\",\"id\":\"$TARGET\",\"seconds\":3}")
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
T_TYPES=$(echo "$TARGETS" | python3 -c "import sys,json; print(len(set(t['type'] for t in json.loads(sys.stdin.read()).get('targets',[]))))")
if [[ "$T_COUNT" -gt "$COUNT" ]] || [[ "$T_TYPES" -gt 1 ]]; then
    pass "targets returns $T_COUNT targets across $T_TYPES types (more than list's $COUNT)"
else
    fail "targets" "expected more targets/types than list"
fi
echo ""

# -- cdp --
echo "[cdp]"
CDP=$(/usr/bin/nc -U "$SOCK" <<< '{"cmd":"cdp","method":"Browser.getVersion"}')
PRODUCT=$(echo "$CDP" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('result',{}).get('product',''))")
if [[ "$PRODUCT" == Chrome/* ]]; then
    pass "cdp Browser.getVersion → $PRODUCT"
else
    fail "cdp" "unexpected product: $PRODUCT"
fi
echo ""

# -- worker-eval (best-effort) --
echo "[worker-eval]"
WORKER_ID=$(echo "$TARGETS" | python3 -c "
import sys,json
targets = json.loads(sys.stdin.read()).get('targets',[])
workers = [t for t in targets if t['type'] == 'service_worker']
print(workers[0]['id'] if workers else '')
")
if [[ -n "$WORKER_ID" ]]; then
    WEVAL=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"worker-eval\",\"id\":\"$WORKER_ID\",\"expr\":\"typeof self\"}" 2>&1 || echo '{"error":"connection dropped"}')
    if echo "$WEVAL" | python3 -c "import sys,json; v=json.loads(sys.stdin.read()); sys.exit(0 if 'value' in v else 1)" 2>/dev/null; then
        pass "worker-eval returned value"
    else
        echo "  SKIP  worker-eval — connection may have dropped (known Chrome bug)"
    fi
else
    echo "  SKIP  worker-eval — no service workers found"
fi
echo ""

# -- helpers (socket) --
echo "[helpers]"
GETTEXT=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"get-text\",\"id\":\"$TARGET\",\"selector\":\"h1\"}")
check_json_field "$GETTEXT" "value" "integration test" "get-text h1"

GETVAL=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"get-text\",\"id\":\"$TARGET\",\"selector\":\"#val\"}")
check_json_field "$GETVAL" "value" "42" "get-text #val"

EXISTS=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"exists\",\"id\":\"$TARGET\",\"selector\":\"h1\"}")
check_json_field "$EXISTS" "value" "True" "exists h1"

EXISTS_NO=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"exists\",\"id\":\"$TARGET\",\"selector\":\".nonexistent\"}")
check_json_field "$EXISTS_NO" "value" "False" "exists nonexistent"

CNT=$(/usr/bin/nc -U "$SOCK" <<< "{\"cmd\":\"count\",\"id\":\"$TARGET\",\"selector\":\"*\"}")
CNT_VAL=$(echo "$CNT" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('value',0))")
if [[ "$CNT_VAL" -gt 0 ]]; then
    pass "count returns $CNT_VAL elements"
else
    fail "count" "expected >0, got $CNT_VAL"
fi
echo ""

# -- CLI (quick check) --
echo "[cli]"
CLI_EVAL=$("$CHROMECTL" --json "$TARGET" eval "1+1" 2>&1)
check_json_field "$CLI_EVAL" "value" "2" "cli eval"

CLI_GETTEXT=$("$CHROMECTL" --json "$TARGET" get-text "h1" 2>&1)
check_json_field "$CLI_GETTEXT" "value" "integration test" "cli get-text"
echo ""

# -- stop --
echo "[stop]"
"$CHROMECTL" stop >/dev/null 2>&1
CLEANUP_PIDS=()  # daemon already stopped
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
