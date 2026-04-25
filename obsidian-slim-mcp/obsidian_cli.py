#!/usr/bin/env python3
"""Obsidian vault CLI — manage notes via Local REST API.

Usage:
    obsidian-cli <action> [payload] [options]
    obsidian-cli help [topic]

Actions:
    list                 List vault root or directory
    read                 Read a file
    write                Create or replace a file
    append               Append content to a file
    patch                Partial update (heading/block/frontmatter)
    delete               Delete a file
    search               Simple text search
    search_advanced      Dataview DQL or JsonLogic search
    tags                 List all tags
    commands             List Obsidian commands
    command_run          Execute an Obsidian command
    open                 Open file in Obsidian UI
    active_read          Read active file
    active_write         Replace active file content
    periodic_read        Read periodic note
    periodic_write       Replace periodic note
    periodic_append      Append to periodic note
    status               Check API server status
    help                 Show help

Flags:
    --format json|table  Output format (default: auto-detect TTY)
    --vault-url URL      Override OBSIDIAN_API_URL
    --api-key KEY        Override OBSIDIAN_API_KEY
    --quiet, -q          Suppress output, exit code only
    --yes                Skip confirmation for destructive actions
    --help, -h           Show this help
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_PERMISSION = 4
EXIT_NETWORK = 5


@dataclass
class Result:
    """Action result."""

    data: Any = None
    error: str | None = None
    exit_code: int = EXIT_OK
    metadata: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


# --- Action handlers (async, using obsidian_client) ---


async def _list(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    paths = [p.strip() for p in (payload or "/").split("\n") if p.strip()]
    if not paths:
        paths = ["/"]
    results = await api.list_dirs(paths)
    if len(paths) == 1:
        data = results[paths[0]]
        if "error" in data:
            return Result(error=data["error"], exit_code=EXIT_ERROR)
        return Result(data=data.get("files", []))
    return Result(data=results)


async def _read(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(error="File path required. Try: obsidian-cli read index.md", exit_code=EXIT_USAGE)
    lines = [line.strip() for line in payload.split("\n") if line.strip()]
    as_json = False
    paths = []
    for line in lines:
        if line.endswith("|json"):
            as_json = True
            paths.append(line[:-5])
        else:
            paths.append(line)
    results = await api.read_files(paths, as_json=as_json)
    if len(paths) == 1:
        val = results[paths[0]]
        if isinstance(val, str) and val.startswith("ERROR: "):
            return Result(error=val, exit_code=EXIT_ERROR)
        return Result(data=val)
    return Result(data=results)


async def _write(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(
            error='JSON required: {"file":"path.md","content":"# Title"}',
            exit_code=EXIT_USAGE,
        )
    data = json.loads(payload)
    result = await api.write_file(data["file"], data["content"])
    return Result(data=result)


async def _append(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(
            error='JSON required: {"file":"path.md","content":"appended text"}',
            exit_code=EXIT_USAGE,
        )
    data = json.loads(payload)
    result = await api.append_file(data["file"], data["content"])
    return Result(data=result)


async def _patch(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(
            error='JSON required: {"file":"path.md","content":"text","operation":"append","target_type":"heading","target":"Section"}',
            exit_code=EXIT_USAGE,
        )
    data = json.loads(payload)
    result = await api.patch_file(
        filename=data["file"],
        content=data["content"],
        operation=data.get("operation", "append"),
        target_type=data.get("target_type", "heading"),
        target=data.get("target", ""),
    )
    return Result(data=result)


async def _delete(payload: str | None = None, confirmed: bool = False, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(error="File path required. Try: obsidian-cli delete scratch/temp.md", exit_code=EXIT_USAGE)
    if not confirmed and sys.stdin.isatty():
        answer = input(f"Delete '{payload}'? [y/N] ")
        if answer.lower() != "y":
            return Result(data={"status": "cancelled"})
    result = await api.delete_file(payload)
    return Result(data=result)


async def _search(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(error="Search query required. Try: obsidian-cli search 'meeting notes'", exit_code=EXIT_USAGE)
    parts = payload.rsplit("|", 1)
    query = parts[0]
    ctx_len = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 100
    results = await api.search_simple(query, ctx_len)
    # Flatten for table display
    rows = []
    for item in results:
        for match in item.get("matches", []):
            rows.append(
                {
                    "file": item["filename"],
                    "context": match.get("context", "")[:120],
                }
            )
    return Result(data=rows, metadata={"total_files": len(results)})


async def _search_advanced(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(
            error='JSON required: {"query":"DQL string","type":"dataview"}',
            exit_code=EXIT_USAGE,
        )
    data = json.loads(payload)
    results = await api.search_advanced(
        query=data["query"],
        query_type=data.get("type", "dataview"),
    )
    return Result(data=results)


async def _tags(**_: Any) -> Result:
    import obsidian_client as api

    result = await api.list_tags()
    return Result(data=result.get("tags", []))


async def _commands(**_: Any) -> Result:
    import obsidian_client as api

    result = await api.list_commands()
    return Result(data=result.get("commands", []))


async def _command_run(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(
            error="Command ID required. Try: obsidian-cli commands (to list IDs)",
            exit_code=EXIT_USAGE,
        )
    result = await api.run_command(payload)
    return Result(data=result)


async def _open(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(error="File path required. Try: obsidian-cli open index.md", exit_code=EXIT_USAGE)
    new_leaf = payload.endswith("|new")
    path = payload[:-4] if new_leaf else payload
    result = await api.open_file(path, new_leaf=new_leaf)
    return Result(data=result)


async def _active_read(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    as_json = payload and payload.lower() == "json"
    result = await api.active_read(as_json=as_json)
    return Result(data=result)


async def _active_write(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(error="Content required for active file.", exit_code=EXIT_USAGE)
    result = await api.active_write(payload)
    return Result(data=result)


async def _periodic_read(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    period, year, month, day, as_json = _parse_periodic(payload)
    result = await api.periodic_read(period=period, year=year, month=month, day=day, as_json=as_json)
    return Result(data=result)


async def _periodic_write(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(
            error='JSON required: {"period":"daily","content":"# Note"}',
            exit_code=EXIT_USAGE,
        )
    data = json.loads(payload)
    result = await api.periodic_write(
        content=data["content"],
        period=data["period"],
        year=data.get("year"),
        month=data.get("month"),
        day=data.get("day"),
    )
    return Result(data=result)


async def _periodic_append(payload: str | None = None, **_: Any) -> Result:
    import obsidian_client as api

    if not payload:
        return Result(
            error='JSON required: {"period":"daily","content":"- item"}',
            exit_code=EXIT_USAGE,
        )
    data = json.loads(payload)
    result = await api.periodic_append(
        content=data["content"],
        period=data["period"],
        year=data.get("year"),
        month=data.get("month"),
        day=data.get("day"),
    )
    return Result(data=result)


async def _status(**_: Any) -> Result:
    import obsidian_client as api

    result = await api.server_status()
    return Result(data=result)


def _help(payload: str | None = None, **_: Any) -> Result:
    if payload and payload in ACTIONS:
        fn = ACTIONS[payload]
        doc = (fn.__doc__ or "No documentation.").strip()
        return Result(data={"action": payload, "help": doc})
    actions = []
    for name, fn in ACTIONS.items():
        doc = (fn.__doc__ or "").split("\n")[0].strip()
        actions.append({"action": name, "description": doc})
    return Result(data=actions)


def _parse_periodic(payload: str | None) -> tuple[str, int | None, int | None, int | None, bool]:
    if not payload:
        return "daily", None, None, None, False
    parts = payload.split("|")
    period = parts[0] if parts else "daily"
    as_json = "json" in parts[1:]
    nums = [p for p in parts[1:] if p != "json" and p.isdigit()]
    year = int(nums[0]) if len(nums) > 0 else None
    month = int(nums[1]) if len(nums) > 1 else None
    day = int(nums[2]) if len(nums) > 2 else None
    return period, year, month, day, as_json


ACTIONS: dict[str, Any] = {
    "list": _list,
    "read": _read,
    "write": _write,
    "append": _append,
    "patch": _patch,
    "delete": _delete,
    "search": _search,
    "search_advanced": _search_advanced,
    "tags": _tags,
    "commands": _commands,
    "command_run": _command_run,
    "open": _open,
    "active_read": _active_read,
    "active_write": _active_write,
    "periodic_read": _periodic_read,
    "periodic_write": _periodic_write,
    "periodic_append": _periodic_append,
    "status": _status,
    "help": _help,
}


# --- Output formatting ---


def format_output(result: Result, fmt: str = "auto") -> str:
    """Format result for terminal or JSON output."""
    if fmt == "auto":
        fmt = "table" if sys.stdout.isatty() else "json"

    if not result.ok:
        payload = {"success": False, "error": result.error}
        if fmt == "json":
            return json.dumps(payload, indent=2)
        return f"Error: {result.error}"

    data = result.data

    # Raw string data (markdown content) — pass through
    if isinstance(data, str):
        if fmt == "json":
            return json.dumps({"success": True, "data": data}, indent=2)
        return data

    payload = {"success": True, "data": data}
    if result.metadata:
        payload["metadata"] = result.metadata

    if fmt == "json":
        return json.dumps(payload, indent=2)
    if fmt == "table":
        return _format_table(data)
    return str(data)


def _format_table(data: Any) -> str:
    if isinstance(data, list) and data and isinstance(data[0], dict):
        headers = list(data[0].keys())
        widths = {h: max(len(h), max((len(str(row.get(h, ""))) for row in data), default=0)) for h in headers}
        lines = [
            " | ".join(h.ljust(widths[h]) for h in headers),
            "-+-".join("-" * widths[h] for h in headers),
        ]
        for row in data:
            lines.append(" | ".join(str(row.get(h, "")).ljust(widths[h]) for h in headers))
        return "\n".join(lines)
    if isinstance(data, list) and data and isinstance(data[0], str):
        return "\n".join(data)
    if isinstance(data, dict):
        max_key = max((len(str(k)) for k in data), default=0)
        return "\n".join(f"{str(k).ljust(max_key)}  {v}" for k, v in data.items())
    return str(data)


# --- Argument parsing ---


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="obsidian-cli",
        description="Obsidian vault operations via Local REST API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="help",
        choices=sorted(ACTIONS.keys()),
        help="Action to perform",
    )
    parser.add_argument(
        "payload",
        nargs="*",
        default=[],
        help="Action-specific payload(s) — read and list accept multiple paths",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=["json", "table"],
        default=None,
        help="Output format (default: auto-detect TTY)",
    )
    parser.add_argument("--vault-url", help="Override OBSIDIAN_API_URL")
    parser.add_argument("--api-key", help="Override OBSIDIAN_API_KEY")
    parser.add_argument("--quiet", "-q", action="store_true", help="Exit code only")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompts")
    return parser


def dispatch(action: str, **kwargs: Any) -> Result:
    """Route action to handler."""
    if action not in ACTIONS:
        valid = ", ".join(sorted(ACTIONS.keys()))
        return Result(
            error=f"Unknown action '{action}'. Valid: {valid}",
            exit_code=EXIT_USAGE,
        )
    handler = ACTIONS[action]
    if asyncio.iscoroutinefunction(handler):
        return asyncio.run(handler(**kwargs))
    return handler(**kwargs)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Override env vars from flags
    if args.vault_url:
        os.environ["OBSIDIAN_API_URL"] = args.vault_url
    if args.api_key:
        os.environ["OBSIDIAN_API_KEY"] = args.api_key

    kwargs: dict[str, Any] = {}
    if args.payload:
        if args.action in ("read", "list"):
            kwargs["payload"] = "\n".join(args.payload)
        else:
            kwargs["payload"] = " ".join(args.payload)
    if args.yes:
        kwargs["confirmed"] = True

    result = dispatch(args.action, **kwargs)

    if not args.quiet:
        fmt = args.output_format or "auto"
        output = format_output(result, fmt=fmt)
        if output:
            if result.ok:
                print(output)
            else:
                print(output, file=sys.stderr)

    return result.exit_code


if __name__ == "__main__":
    sys.exit(main())
