#!/usr/bin/env python3
"""
Analyze token usage per step and subagent.
Usage: python3 analyze_steps.py [trace_log] [otel_log]
"""
import sys
import re

# Step definitions for youtube-to-markdown skill variants
# Format: (step_name, model, parallel_with_next)

STEP_DEFINITIONS_FULL = [
    ("Step 4: Paragraph breaks", "sonnet", True),   # parallel with Step 5
    ("Step 5: Summarize transcript", "sonnet", False),
    ("Step 6: Review/tighten summary", "sonnet", False),
    ("Step 7: Clean speech artifacts", "haiku", False),
    ("Step 8: Add topic headings", "sonnet", False),
    ("Step 10a: Extract comments", "sonnet", False),
    ("Step 10b: Analyze comments", "sonnet", False),
]

STEP_DEFINITIONS_NO_POLISH = [
    ("Step 5: Summarize transcript", "sonnet", False),
    ("Step 6: Review/tighten summary", "sonnet", False),
    ("Step 10b: Analyze comments", "sonnet", False),  # 10a is bash only
]

STEP_DEFINITIONS_COMBINED = [
    ("Step 4: Paragraph breaks", "sonnet", False),
    ("Step 5: Summarize (combined)", "sonnet", False),
    ("Step 7: Clean speech", "haiku", False),
    ("Step 8: Add headings", "sonnet", False),
    ("Step 10: Comments (combined)", "sonnet", False),
]

STEP_DEFINITIONS_LITE = [
    ("Step 5: Summarize (combined)", "sonnet", False),
    ("Step 10: Comments (combined)", "sonnet", False),
]

def get_step_definitions(subagent_count: int) -> list:
    """Auto-detect skill variant by subagent count."""
    if subagent_count == 7:
        return STEP_DEFINITIONS_FULL
    elif subagent_count == 5:
        return STEP_DEFINITIONS_COMBINED
    elif subagent_count == 3:
        return STEP_DEFINITIONS_NO_POLISH
    elif subagent_count == 2:
        return STEP_DEFINITIONS_LITE
    else:
        return STEP_DEFINITIONS_FULL  # fallback

def parse_trace(path: str) -> list[dict]:
    """Parse trace into events with timestamps."""
    events = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                event = {"type": parts[0], "ts": float(parts[1])}
                if len(parts) >= 3:
                    event["tool"] = parts[2]
                events.append(event)
    return events

def parse_otel_snapshots(path: str) -> list[dict]:
    """Parse OTel into time-ordered snapshots with token deltas."""
    with open(path) as f:
        content = f.read()

    snapshots = []
    blocks = re.split(r'\n\{[\s\n]+descriptor:', content)

    for block in blocks[1:]:
        block = "descriptor:" + block
        if 'name: "claude_code.token.usage"' not in block:
            continue

        # Extract end_time and token values
        ends = re.findall(r'endTime: \[\s*(\d+),\s*(\d+)\s*\]', block)
        if not ends:
            continue
        end_time = int(ends[-1][0]) + int(ends[-1][1]) / 1e9

        models = re.findall(r'model: "([^"]+)"', block)
        types = re.findall(r'type: "(input|output|cacheRead|cacheCreation)"', block)
        values = re.findall(r'^\s*value: ([\d.]+)', block, re.MULTILINE)

        data = {}
        for model, tok_type, value in zip(models, types, values):
            short = model.split("-")[1] if "-" in model else model
            key = f"{short}_{tok_type}"
            data[key] = int(float(value))

        if data:
            snapshots.append({"ts": end_time, "data": data})

    return sorted(snapshots, key=lambda x: x["ts"])

# Pricing per 1M tokens (USD)
PRICING = {
    "opus": {"input": 15.0, "output": 75.0, "cacheRead": 1.5, "cacheCreation": 18.75},
    "sonnet": {"input": 3.0, "output": 15.0, "cacheRead": 0.3, "cacheCreation": 3.75},
    "haiku": {"input": 0.25, "output": 1.25, "cacheRead": 0.025, "cacheCreation": 0.3125},
}

def get_token_delta(snapshots: list, start_ts: float, end_ts: float) -> dict:
    """Get token delta between two timestamps."""
    # Find snapshots bracketing the time range
    before = None
    after = None

    for s in snapshots:
        if s["ts"] <= start_ts:
            before = s
        if s["ts"] >= end_ts and after is None:
            after = s

    if not before or not after:
        return {}

    delta = {}
    for key in after["data"]:
        d = after["data"].get(key, 0) - before["data"].get(key, 0)
        if d > 0:
            delta[key] = d
    return delta

def calculate_cost(delta: dict) -> float:
    """Calculate USD cost from token delta."""
    cost = 0.0
    for key, tokens in delta.items():
        parts = key.split("_")
        if len(parts) == 2:
            model, tok_type = parts
            if model in PRICING and tok_type in PRICING[model]:
                cost += tokens * PRICING[model][tok_type] / 1_000_000
    return cost

