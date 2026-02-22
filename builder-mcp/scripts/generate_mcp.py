#!/usr/bin/env python3
"""Generate a single-tool MCP server with action dispatcher.

Usage:
    python3 generate_mcp.py '{"domain":"weather","actions":["get","forecast","alerts"],"description":"Weather data","auth_method":"env_var","has_external_api":true}'

Output: writes {domain}_mcp.py to current directory.
"""

import json
import sys
from pathlib import Path
from typing import TypedDict


class McpConfig(TypedDict, total=False):
    """Configuration for MCP server generation."""

    domain: str  # Required: domain name (e.g., "weather")
    actions: list[str]  # Required: action names (e.g., ["get", "forecast"])
    description: str  # Optional: tool description
    auth_method: str  # Optional: "none" | "env_var" | "keyring"
    has_external_api: bool  # Optional: whether tool calls external APIs


def generate_action_validator(actions: list[str]) -> str:
    """Generate Pydantic field validator for actions."""
    actions_with_help = sorted(set(actions + ["help"]))
    actions_set = ", ".join(f'"{a}"' for a in actions_with_help)
    return f"""    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        valid = {{{actions_set}}}
        v_lower = v.lower()
        if v_lower not in valid:
            raise ValueError(f"Invalid action '{{v}}'. Valid: {{', '.join(sorted(valid))}}")
        return v_lower"""


def generate_help_topics(domain: str, actions: list[str]) -> str:
    """Generate HELP_TOPICS dict with overview and per-action stubs."""
    action_lines = "\n".join(f"- **{a}** - TODO: describe" for a in actions)
    example_action = actions[0] if actions else "list"

    topics = [
        f'    "overview": """\n# {domain.title()} Tool\n\n## Actions\n\n{action_lines}\n\n## Examples\n\n{{action: "help", payload: "{example_action}"}}\n"""',
    ]
    for action in actions:
        topics.append(
            f'    "{action}": """\n# {action} - TODO: Title\n\nTODO: describe what this action does.\n\n## Parameters\n- payload: TODO\n\n## Example\n{{action: "{action}", payload: "TODO"}}\n"""'
        )

    return "HELP_TOPICS = {\n" + ",\n".join(topics) + ",\n}"


def generate_action_handlers(actions: list[str]) -> str:
    """Generate action dispatcher elif blocks."""
    blocks = []
    for i, action in enumerate(actions):
        keyword = "if" if i == 0 else "elif"
        blocks.append(
            f"""        {keyword} action == "{action}":
            # TODO: implement {action}
            return f"Action '{action}' not yet implemented.\""""
        )
    return "\n\n".join(blocks)


def generate_pydantic_model(domain: str, actions: list[str]) -> str:
    """Generate Pydantic input model."""
    actions_desc = "|".join(sorted(set(actions + ["help"])))
    return f'''class {domain.title()}Action(BaseModel):
    """Input for use_{domain} tool."""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: str = Field(..., description="Action: {actions_desc}")
    payload: str | None = Field(
        default=None,
        description="Action-specific data (see help for details)",
    )

{generate_action_validator(actions)}'''


def generate_annotations(has_external_api: bool) -> str:
    """Generate tool annotations dict."""
    return f"""    annotations={{
        "title": "TODO: Tool Title",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": {has_external_api},
    }},"""


def generate_auth_block(auth_method: str) -> str:
    """Generate authentication setup code."""
    if auth_method == "env_var":
        return '''

def _get_credentials() -> str:
    """Get API credentials from environment."""
    import os

    key = os.environ.get("${DOMAIN_UPPER}_API_KEY")
    if not key:
        raise RuntimeError(
            "${DOMAIN_UPPER}_API_KEY not set. "
            "Export it: export ${DOMAIN_UPPER}_API_KEY=your-key-here"
        )
    return key
'''
    if auth_method == "keyring":
        return '''

def _get_credentials() -> str:
    """Get API credentials from OS keychain."""
    import keyring

    key = keyring.get_password("${domain}-mcp", "api_key")
    if not key:
        plugin_dir = Path(__file__).parent.resolve()
        raise RuntimeError(
            "No API key in keychain. Run setup:\\n"
            f"  uv run --directory {plugin_dir} python setup.py"
        )
    return key
'''
    return ""


def generate_server(config: McpConfig) -> str:
    """Generate complete MCP server file."""
    domain = config["domain"]
    actions = config["actions"]
    description = config.get("description", f"{domain.title()} operations")
    auth_method = config.get("auth_method", "none")
    has_external_api = config.get("has_external_api", False)

    actions_desc = "|".join(sorted(set(actions + ["help"])))
    example_action = actions[0] if actions else "list"
    domain_upper = domain.upper()

    auth_block = generate_auth_block(auth_method)
    auth_block = auth_block.replace("${DOMAIN_UPPER}", domain_upper)
    auth_block = auth_block.replace("${domain}", domain)

    model_name = f"{domain.title()}Action"

    # Only include imports that are actually used
    stdlib_imports = []
    if auth_method == "keyring":
        stdlib_imports.append("from pathlib import Path")
    stdlib_block = "\n".join(stdlib_imports)
    if stdlib_block:
        stdlib_block = "\n" + stdlib_block + "\n"

    parts = [
        f'''#!/usr/bin/env python3
"""{domain.title()} MCP Server - {description}.

Single tool with action dispatcher (~500 tokens vs typical 15,000+).
Self-documenting via 'help' action.

Usage with Claude Desktop/Code:
    Add to your MCP config:
    {{
        "mcpServers": {{
            "{domain}-mcp": {{
                "command": "uv",
                "args": ["--directory", "/path/to/{domain}-mcp", "run", "{domain}-mcp"]
            }}
        }}
    }}
"""
{stdlib_block}
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator
''',
        auth_block,
        f'''
mcp = FastMCP("{domain}_mcp")


{generate_pydantic_model(domain, actions)}


# Help documentation - loaded only when needed
{generate_help_topics(domain, actions)}


@mcp.tool(
    name="use_{domain}",
{generate_annotations(has_external_api)}
)
async def use_{domain}(params: {model_name}) -> str:
    """{description}. Actions: {actions_desc}.

    Examples:
      {{action:"help"}} - show available actions
      {{action:"{example_action}", payload:"TODO"}} - {example_action}
    """
    try:
        action = params.action

        # Help - self-documenting
        if action == "help":
            topic = (params.payload or "overview").lower()
            if topic in HELP_TOPICS:
                return HELP_TOPICS[topic]
            return f"Unknown topic '{{topic}}'. Available: {{', '.join(HELP_TOPICS.keys())}}"

{generate_action_handlers(actions)}

        return f"Unknown action '{{action}}'. Try: {{', '.join(sorted(HELP_TOPICS.keys()))}}"

    except Exception as e:
        return f"Error: {{e}}. Try: action=help for usage."


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
''',
    ]

    return "\n".join(parts)


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print(
            "Usage: python3 generate_mcp.py '<json_config>'\n"
            'Example: \'{"domain":"weather","actions":["get","forecast"],'
            '"description":"Weather data","auth_method":"env_var",'
            '"has_external_api":true}\'',
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        config = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    required = ["domain", "actions"]
    missing = [k for k in required if k not in config]
    if missing:
        print(f"Missing required fields: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    if not config["actions"]:
        print("Actions list cannot be empty. Provide at least one action.", file=sys.stderr)
        sys.exit(1)

    output = generate_server(config)
    filename = f"{config['domain']}_mcp.py"
    Path(filename).write_text(output)
    print(json.dumps({"created": filename, "domain": config["domain"]}))


if __name__ == "__main__":
    main()
