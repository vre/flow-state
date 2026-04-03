---
name: cli-tool-builder
description: Use when creating CLI tools with action dispatcher pattern
keywords: cli, tool, generator, scaffold, argparse
allowed-tools:
  - Bash
  - Read
  - Write
---

# CLI Tool Builder

## Workflow

1. **Gate**: If <50 lines needed, write directly instead
2. **Discover**: What problem, who uses it, 3-5 core operations
3. **Scaffold**:
   - With project-builder: invoke it first (`python3 ./project-builder/project_builder/build_project.py cli ${NAME} <dir>`), then run generate_cli.py on top
   - Standalone: `python3 ./scripts/generate_cli.py --name ${NAME} --operations '${OPS_JSON}' --output ${DIR}`
   - Embedded (inside skill): add `--flat` flag. Creates single .py file, no package, no tests.
4. **Implement**: User fills in action logic. Tests fail until implemented (TDD).
5. **Validate**: `python3 ./scripts/validate_tool.py ${DIR}/${NAME}`

## What Gets Generated

```
${NAME}/
├── ${NAME}.py        # Core: Result type, ACTIONS dict, dispatch()
├── cli.py            # Entry: argparse, --format, --quiet, --yes, TTY detection
├── pyproject.toml    # Entry points, optional [mcp] extra
└── tests/
    ├── test_core.py  # Per-action failing stubs
    └── test_cli.py   # Exit codes, format, help
```

With `--flat`:
```
${DIR}/${NAME}.py    # All-in-one: Result, actions, dispatch, argparse
```

## Constraints

- Python 3.10+, stdlib only (no click/typer/rich)
- POSIX: `-v` `-q` `--format json|table` `--yes`
- Exit codes: 0=ok, 1=error, 2=usage, 3=not found, 4=permission, 5=network
- Errors suggest fix: `"Unknown 'x'. Valid: list, get, help"`
- See: `./references/writing-cli-tools.md`

## Stop

- MCP-only (no CLI): use `mcp-builder` instead
- One-liner: write directly, skip this skill