def analyze_steps(trace_path: str, otel_path: str):
    """Analyze and print per-step/subagent breakdown."""
    events = parse_trace(trace_path)
    snapshots = parse_otel_snapshots(otel_path)

    if not events:
        print("No events")
        return

    session_start = events[0]["ts"]

    print("=" * 80)
    print("STEP-BY-STEP EXECUTION TIMELINE")
    print("=" * 80)
    print()

    # Identify phases based on tool patterns
    phases = []
    current_phase = {"name": "Init", "start": session_start, "tools": [], "subagents": 0}

    task_starts = []  # Stack of Task PRE_TOOL timestamps

    for e in events:
        rel_time = e["ts"] - session_start

        if e["type"] == "SESSION_START":
            current_phase["start"] = e["ts"]

        elif e["type"] == "SUBAGENT_END" and not task_starts:
            # Initial subagents (skill loading)
            current_phase["subagents"] += 1

        elif e["type"] == "PRE_TOOL":
            tool = e.get("tool", "?")
            current_phase["tools"].append(tool)

            if tool == "Task":
                task_starts.append(e["ts"])
            elif tool == "Skill" and "youtube" not in current_phase["name"]:
                # Skill invocation marks new phase
                if current_phase["tools"]:
                    current_phase["end"] = e["ts"]
                    phases.append(current_phase)
                current_phase = {"name": "Skill: youtube-to-markdown", "start": e["ts"], "tools": [], "subagents": 0}

        elif e["type"] == "SUBAGENT_END" and task_starts:
            current_phase["subagents"] += 1

        elif e["type"] == "POST_TOOL":
            tool = e.get("tool", "?")
            if tool == "Task" and task_starts:
                task_starts.pop()

        elif e["type"] == "SESSION_END":
            current_phase["end"] = e["ts"]
            phases.append(current_phase)

    # Now print phases with token info
    for i, phase in enumerate(phases):
        duration = phase.get("end", events[-1]["ts"]) - phase["start"]
        rel_start = phase["start"] - session_start

        # Get token delta for this phase
        delta = get_token_delta(snapshots, phase["start"], phase.get("end", events[-1]["ts"]))

        print(f"Phase {i+1}: {phase['name']}")
        print(f"  Time: +{rel_start:.0f}s, duration {duration:.1f}s")
        print(f"  Subagents completed: {phase['subagents']}")

        # Tool summary
        tool_counts = {}
        for t in phase["tools"]:
            tool_counts[t] = tool_counts.get(t, 0) + 1
        if tool_counts:
            tools_str = ", ".join(f"{t}:{c}" for t, c in sorted(tool_counts.items()))
            print(f"  Tools: {tools_str}")

        # Token delta
        if delta:
            opus_out = delta.get("opus_output", 0)
            haiku_out = delta.get("haiku_output", 0)
            sonnet_out = delta.get("sonnet_output", 0)
            print(f"  Tokens out: opus={opus_out}, haiku={haiku_out}, sonnet={sonnet_out}")

        print()

    # Now detailed subagent timeline - collect all first, sort by start time
    print("=" * 80)
    print("SUBAGENT EXECUTION DETAILS")
    print("=" * 80)
    print()

    # Collect Task PRE/POST pairs with their indices
    task_events = [(i, e) for i, e in enumerate(events)
                   if e["type"] in ("PRE_TOOL", "POST_TOOL") and e.get("tool") == "Task"]

    # Match PRE with POST by finding closest POST after each PRE
    subagents = []
    used_posts = set()

    pre_events = [(i, e) for i, e in task_events if e["type"] == "PRE_TOOL"]
    post_events = [(i, e) for i, e in task_events if e["type"] == "POST_TOOL"]

    for pre_idx, pre_e in pre_events:
        # Find first POST after this PRE that isn't used
        for post_idx, post_e in post_events:
            if post_idx > pre_idx and post_idx not in used_posts:
                used_posts.add(post_idx)
                subagents.append({
                    "start": pre_e["ts"],
                    "end": post_e["ts"],
                    "duration": post_e["ts"] - pre_e["ts"]
                })
                break

    # Sort by start time
    subagents.sort(key=lambda x: x["start"])

    # Auto-detect skill variant by subagent count
    step_defs = get_step_definitions(len(subagents))

    # Identify parallel groups and assign IDs
    for i, sa in enumerate(subagents):
        sa["id"] = i + 1
        start_rel = sa["start"] - session_start
        end_rel = sa["end"] - session_start

        # Get tokens for this subagent
        delta = get_token_delta(snapshots, sa["start"], sa["end"])
        opus_out = delta.get("opus_output", 0)
        haiku_out = delta.get("haiku_output", 0)
        sonnet_out = delta.get("sonnet_output", 0)

        # Get step name
        if i < len(step_defs):
            step_name, expected_model, _ = step_defs[i]
        else:
            step_name = f"Subagent #{i + 1}"

        # Check if parallel with previous
        parallel = ""
        if i > 0 and sa["start"] < subagents[i-1]["end"]:
            prev_name = step_defs[i-1][0] if i-1 < len(step_defs) else f"#{i}"
            parallel = f" [parallel with {prev_name}]"

        print(f"{step_name}{parallel}:")
        print(f"  Time: +{start_rel:.0f}s → +{end_rel:.0f}s ({sa['duration']:.1f}s)")
        print(f"  Tokens out: opus={opus_out}, haiku={haiku_out}, sonnet={sonnet_out}")
        print()

    # Final summary table
    print("=" * 80)
    print("SUMMARY TABLE (output tokens + cost)")
    print("=" * 80)
    print()

    # Header
    step_col = 32
    print(f"{'Step':<{step_col}} {'Dur':>6} {'Opus':>7} {'Haiku':>7} {'Sonnet':>7} {'Cost':>8}")
    print("-" * 75)

    total_opus = 0
    total_haiku = 0
    total_sonnet = 0
    total_cost = 0.0

    for i, sa in enumerate(subagents):
        start_rel = sa["start"] - session_start
        end_rel = sa["end"] - session_start
        delta = get_token_delta(snapshots, sa["start"], sa["end"])
        opus = delta.get("opus_output", 0)
        haiku = delta.get("haiku_output", 0)
        sonnet = delta.get("sonnet_output", 0)
        cost = calculate_cost(delta)
        total_opus += opus
        total_haiku += haiku
        total_sonnet += sonnet
        total_cost += cost

        # Get step name from definitions, with parallel indicator
        if i < len(step_defs):
            step_name, expected_model, is_parallel = step_defs[i]
            if is_parallel and i + 1 < len(subagents):
                # Check if next subagent starts at same time (parallel)
                next_start = subagents[i + 1]["start"] - session_start
                if abs(next_start - start_rel) < 1:
                    step_name += " ||"
        else:
            step_name = f"Subagent #{i + 1}"

        print(f"{step_name:<{step_col}} {sa['duration']:>5.1f}s {opus:>7} {haiku:>7} {sonnet:>7} ${cost:>6.3f}")

    print("-" * 75)
    print(f"{'Subagents total*':<{step_col}} {'':>6} {total_opus:>7} {total_haiku:>7} {total_sonnet:>7} ${total_cost:>6.2f}")
    print("  * Parallel steps share token deltas (may double-count)")

    # Calculate orchestration overhead (full session - subagents)
    if snapshots:
        first = snapshots[0]
        last = snapshots[-1]
        session_delta = {}
        for key in last["data"]:
            d = last["data"].get(key, 0) - first["data"].get(key, 0)
            if d > 0:
                session_delta[key] = d

        session_opus = session_delta.get("opus_output", 0)
        session_haiku = session_delta.get("haiku_output", 0)
        session_sonnet = session_delta.get("sonnet_output", 0)
        session_cost = calculate_cost(session_delta)

        orch_opus = session_opus - total_opus
        orch_haiku = session_haiku - total_haiku
        orch_sonnet = session_sonnet - total_sonnet
        orch_cost = session_cost - total_cost

        # Note: parallel subagents cause double-counting, so only show orchestration opus
        # (haiku/sonnet would be negative due to overlap)
        print(f"{'Orchestration (opus)':<{step_col}} {'':>6} {orch_opus:>7} {'':>7} {'':>7} ${orch_cost:>6.2f}")
        print("-" * 75)
        print(f"{'SESSION TOTAL (accurate)':<{step_col}} {'':>6} {session_opus:>7} {session_haiku:>7} {session_sonnet:>7} ${session_cost:>6.2f}")

    # Caching summary
    print()
    print("=" * 80)
    print("CACHING SUMMARY")
    print("=" * 80)
    print()

    # Get total delta for full session
    if snapshots:
        first = snapshots[0]
        last = snapshots[-1]

        print(f"{'Model':<8} {'CacheRead':>12} {'CacheCreate':>12} {'Saved':>12}")
        print("-" * 50)

        for model in ["opus", "sonnet", "haiku"]:
            cache_read = last["data"].get(f"{model}_cacheRead", 0) - first["data"].get(f"{model}_cacheRead", 0)
            cache_create = last["data"].get(f"{model}_cacheCreation", 0) - first["data"].get(f"{model}_cacheCreation", 0)

            if cache_read > 0 or cache_create > 0:
                # Calculate savings: cacheRead is 10x cheaper than input
                input_price = PRICING[model]["input"]
                cache_price = PRICING[model]["cacheRead"]
                saved = cache_read * (input_price - cache_price) / 1_000_000
                print(f"{model:<8} {cache_read:>12,} {cache_create:>12,} ${saved:>10.3f}")

if __name__ == "__main__":
    trace_log = sys.argv[1] if len(sys.argv) > 1 else "./agent_trace.log"
    otel_log = sys.argv[2] if len(sys.argv) > 2 else "./otel_metrics.log"
    analyze_steps(trace_log, otel_log)
