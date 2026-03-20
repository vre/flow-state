# Cycle Reflection: builder-mcp v2 (HTTP transport + discoverability)

## Plan-to-Implementation Translation

Plan translated well after two critical corrections:
1. `defer_loading` removed entirely — research proved it's client-side only (MCP spec has no such field, Claude Code applies it automatically). Plan originally assumed server-side annotation.
2. Orthogonal composition adopted — transport as parameter, not separate subskill. Codex review found the 3×2 routing matrix was unresolvable with the original separate-subskill approach.

FastMCP API verification before implementation confirmed: `FastMCP(name, instructions=...)`, `mcp.run(transport="streamable-http")`, built-in host/port/path handling. This eliminated planned CORS/health/uvicorn manual code generation.

## Review Iterations

- **Self-review** found 4 open questions (overlapping changes, composition model, FastMCP API, routing matrix)
- **Codex review** found 8 issues (2 critical, 4 high, 2 medium). Critical: defer_loading wrong interface, auth model conflation. All integrated into revised plan.
- **defer_loading research** (separate investigation) — surveyed Claude Code, Copilot CLI, Codex CLI, Cursor, FastMCP, MCP spec. Conclusive: 100% client-side.
- **ORC review** of implementation: no blocking issues found. HTTP README and packaging verified correct.

Root causes of review findings: plan was written before researching the actual APIs. The pre-implementation experiment (FastMCP API check) should have been done during planning, not after plan approval.

## Delegation Effectiveness

Codex for review: highly effective. Found auth conflation and defer_loading misunderstanding that would have wasted the implementation.

Codex for implementation: effective for code changes. Known sandbox issue — git commits blocked by worktree `.git` pointing outside writable roots. Manual commit after Codex finished. Ruff autofix needed (3 issues). Same pattern as previous cycles.

Codex `resume` for role change (review → implementation): failed. Codex continued the review instead of switching to implementation. Had to start a new session. Lesson: don't reuse review sessions for implementation — start fresh.

## Process Improvements

- **Research APIs during planning, not after.** The FastMCP API verification and defer_loading research changed the plan fundamentally. If done during planning, the first plan version would have been correct.
- **Don't reuse Codex review sessions for implementation.** The session context is loaded with review findings and critique mode. A fresh session with only the plan produces better implementation.
- **Orthogonal composition > combinatorial subskills.** When two dimensions are independent (domain type × transport), make them parameters, not a matrix of subskills.
