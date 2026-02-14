#!/usr/bin/env python3
"""Generate pyproject.toml for an MCP server.

Usage:
    python3 generate_pyproject.py '{"domain":"weather","description":"Weather data","version":"0.1.0","dependencies":["httpx"]}'

Output: writes pyproject.toml to current directory.
"""

import json
import sys
from pathlib import Path


def generate_pyproject(config: dict) -> str:
    """Generate pyproject.toml content."""
    domain = config["domain"]
    description = config.get("description", f"{domain.title()} MCP server")
    version = config.get("version", "0.1.0")
    extra_deps = config.get("dependencies", [])

    # Core MCP deps always included
    deps = [
        '"mcp>=1.0.0"',
        '"pydantic>=2.0.0"',
    ]
    for dep in extra_deps:
        deps.append(f'"{dep}"')

    deps_str = ",\n    ".join(deps)
    module_name = domain.replace("-", "_")
    entry_point = domain

    return f'''[project]
name = "{domain}-mcp"
version = "{version}"
description = "{description}"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    {deps_str},
]

[project.scripts]
{entry_point}-mcp = "{module_name}_mcp:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=9.0.2",
]
'''


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) != 2:
        print(
            'Usage: python3 generate_pyproject.py \'<json_config>\'\nExample: \'{"domain":"weather","description":"Weather data"}\'',
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

    output = generate_pyproject(config)
    Path("pyproject.toml").write_text(output)
    print(json.dumps({"created": "pyproject.toml", "domain": config["domain"]}))


if __name__ == "__main__":
    main()
