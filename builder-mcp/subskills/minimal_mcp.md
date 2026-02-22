# Minimal MCP (stdio, single-tool)

Generates a basic MCP server with action dispatcher. No external API client.

## Step 1: Generate server

```bash
python3 ./scripts/generate_mcp.py '{"domain":"${DOMAIN}","actions":${ACTIONS_JSON},"description":"${DESCRIPTION}","auth_method":"${AUTH_METHOD}","has_external_api":false}'
```

Creates: `${DOMAIN}_mcp.py`

## Step 2: Generate pyproject.toml

```bash
python3 ./scripts/generate_pyproject.py '{"domain":"${DOMAIN}","description":"${DESCRIPTION}"}'
```

Creates: `pyproject.toml`

## Step 3: Generate packaging

```bash
python3 ./scripts/generate_packaging.py '{"domain":"${DOMAIN}","description":"${DESCRIPTION}","actions":${ACTIONS_JSON}}'
```

Creates: `.mcp.json`, `README.md`

## Step 4: Create project directory

Move generated files into `${DOMAIN}-mcp/` directory:

```
${DOMAIN}-mcp/
├── ${DOMAIN}_mcp.py
├── pyproject.toml
├── .mcp.json
└── README.md
```

## Step 5: Fill in TODOs

Open `${DOMAIN}_mcp.py` and implement:
1. Each action handler (replace TODO comments)
2. Help topics (replace TODO descriptions)
3. Tool title annotation

Return to parent skill for validation.
