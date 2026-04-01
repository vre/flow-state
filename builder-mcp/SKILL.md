---
name: mcp-builder
description: Use when building Python MCP servers. Produces a single-tool action-dispatcher package.
keywords:
  - mcp
  - fastmcp
  - http
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# MCP Builder

Python only. Use repo scripts, not custom templates.

Read `docs/writing-mcp-servers.md` first.

## Step 0: Threshold

- Single CLI command? STOP. Use `curl`, `jq`, or a shell alias.
- Existing tool covers it? STOP. Use `gh`, `git`, `docker`, or `kubectl`.
- One-off data fetch? STOP. Use a script.

## Step 1: Gather

AskUserQuestion:
- question: "What domain does this MCP serve?"
- header: "Domain"
- options:
  A. "API wrapper" - Wraps an external REST/GraphQL API
  B. "Local service" - Interacts with local files, DBs, or system
  C. "Integration" - Bridges two systems

Then ask:
- Domain name
- Transport: `stdio` or `streamable-http`
- Actions
- Auth: `none` | `env_var` | `keyring` | `oauth`
- Server instructions: one sentence on when to use this server

Set `${DOMAIN}`, `${TRANSPORT}`, `${ACTIONS_JSON}`, `${AUTH_METHOD}`, `${INSTRUCTIONS}` from answers.

## Step 2: Generate

- API wrapper → `./subskills/with_api.md`
- Otherwise → `./subskills/minimal_mcp.md`
- Transport is a generator parameter, not a transport-specific subskill.

## Step 3: HTTP extras

If `${TRANSPORT}` is `streamable-http`:
- Create `.env.example` with `HOST=127.0.0.1`, `PORT=8000`, `STREAMABLE_HTTP_PATH=/mcp`
- Add auth env vars if the upstream API needs them
- Ask if a Dockerfile is needed; create it only if requested

Do not add `defer_loading` to server code. It is client-side only. Use `instructions=` and search-optimized descriptions instead.

## Step 4: Validate

```bash
python3 ./scripts/validate_mcp.py "${DOMAIN}_mcp.py"
```

Fix FAIL. Review WARN.

## Step 5: Verify

```bash
cd ${DOMAIN}-mcp && uv sync && uv run ${DOMAIN}-mcp &
```

HTTP default: `http://127.0.0.1:8000/mcp`.
Report created files and validation results.
