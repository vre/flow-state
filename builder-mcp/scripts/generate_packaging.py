#!/usr/bin/env python3
"""Generate packaging files for an MCP server (.mcp.json, README.md).

Usage:
    python3 generate_packaging.py '{"domain":"weather","description":"Weather data","version":"0.1.0"}'

Output: writes .mcp.json and README.md to current directory.
"""

import json
import sys
from pathlib import Path


def generate_mcp_json(domain: str, transport: str = "stdio") -> str:
    """Generate .mcp.json for Claude plugin install."""
    entry_point = f"{domain}-mcp"
    if transport == "streamable-http":
        config = {
            entry_point: {
                "type": "http",
                "url": "http://localhost:${PORT}/mcp",
            }
        }
    else:
        config = {
            entry_point: {
                "command": "uv",
                "args": ["--directory", "${CLAUDE_PLUGIN_ROOT}", "run", entry_point],
            }
        }
    return json.dumps(config, indent=2) + "\n"


def generate_readme(domain: str, description: str, actions: list[str], transport: str = "stdio") -> str:
    """Generate minimal README.md."""
    actions_list = "\n".join(f"- `{a}` - TODO: describe" for a in actions)
    install_block = f"""```bash
claude mcp add {domain}-mcp -- uv --directory /path/to/{domain}-mcp run {domain}-mcp
```"""
    if transport == "streamable-http":
        install_block = f"""```json
{{
  "{domain}-mcp": {{
    "type": "http",
    "url": "http://localhost:${{PORT}}/mcp"
  }}
}}
```"""
    return f"""# {domain}-mcp

{description}. MCP server for Claude Desktop/Code.

## Install

{install_block}

## Actions

{actions_list}
- `help` - Show documentation

## Usage

```
{{action: "help"}}                    # Show all actions
{{action: "{actions[0] if actions else "help"}", payload: "..."}}   # TODO
```

## Development

```bash
uv sync
uv run {domain}-mcp
```
"""


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print(
            "Usage: python3 generate_packaging.py '<json_config>'\n"
            'Example: \'{"domain":"weather","description":"Weather data","actions":["get"]}\'',
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        config = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if "domain" not in config:
        print("Missing required field: domain", file=sys.stderr)
        sys.exit(1)

    domain = config["domain"]
    description = config.get("description", f"{domain.title()} operations")
    actions = config.get("actions", [])
    transport = config.get("transport", "stdio")

    mcp_json = generate_mcp_json(domain, transport=transport)
    Path(".mcp.json").write_text(mcp_json)

    readme = generate_readme(domain, description, actions, transport=transport)
    Path("README.md").write_text(readme)

    print(json.dumps({"created": [".mcp.json", "README.md"], "domain": domain}))


if __name__ == "__main__":
    main()
