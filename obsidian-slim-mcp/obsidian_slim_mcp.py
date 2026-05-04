#!/usr/bin/env python3
"""Obsidian MCP Server — vault operations via Local REST API.

Single tool with action dispatcher (~500 tokens vs typical 15,000+).
Self-documenting via 'help' action.

Usage with Claude Desktop/Code:
    Add to your MCP config:
    {
        "mcpServers": {
            "obsidian-slim-mcp": {
                "command": "uv",
                "args": ["--directory", "/path/to/obsidian-slim-mcp", "run", "obsidian-slim-mcp"]
            }
        }
    }
"""

import json

import obsidian_client as api
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

mcp = FastMCP(
    "obsidian_slim_mcp",
    instructions=("Use when reading, writing, searching, or managing notes in an Obsidian vault via the Local REST API plugin."),
)


class ObsidianAction(BaseModel):
    """Input for use_obsidian tool."""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: str = Field(
        ...,
        description=(
            "Action: list|read|write|append|patch|delete|search|search_advanced"
            "|outlinks|backlinks|broken_links"
            "|tags|commands|command_run|open|active_read|active_write"
            "|periodic_read|periodic_write|periodic_append|help"
        ),
    )
    payload: str | None = Field(
        default=None,
        description="Action-specific data (see help for details)",
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid = {
            "active_read",
            "active_write",
            "append",
            "backlinks",
            "broken_links",
            "command_run",
            "commands",
            "delete",
            "help",
            "list",
            "open",
            "outlinks",
            "patch",
            "periodic_append",
            "periodic_read",
            "periodic_write",
            "read",
            "search",
            "search_advanced",
            "tags",
            "write",
        }
        v_lower = v.lower()
        if v_lower not in valid:
            raise ValueError(f"Invalid action '{v}'. Valid: {', '.join(sorted(valid))}")
        return v_lower


HELP_TOPICS = {
    "overview": """# Obsidian Vault Tool

## Actions

- **list** — List vault root or a directory
- **read** — Read a file (markdown or JSON with frontmatter/tags)
- **write** — Create or replace a file
- **append** — Append content to a file
- **patch** — Partial update targeting a heading, block, or frontmatter
- **delete** — Delete a file
- **search** — Simple text search
- **search_advanced** — Dataview DQL or JsonLogic search
- **outlinks** — Parse outgoing links from a file
- **backlinks** — Find all files linking to a given file
- **broken_links** — Find broken links in vault or directory
- **tags** — List all tags with counts
- **commands** — List available Obsidian commands
- **command_run** — Execute an Obsidian command
- **open** — Open a file in the Obsidian UI
- **active_read** — Read the currently active file
- **active_write** — Replace the active file's content
- **periodic_read** — Read a periodic note (daily/weekly/monthly/quarterly/yearly)
- **periodic_write** — Replace a periodic note
- **periodic_append** — Append to a periodic note

## Quick Start

{action: "list"} — list vault root
{action: "read", payload: "index.md"} — read a file
{action: "search", payload: "meeting notes"} — search vault
{action: "help", payload: "patch"} — detailed help on patch
""",
    "list": """# list — List directory contents

## Payload
- Path to directory (default: "/" for vault root)
- Multiple paths: one per line (newline-separated)
- Directories in the vault end with "/"

## Examples
{action: "list"} — vault root
{action: "list", payload: "projects/"} — list projects directory
{action: "list", payload: "projects/\\ntopics/"} — list two directories
""",
    "read": """# read — Read a file

## Payload
- File path in the vault
- Multiple paths: one per line (newline-separated)
- Append "|json" to get structured JSON with frontmatter, tags, and stat

## Examples
{action: "read", payload: "index.md"} — markdown
{action: "read", payload: "index.md|json"} — JSON with metadata
{action: "read", payload: "CLAUDE.md\\nindex.md"} — read two files
""",
    "write": """# write — Create or replace a file

## Payload
JSON: {"file": "path/to/note.md", "content": "# Title\\n\\nBody text"}

## Example
{action: "write", payload: '{"file":"notes/new.md","content":"# New Note\\n\\nContent here"}'}
""",
    "append": """# append — Append to a file

## Payload
JSON: {"file": "path/to/note.md", "content": "\\n## New Section\\n\\nAppended text"}

## Example
{action: "append", payload: '{"file":"log.md","content":"\\n- New entry"}'}
""",
    "patch": """# patch — Partial update

Target a heading, block reference, or frontmatter field.

## Payload
JSON: {"file": "path.md", "content": "new text", "operation": "append|prepend|replace", "target_type": "heading|block|frontmatter", "target": "Section Name"}

## Example
{action: "patch", payload: '{"file":"notes/project.md","content":"\\n- task done","operation":"append","target_type":"heading","target":"Tasks"}'}
""",
    "delete": """# delete — Delete a file

## Payload
File path to delete.

## Example
{action: "delete", payload: "scratch/temp.md"}
""",
    "search": """# search — Simple text search

## Payload
Search query text. Optionally append "|N" for context length (default 100).

## Examples
{action: "search", payload: "meeting notes"}
{action: "search", payload: "project alpha|200"} — 200 chars context
""",
    "search_advanced": """# search_advanced — Dataview DQL or JsonLogic

## Payload
JSON: {"query": "DQL or JSON string", "type": "dataview|jsonlogic"}

Default type is "dataview".

## Examples
{action: "search_advanced", payload: '{"query":"TABLE file.mtime FROM \\"projects\\""}'}
{action: "search_advanced", payload: '{"query":"{\\"glob\\": [\\"*.md\\"]}","type":"jsonlogic"}'}
""",
    "outlinks": """# outlinks — Parse outgoing links

## Payload
File path.

## Example
{action: "outlinks", payload: "index.md"}

Returns list of {target, type, alias?, heading?, embed?}.
""",
    "backlinks": """# backlinks — Find incoming links

## Payload
File path.

## Example
{action: "backlinks", payload: "topics/knowledge-management.md"}

Returns list of {source, type, context}.
Note: scans entire vault (O(n)). Fine for vaults < 5000 files.
""",
    "broken_links": """# broken_links — Find broken links

## Payload
Optional directory path (default: entire vault).

## Examples
{action: "broken_links"} — scan entire vault
{action: "broken_links", payload: "projects/"} — scan one directory

Returns list of {source, target, type}.
""",
    "tags": """# tags — List all tags

No payload needed. Returns all tags with occurrence counts.

## Example
{action: "tags"}
""",
    "commands": """# commands — List Obsidian commands

No payload needed. Returns available command IDs and names.

## Example
{action: "commands"}
""",
    "command_run": """# command_run — Execute a command

## Payload
Command ID string (e.g., "editor:save-file").
Use {action: "commands"} to list available IDs.

## Example
{action: "command_run", payload: "editor:save-file"}
""",
    "open": """# open — Open file in Obsidian UI

## Payload
File path. Append "|new" to open in a new tab.

## Examples
{action: "open", payload: "index.md"}
{action: "open", payload: "notes/project.md|new"} — new tab
""",
    "active_read": """# active_read — Read active file

No payload needed. Returns the currently focused file.
Append "|json" for structured JSON output.

## Examples
{action: "active_read"}
{action: "active_read", payload: "json"}
""",
    "active_write": """# active_write — Replace active file content

## Payload
The new markdown content for the active file.

## Example
{action: "active_write", payload: "# Updated Title\\n\\nNew content"}
""",
    "periodic_read": """# periodic_read — Read periodic note

## Payload
Period type, optionally with date: "daily", "weekly|2026|4|1", etc.
Append "|json" for structured output.

## Examples
{action: "periodic_read", payload: "daily"} — today's daily note
{action: "periodic_read", payload: "weekly|2026|4|1"} — specific week
""",
    "periodic_write": """# periodic_write — Replace periodic note

## Payload
JSON: {"period": "daily", "content": "# Daily Note\\n\\nContent", "year": 2026, "month": 4, "day": 1}
year/month/day are optional (defaults to current period).

## Example
{action: "periodic_write", payload: '{"period":"daily","content":"# Today\\n\\n- Task 1"}'}
""",
    "periodic_append": """# periodic_append — Append to periodic note

## Payload
JSON: {"period": "daily", "content": "\\n- New item", "year": 2026, "month": 4, "day": 1}
year/month/day are optional (defaults to current period).

## Example
{action: "periodic_append", payload: '{"period":"daily","content":"\\n## Evening\\n- Reflection"}'}
""",
}


def _parse_json_payload(payload: str | None, required_fields: list[str] | None = None) -> dict:
    """Parse a JSON payload string. Returns dict or raises ValueError."""
    if not payload:
        raise ValueError("Payload required. Try: action=help")
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}. Payload must be valid JSON.") from e
    if required_fields:
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise ValueError(f"Missing fields: {', '.join(missing)}. Required: {', '.join(required_fields)}")
    return data


