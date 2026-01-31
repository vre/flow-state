#!/usr/bin/env python3
import json
import sys
from datetime import datetime

event_type = sys.argv[1] if len(sys.argv) > 1 else "UNKNOWN"
log_file = "/Users/vre/work/flow-state/token-test/agent_trace.log"

try:
    data = json.load(sys.stdin)
    tool_name = data.get("tool_name", "?")
except:
    tool_name = "?"

timestamp = datetime.now().timestamp()

with open(log_file, "a") as f:
    f.write(f"{event_type} {timestamp:.6f} {tool_name}\n")
