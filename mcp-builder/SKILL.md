---
name: mcp-builder
description: Use when building MCP servers to integrate external APIs or services. Produces a complete Python MCP server package with single-tool action dispatcher.
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# MCP Builder

Python only. stdio transport only. Single tool + action dispatcher default. Do not create your own templates.

## Step 0: Threshold check

Before building, verify MCP is warranted:
- Single CLI command? → "Could be: `curl ... | jq` or a shell alias"
- Existing tool covers it? → "Could be: `gh`, `git`, `docker`, `kubectl`"
- One-off data fetch? → "Could be: an ad-hoc script"

If unclear, ask user. If CLI suffices: `STOP`.

## Step 1: Gather requirements

AskUserQuestion:
- question: "What domain does this MCP serve?"
- header: "Domain"
- options:
  A. "API wrapper" - Wraps an external REST/GraphQL API
  B. "Local service" - Interacts with local files, DBs, or system
  C. "Integration" - Bridges two systems

Then ask:
- Domain name (e.g., "weather", "calendar", "jira")
- What actions? (list, get, create, update, delete, search, etc.)
- Auth method? (none, env_var, keyring)

Set `${DOMAIN}` from answers.

## Step 2: Generate

If answer was A (API wrapper): Read and follow `./subskills/with_api.md`

Otherwise: Read and follow `./subskills/minimal_mcp.md`

## Step 3: Validate

```bash
python3 ./scripts/validate_mcp.py "${DOMAIN}_mcp.py"
```

If FAIL: fix issues. If WARN: review, fix if appropriate.

## Step 4: Verify

```bash
cd ${DOMAIN}-mcp && uv sync && uv run ${DOMAIN}-mcp &
# Should start without error. Kill after verification.
```

Report created files and validation results.
