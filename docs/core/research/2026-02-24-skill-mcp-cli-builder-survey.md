# Survey: Skill, MCP & CLI Builder Tools

**Date:** 2026-02-24
**Scope:** GitHub + Reddit, frameworks, scaffolders, registries, testing, observability

---

## Executive Summary

FastMCP (23k stars) dominates MCP server building. Scaffolders exist but are fragmented and low-adoption. No scaffolder produces single-tool action routing by default. The official MCP Registry is emerging. Skill ecosystems are growing fast with SKILL.md becoming cross-platform (Claude Code + Codex CLI + ChatGPT). No unified "create skill" CLI exists.

---

## 1. MCP Server Frameworks

### FastMCP (Python) -- jlowin/fastmcp (23,100 stars)
- **URL:** https://github.com/jlowin/fastmcp
- **Language:** Python 3.10+
- Decorator-based API. ~1M daily downloads, ~70% of MCP servers. v3.0.2 (Feb 2026). Incorporated into official MCP Python SDK. Now includes client, Apps (interactive UIs).
- **Verdict:** The standard for Python MCP development.

### FastMCP (TypeScript) -- punkpeye/fastmcp (3,000 stars)
- **URL:** https://github.com/punkpeye/fastmcp
- Session management, auth, HTTP streaming + SSE, edge runtime support (Cloudflare Workers, Deno Deploy), stateless mode.

### Official MCP SDKs
- **TypeScript:** https://github.com/modelcontextprotocol/typescript-sdk
- **Python:** https://github.com/modelcontextprotocol/python-sdk (includes FastMCP 1.0)

---

## 2. MCP Server Scaffolders

| Project | Stars | Lang | What |
|---|---|---|---|
| agentailor/create-mcp-server | 8 | TS | `npx` scaffolder, framework choice (SDK/FastMCP), OAuth support. v0.5.3 Feb 2026 |
| mcpdotdirect/template-mcp-server | -- | TS | Simpler `npx` scaffolder, FastMCP-based |
| vlyl/mcpc | 7 | Rust | Dual-language scaffolder (TS or Python) |
| GongRzhe/MCP-Server-Creator | 37 | Py | Meta-MCP: LLM describes → code generated |
| Epi-1120/create-mcp-server-kit | -- | -- | "Production-ready MCP server in seconds" |

**Gap:** No scaffolder produces single-tool action routing. All generate multi-tool patterns.

---

## 3. Meta-MCPs and Orchestrators

### MetaMCP -- metatool-ai/metamcp (2,000 stars)
- **URL:** https://github.com/metatool-ai/metamcp
- Aggregates multiple MCP servers. Namespace grouping, tool curation, middleware for observability/security, rate limiting. Production-ready.

### Magg -- sitbon/magg (130 stars)
- **URL:** https://github.com/sitbon/magg
- LLMs autonomously discover, install, and orchestrate MCP servers at runtime. "Package manager for LLM tools."

---

## 4. MCP Testing & Validation

| Tool | Stars | What |
|---|---|---|
| MCP Inspector (official) | 8,800 | React web UI + Node.js proxy. Interactive testing. Protocol validation. CI mode. Essential. |
| MCPLint | 2 | Rust. 56 validation rules, 20+ security rules, coverage fuzzing, SARIF/JUnit output |
| Janix-ai/mcp-validator | 35 | Python. Compliance test suite for MCP spec 2025-06-18 |
| RHEcosystemAppEng/mcp-validation | -- | Red Hat's validation + security analysis |

**Gap:** No pytest-mcp or jest-mcp plugin pattern exists. CI/CD integration immature.

---

## 5. MCP Observability

### MCPcat (92 stars TS SDK, 45 Python)
- **URL:** https://mcpcat.io
- Only dedicated MCP observability platform. User session replay, trace debugging, OpenTelemetry/Datadog/Sentry integration.

---

## 6. Registries & Marketplaces

| Registry | Type | Notes |
|---|---|---|
| GitHub MCP Registry (official) | Server registry | API frozen v0.1 since Oct 2025. One-click VS Code install |
| Docker MCP Registry | Container-focused | |
| mcp.run | WASM hosting + marketplace | OpenAPI-to-MCP generation |
| awesome-claude-skills | 7,600 stars | Best single skill resource |
| agent-skills (tech-leads-club) | 1,500 stars | Security-first. Cross-agent (Claude, Cursor, Copilot, etc.) |
| CCPI (jeremylongshore) | 1,400 stars | 270+ plugins, 739 skills. CLI for search/install |
| SkillsMP.com | Web marketplace | Aggregates from GitHub. Supports SKILL.md standard |
| aiskillstore/marketplace | Security-audited | Skills failing security not published |

---

## 7. Claude Code CLI Enhancers

| Tool | Stars | What |
|---|---|---|
| CCPM (kaldown) | 36 | Rust TUI (lazygit-style) for managing plugins. Vim keybindings |
| MCP Hub (ravitemer) | 374 | Central coordinator, web UI, Neovim plugin (mcphub.nvim: 1,600 stars) |

---

## 8. What Exists vs What's Missing

### Solved
- MCP server building (FastMCP)
- MCP aggregation/gateway (MetaMCP)
- Official registry (GitHub MCP Registry)
- Skill/plugin ecosystem (SKILL.md cross-platform)

### Missing
1. No unified `create-claude-skill` CLI
2. MCP testing in CI/CD immature (no pytest-mcp)
3. Skill quality/security unsolved (13% vulnerability rate per tech-leads-club)
4. No standard MCP project structure
5. Observability nascent (MCPcat only)
6. OpenAPI-to-MCP generation scarce outside mcp.run
