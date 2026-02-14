# Review: 2026-02-03-cli-builder-skill.md

## Summary
The core idea (one Python codebase that can run as a human-friendly CLI *and* expose the same action dispatcher as an MCP server) is coherent and aligns with `docs/Designing CLI Tools.md` + `docs/Designing MCP Servers.md`. The plan got broader (security patterns, per-action test generation, MCP transport tests, templating), so v1 scope boundaries matter more now.

## Alignment with AGENTS.md
- ✅ Clear constraints and concrete acceptance criteria.
- ⚠️ Naming convention conflict: AGENTS.md prefers gerunds, plan chooses `cli-tool-builder` (builder noun). Decide and make consistent across the repo.
- ⚠️ Several “MUST” items need an enforcement mechanism (stdlib-only in CLI mode, dependency minimalism, stdout/stderr rules).

## What’s solid
- TTY auto-format and `--format` support match the CLI design doc.
- Exit codes 0–5 are explicit and script-friendly.
- Shared action dispatcher for CLI + MCP is the right architecture.
- Security additions (stdout/stderr separation, path validation, destructive `--yes`, credential hygiene) are directionally correct.

## Must-fix / clarify
1. **Pick the MCP framework + dependency story (currently inconsistent)**
   - Plan text says “FastMCP wrapper” but the dependency list says `mcp` (official SDK).
   - Decide one primary stack:
     - A) FastMCP (then dependency is `fastmcp`, and examples should import that), or
     - B) MCP Python SDK directly (then remove “FastMCP wrapper” wording).

2. **“CLI-only mode is stdlib only” conflicts with always-on MCP deps**
   - Fix via packaging separation:
     - base install: stdlib-only,
     - optional extra: `.[mcp]` that installs MCP deps,
     - lazy-import MCP modules and fail helpfully if user runs `--mcp` without the extra.

3. **`--mcp` via `"--mcp" in sys.argv` is brittle (and you already want argparse)**
   - It bypasses arg validation and makes help/usage confusing.
   - Prefer either:
     - separate entrypoint only (`mytool-mcp`), or
     - an argparse subcommand (`mytool mcp`), or
     - a real argparse flag that’s parsed normally.

4. **Jinja2 templates are an undeclared dependency**
   - You list “minimal deps” but the directory structure uses `*.jinja` templates.
   - Either justify + declare `jinja2`, or switch to stdlib templating (string.Template / f-strings) to keep deps minimal.

5. **Command whitelisting is a niche feature; don’t bake it into every generated CLI**
   - `ALLOWED_COMMANDS` patterns are relevant if the tool *wraps external CLIs*.
   - For normal “API client / data processor” tools, default should be “no arbitrary subprocess execution”. Make the wrapper security helpers conditional.

## Should-fix / improvements
- “Security warning comments in generated code” risks comment bloat; prefer short, targeted comments + actual safeguards.
- MCP transport testing (“validate JSON-RPC stream”) is high effort and flaky; consider v1 as static checks (no stdout prints, logging to stderr) + a minimal smoke test.
- Scope boundary with `mcp-builder`: either reuse it (subskill) or explicitly state this skill owns only the thin MCP wrapper.
- Add a “doesn’t need a CLI” gate (like your other plans): one-liner transforms shouldn’t become a project scaffold.

## Minimal v1 suggestion
Ship v1 as:
- generator: core + cli + tests for core,
- optional `add_mcp_mode.py` behind optional dependency,
- `validate_tool.py` enforcing: exit codes, TTY defaulting, fail-helpfully errors, and “no stdout pollution” in MCP mode.
