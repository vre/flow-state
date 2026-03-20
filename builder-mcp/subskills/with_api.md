# MCP with External API

Extends minimal MCP with an httpx API client. Separates domain logic from MCP protocol.

## Step 1: Generate server

```bash
python3 ./scripts/generate_mcp.py '{"domain":"${DOMAIN}","actions":${ACTIONS_JSON},"description":"${DESCRIPTION}","instructions":"${INSTRUCTIONS}","transport":"${TRANSPORT}","auth_method":"${AUTH_METHOD}","has_external_api":true}'
```

Creates: `${DOMAIN}_mcp.py`

## Step 2: Generate API client

Create `${DOMAIN}_client.py` with httpx:

```python
"""${DOMAIN} API client - domain logic separated from MCP."""

import httpx

API_BASE = "${API_BASE_URL}"

async def ${first_action}(**kwargs) -> dict:
    """TODO: implement."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/endpoint", params=kwargs)
        response.raise_for_status()
        return response.json()
```

One function per action. Pure async. No MCP imports.

## Step 3: Generate pyproject.toml

```bash
python3 ./scripts/generate_pyproject.py '{"domain":"${DOMAIN}","description":"${DESCRIPTION}","transport":"${TRANSPORT}","dependencies":["httpx>=0.27.0"]}'
```

Creates: `pyproject.toml`

## Step 4: Generate packaging

```bash
python3 ./scripts/generate_packaging.py '{"domain":"${DOMAIN}","description":"${DESCRIPTION}","actions":${ACTIONS_JSON},"transport":"${TRANSPORT}"}'
```

Creates: `.mcp.json`, `README.md`

## Step 5: Create project directory

```
${DOMAIN}-mcp/
├── ${DOMAIN}_mcp.py        # MCP server (action dispatcher)
├── ${DOMAIN}_client.py     # API client (domain logic)
├── pyproject.toml
├── .mcp.json
└── README.md
```

## Step 6: Wire client into server

In `${DOMAIN}_mcp.py`, import from `${DOMAIN}_client` and call from action handlers.

Return to parent skill for validation.