@mcp.tool(
    name="use_obsidian",
    annotations={
        "title": "Obsidian Vault",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def use_obsidian(params: ObsidianAction) -> str:
    """Obsidian vault operations via Local REST API. Actions: list|read|write|append|patch|delete|search|search_advanced|outlinks|backlinks|broken_links|tags|commands|command_run|open|active_read|active_write|periodic_read|periodic_write|periodic_append|help.

    Examples:
      {action:"help"} — show available actions
      {action:"list"} — list vault root
      {action:"read", payload:"index.md"} — read a file
      {action:"search", payload:"meeting notes"} — search
    """
    try:
        action = params.action
        payload = params.payload

        # --- Help ---
        if action == "help":
            topic = (payload or "overview").lower()
            if topic in HELP_TOPICS:
                return HELP_TOPICS[topic]
            return f"Unknown topic '{topic}'. Available: {', '.join(sorted(HELP_TOPICS.keys()))}"

        # --- Vault CRUD ---
        if action == "list":
            paths = [p.strip() for p in (payload or "/").split("\n") if p.strip()]
            if not paths:
                paths = ["/"]
            results = await api.list_dirs(paths)
            if len(paths) == 1:
                return json.dumps(results[paths[0]], indent=2)
            parts = []
            for path in paths:
                parts.append(f"=== {path} ===\n{json.dumps(results[path], indent=2)}")
            return "\n\n".join(parts)

        elif action == "read":
            raw = payload or ""
            if not raw:
                return 'Payload required: file path. Try: {action: "read", payload: "index.md"}'
            lines = [line.strip() for line in raw.split("\n") if line.strip()]
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
                if isinstance(val, dict):
                    return json.dumps(val, indent=2)
                return val
            parts = []
            for path in paths:
                val = results[path]
                if isinstance(val, dict):
                    parts.append(f"=== {path} ===\n{json.dumps(val, indent=2)}")
                else:
                    parts.append(f"=== {path} ===\n{val}")
            return "\n\n".join(parts)

        elif action == "write":
            data = _parse_json_payload(payload, ["file", "content"])
            result = await api.write_file(data["file"], data["content"])
            return json.dumps(result)

        elif action == "append":
            data = _parse_json_payload(payload, ["file", "content"])
            result = await api.append_file(data["file"], data["content"])
            return json.dumps(result)

        elif action == "patch":
            data = _parse_json_payload(payload, ["file", "content"])
            result = await api.patch_file(
                filename=data["file"],
                content=data["content"],
                operation=data.get("operation", "append"),
                target_type=data.get("target_type", "heading"),
                target=data.get("target", ""),
            )
            return json.dumps(result)

        elif action == "delete":
            if not payload:
                return 'Payload required: file path. Try: {action: "delete", payload: "scratch/temp.md"}'
            result = await api.delete_file(payload)
            return json.dumps(result)

        # --- Search ---
        elif action == "search":
            if not payload:
                return 'Payload required: search query. Try: {action: "search", payload: "meeting notes"}'
            parts = payload.rsplit("|", 1)
            query = parts[0]
            context_length = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 100
            results = await api.search_simple(query, context_length)
            return json.dumps(results, indent=2)

        elif action == "search_advanced":
            data = _parse_json_payload(payload, ["query"])
            results = await api.search_advanced(
                query=data["query"],
                query_type=data.get("type", "dataview"),
            )
            return json.dumps(results, indent=2)

        # --- Graph ---
        elif action == "outlinks":
            if not payload:
                return 'Payload required: file path. Try: {action: "outlinks", payload: "index.md"}'
            results = await api.outlinks(payload)
            return json.dumps(results, indent=2)

        elif action == "backlinks":
            if not payload:
                return 'Payload required: file path. Try: {action: "backlinks", payload: "index.md"}'
            results = await api.backlinks(payload)
            return json.dumps(results, indent=2)

        elif action == "broken_links":
            results = await api.broken_links(payload or "/")
            return json.dumps(results, indent=2)

        # --- Tags ---
        elif action == "tags":
            result = await api.list_tags()
            return json.dumps(result, indent=2)

        # --- Commands ---
        elif action == "commands":
            result = await api.list_commands()
            return json.dumps(result, indent=2)

        elif action == "command_run":
            if not payload:
                return 'Payload required: command ID. Try: {action: "commands"} to list available commands.'
            result = await api.run_command(payload)
            return json.dumps(result)

        # --- Open ---
        elif action == "open":
            if not payload:
                return 'Payload required: file path. Try: {action: "open", payload: "index.md"}'
            new_leaf = False
            path = payload
            if path.endswith("|new"):
                path = path[:-4]
                new_leaf = True
            result = await api.open_file(path, new_leaf=new_leaf)
            return json.dumps(result)

        # --- Active File ---
        elif action == "active_read":
            as_json = payload and payload.lower() == "json"
            result = await api.active_read(as_json=as_json)
            if isinstance(result, dict):
                return json.dumps(result, indent=2)
            return result

        elif action == "active_write":
            if not payload:
                return "Payload required: new content for active file."
            result = await api.active_write(payload)
            return json.dumps(result)

        # --- Periodic Notes ---
        elif action == "periodic_read":
            period, year, month, day, as_json = _parse_periodic_payload(payload)
            result = await api.periodic_read(
                period=period,
                year=year,
                month=month,
                day=day,
                as_json=as_json,
            )
            if isinstance(result, dict):
                return json.dumps(result, indent=2)
            return result

        elif action == "periodic_write":
            data = _parse_json_payload(payload, ["period", "content"])
            result = await api.periodic_write(
                content=data["content"],
                period=data["period"],
                year=data.get("year"),
                month=data.get("month"),
                day=data.get("day"),
            )
            return json.dumps(result)

        elif action == "periodic_append":
            data = _parse_json_payload(payload, ["period", "content"])
            result = await api.periodic_append(
                content=data["content"],
                period=data["period"],
                year=data.get("year"),
                month=data.get("month"),
                day=data.get("day"),
            )
            return json.dumps(result)

        return f"Unknown action '{action}'. Try: {', '.join(sorted(HELP_TOPICS.keys()))}"

    except json.JSONDecodeError as e:
        return f"JSON parse error: {e}. Check your payload format. Try: action=help"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error: {e}. Try: action=help for usage."


def _parse_periodic_payload(
    payload: str | None,
) -> tuple[str, int | None, int | None, int | None, bool]:
    """Parse periodic note payload like 'daily|2026|4|1|json'."""
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


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
