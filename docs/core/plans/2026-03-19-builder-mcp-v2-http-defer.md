# Plan: builder-mcp v2 — HTTP transport + discoverability

**Status**: HC approved, FastMCP API verified, implementation phase
**Scope**: builder-mcp skill update
**Depends on**: None (additive, existing stdio path unchanged)

## Problem

builder-mcp v1 generates only stdio transport MCP servers. SKILL.md already asks about transport and defer_loading but subskills and scripts don't implement either.

## Key Research Finding: defer_loading is client-side only

Research (2026-03-19) established that `defer_loading` is **not an MCP protocol feature**. It exists only in the Anthropic Messages API as a client parameter. MCP servers have no control over it:

- Claude Code applies it automatically when MCP tools exceed >10% of context
- Copilot CLI, Codex CLI, Cursor do not support it at all
- FastMCP has no `defer_loading` parameter
- MCP spec `ToolAnnotations` has only 5 fields (readOnly, destructive, idempotent, openWorld, title)

**Consequence**: Drop `defer_loading` from server generation entirely. Instead improve **discoverability** — the server-side levers that help clients find and use tools:
1. `instructions=` parameter on `FastMCP()` — tells client when to use this server's tools
2. Search-optimized tool descriptions — Claude Code finds deferred tools by searching descriptions
3. `validate_mcp.py` checks description quality

## Changes

### 1. `generate_mcp.py` — add `transport` and `instructions`

- Add `transport: str` to `McpConfig` (default "stdio", option "streamable-http")
- Add `instructions: str` to `McpConfig` (optional server-level instructions)
- Generate `FastMCP("{domain}_mcp", instructions="{instructions}")` when provided
- When transport="streamable-http": generate `mcp.run(transport="streamable-http")`

**Verified (2026-03-20):** FastMCP API confirms:
- `FastMCP(name, instructions=...)` ✓
- `mcp.run(transport="streamable-http")` ✓
- HTTP params in `__init__`: `host="127.0.0.1"`, `port=8000`, `streamable_http_path="/mcp"`, `stateless_http=False`, `json_response=False`
- No manual uvicorn/starlette/CORS needed — FastMCP handles internally
- Auth support: `auth_server_provider`, `token_verifier`, `auth` params (out of scope for v2)

### 2. Orthogonal composition: transport overlay on existing subskills

Instead of N subskills for each domain×transport combo, use composition:
- Domain type selects subskill (minimal_mcp.md or with_api.md) — same as v1
- Transport is a parameter passed to `generate_mcp.py` — affects `mcp.run()` call and deps only
- HTTP-specific extras (`.env.example`, optional Dockerfile) handled as post-generation steps in SKILL.md

No new `with_http.md` subskill needed. SKILL.md routing stays simple.

### 3. `generate_pyproject.py` — transport-aware deps

When transport="streamable-http": add `uvicorn>=0.30.0` to dependencies. FastMCP uses uvicorn internally for HTTP.

### 4. `generate_packaging.py` — transport-aware config

- stdio: current `.mcp.json` format (command-based)
- streamable-http: URL-based `.mcp.json` (`"type": "http"`, `"url": "http://localhost:${PORT}/mcp"`)
- README: transport-specific install/run instructions

### 5. `SKILL.md` — simplified routing + transport handling

Step 1 gathers: domain, transport, actions, auth
Step 2 routes by domain type to existing subskills
Step 3 (NEW): if transport=streamable-http, post-generate:
- Generate `.env.example` (HOST, PORT, auth config)
- Optional: ask if Dockerfile needed
Step 4: validate
Step 5: verify

Remove `defer_loading` question from Step 1.

### 6. `validate_mcp.py` — discoverability and HTTP checks

New checks:
- WARN if no `instructions=` on FastMCP (poor discoverability)
- WARN if tool description > 50 words or < 5 words (poor searchability)
- WARN if transport=streamable-http but no health-related code
- **Drop**: HTTP-without-auth FAIL — server auth is a separate concern from upstream API auth (Codex review finding #2). Out of scope for v2.

### 7. `SKILL.md` and docs — remove defer_loading references

- Remove `defer_loading` question from SKILL.md Step 1
- Update CLAUDE.md "Writing MCPs" trigger: remove "Support defer_loading" line
- Update Designing MCP Servers.md section 9.4: clarify this is client-side, not server-side

## Out of Scope (v2)

- MCP server-side auth (OAuth on the MCP endpoint itself) — separate from upstream API auth
- MCP `prompts` and `resources` generation — future v3
- Multi-tool MCP generation — remains single-tool + action dispatcher

## Acceptance Criteria

- [x] `generate_mcp.py '{"domain":"test","actions":["list"]}'` produces same output as v1 (regression)
- [x] `generate_mcp.py '{"domain":"test","actions":["list"],"transport":"streamable-http"}'` produces HTTP server
- [x] `generate_mcp.py '{"domain":"test","actions":["list"],"instructions":"Use for test data"}'` includes instructions in FastMCP init
- [x] `generate_packaging.py` produces URL-based `.mcp.json` for HTTP transport
- [x] `validate_mcp.py` warns on missing instructions and poor descriptions
- [>] Generated HTTP server starts and responds to MCP `initialize` + `list_tools` (integration test) - deferred in this sandbox; `mcp` package is unavailable and network access is blocked
- [>] Existing tests pass - builder-mcp tests pass; wider builder suite still has an unrelated pre-existing failure in `tests/builder-skill/test_validate_structure.py::TestRealSkillFiles::test_skill_builder_passes`

## Files to modify

- `builder-mcp/scripts/generate_mcp.py` — McpConfig, instructions, transport
- `builder-mcp/scripts/generate_pyproject.py` — transport-aware deps
- `builder-mcp/scripts/generate_packaging.py` — transport-aware .mcp.json
- `builder-mcp/scripts/validate_mcp.py` — discoverability + HTTP checks
- `builder-mcp/SKILL.md` — transport handling, remove defer_loading
- `builder-mcp/subskills/minimal_mcp.md` — pass transport param
- `builder-mcp/subskills/with_api.md` — pass transport param
- `CLAUDE.md` — remove defer_loading line from Writing MCPs
- `docs/Designing MCP Servers.md` — clarify section 9.4 is client-side

## Testing

- Unit tests: `tests/builder-mcp/test_generate_mcp.py` (HTTP + instructions cases)
- Integration test: generate HTTP server → start → MCP client `initialize` + `list_tools` + tool call
- Regression: generate stdio server, compare output to v1
- **Pre-implementation experiment**: verify FastMCP `transport="streamable-http"` API works as expected
