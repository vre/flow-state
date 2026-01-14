#!/usr/bin/env python3
"""
Analyze token usage from Claude Code session logs.
Usage: python3 analyze_run.py [trace_log] [otel_log]
"""
import sys
import re
from datetime import datetime
from collections import defaultdict

def parse_trace_log(path: str) -> list[dict]:
    """Parse agent_trace.log into events."""
    events = []
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 2:
                event = {"type": parts[0], "timestamp": float(parts[1])}
                if len(parts) >= 3:
                    event["tool"] = parts[2]
                events.append(event)
    return events

def parse_otel_log(path: str) -> list[dict]:
    """Parse OTel console output into metrics snapshots."""
    snapshots = []
    with open(path) as f:
        content = f.read()

    # Split into metric blocks by looking for descriptor patterns
    blocks = re.split(r'\n\{[\s\n]+descriptor:', content)

    for block in blocks[1:]:  # Skip first empty
        block = "descriptor:" + block

        # Determine metric type
        if 'name: "claude_code.token.usage"' in block:
            metric_type = "tokens"
        elif 'name: "claude_code.cost.usage"' in block:
            metric_type = "cost"
        else:
            continue

        snapshot = {"type": metric_type, "data": {}}

        # Find all model/type/value/endTime - collect all then match
        models = re.findall(r'model: "([^"]+)"', block)
        types = re.findall(r'type: "(input|output|cacheRead|cacheCreation)"', block)
        values = re.findall(r'^\s*value: ([\d.]+)', block, re.MULTILINE)
        ends = re.findall(r'endTime: \[\s*(\d+),\s*(\d+)\s*\]', block)

        if metric_type == "tokens":
            # Token datapoints have model, type, value in order
            for i, (model, tok_type, value) in enumerate(zip(models, types, values)):
                key = f"{model}_{tok_type}"
                snapshot["data"][key] = int(float(value))
            if ends:
                snapshot["end_time"] = int(ends[-1][0]) + int(ends[-1][1]) / 1e9
        else:
            # Cost datapoints have model, value in order
            for model, value in zip(models, values):
                snapshot["data"][model] = float(value)
            if ends:
                snapshot["end_time"] = int(ends[-1][0]) + int(ends[-1][1]) / 1e9

        if snapshot["data"]:
            snapshots.append(snapshot)

    return snapshots

def analyze(trace_path: str, otel_path: str):
    """Analyze and print summary."""
    events = parse_trace_log(trace_path)
    snapshots = parse_otel_log(otel_path)

    if not events:
        print("No trace events found")
        return

    # Session timeline
    start_time = events[0]["timestamp"]
    end_time = events[-1]["timestamp"]
    duration = end_time - start_time

    print("=" * 70)
    print("SESSION SUMMARY")
    print("=" * 70)
    print(f"Duration: {duration:.1f}s")
    print()

    # Tool usage breakdown
    print("TOOL CALLS")
    print("-" * 70)
    tool_counts = defaultdict(int)
    tool_times = defaultdict(list)

    pre_tools = {}
    for e in events:
        if e["type"] == "PRE_TOOL" and "tool" in e:
            pre_tools[e["tool"]] = e["timestamp"]
            tool_counts[e["tool"]] += 1
        elif e["type"] == "POST_TOOL" and "tool" in e:
            if e["tool"] in pre_tools:
                elapsed = e["timestamp"] - pre_tools[e["tool"]]
                tool_times[e["tool"]].append(elapsed)

    print(f"{'Tool':<20} {'Count':>8} {'Avg Time':>12} {'Total':>12}")
    print("-" * 52)
    for tool in sorted(tool_counts.keys()):
        count = tool_counts[tool]
        times = tool_times.get(tool, [])
        avg = sum(times) / len(times) if times else 0
        total = sum(times)
        print(f"{tool:<20} {count:>8} {avg:>10.2f}s {total:>10.2f}s")

    # Subagent events
    subagent_count = sum(1 for e in events if e["type"] == "SUBAGENT_END")
    print()
    print(f"Subagent completions: {subagent_count}")

    # Token/cost summary from final snapshot
    if snapshots:
        print()
        print("TOKEN USAGE (cumulative)")
        print("-" * 70)

        # Get last token snapshot
        token_snapshots = [s for s in snapshots if s["type"] == "tokens"]
        if token_snapshots:
            final = token_snapshots[-1]["data"]

            # Group by model
            models = set()
            for key in final:
                model = key.rsplit("_", 1)[0]
                models.add(model)

            for model in sorted(models):
                short_name = model.split("-")[1] if "-" in model else model
                input_tok = final.get(f"{model}_input", 0)
                output_tok = final.get(f"{model}_output", 0)
                cache_read = final.get(f"{model}_cacheRead", 0)
                cache_create = final.get(f"{model}_cacheCreation", 0)

                print(f"\n{short_name}:")
                print(f"  Input:          {input_tok:>10,}")
                print(f"  Output:         {output_tok:>10,}")
                print(f"  Cache read:     {cache_read:>10,}")
                print(f"  Cache creation: {cache_create:>10,}")

        # Cost summary
        cost_snapshots = [s for s in snapshots if s["type"] == "cost"]
        if cost_snapshots:
            final_cost = cost_snapshots[-1]["data"]
            total_cost = sum(final_cost.values())

            print()
            print("COST BREAKDOWN")
            print("-" * 70)
            for model, cost in sorted(final_cost.items()):
                short_name = model.split("-")[1] if "-" in model else model
                print(f"  {short_name:<15} ${cost:.4f}")
            print(f"  {'TOTAL':<15} ${total_cost:.4f}")

    # Timeline with deltas
    if len(snapshots) > 1:
        print()
        print("TOKEN DELTA TIMELINE (5s intervals)")
        print("-" * 70)

        token_snapshots = sorted(
            [s for s in snapshots if s["type"] == "tokens"],
            key=lambda x: x.get("end_time", 0)
        )

        prev = None
        for snap in token_snapshots:
            if prev:
                # Calculate deltas
                deltas = {}
                for key in snap["data"]:
                    delta = snap["data"].get(key, 0) - prev["data"].get(key, 0)
                    if delta > 0:
                        deltas[key] = delta

                if deltas:
                    t = snap.get("end_time", 0) - start_time
                    opus_out = deltas.get("claude-opus-4-5-20251101_output", 0)
                    haiku_out = deltas.get("claude-haiku-4-5-20251001_output", 0)
                    print(f"  +{t:>5.0f}s: opus_out={opus_out:>5}, haiku_out={haiku_out:>5}")
            prev = snap

    print()
    print("=" * 70)

if __name__ == "__main__":
    trace_log = sys.argv[1] if len(sys.argv) > 1 else "./agent_trace.log"
    otel_log = sys.argv[2] if len(sys.argv) > 2 else "./otel_metrics.log"
    analyze(trace_log, otel_log)
