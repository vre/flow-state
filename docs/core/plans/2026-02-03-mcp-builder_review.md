# Review: 2026-02-03-mcp-builder.md

## Summary
This plan matches `docs/Designing MCP Servers.md` well: token economics, single-tool + action dispatcher default, help action, fail-helpfully, and transport selection. Remaining gaps are mainly (1) measurable enforcement for the “startup token budget”, and (2) reducing v1 scope creep (dual transport / multi-tool path).

## Alignment with AGENTS.md
- ✅ Clear constraints + acceptance criteria.
- ✅ Has a validation approach.
- ⚠️ Some requirements are stated as “MUST” without a measurement method (startup token budget).

## What’s solid
- Tool count thresholds (1 default, 2 ok, 3–4 warn, 5+ fail) are concrete.
- Help action as progressive disclosure avoids schema bloat.
- Fail-helpfully + Postel inputs are correct for LLM consumers.
- Transport matrix matches `docs/Designing MCP Servers.md`.

## Must-fix / clarify
1. **“<500 token startup cost” is currently not measurable**
   - You can’t reliably measure “Claude startup tokens” from the server side.
   - Convert to enforceable proxies:
     - tool count (already),
     - tool description word count (already),
     - schema size checks (max properties / enum lengths),
     - a documented heuristic estimate (and treat it as an estimate).

2. **SDK/framework specificity**
   - The plan is now mostly “FastMCP + Python”. Keep that consistent in generated templates and wording; referencing MCP SDK in “Sources” is fine, but the generated code should pick one primary stack.

3. **Dual transport (“both local and remote”) needs a concrete story**
   - Dual transport can explode scope; define whether v1 generates two entrypoints/configs or whether dual is deferred.

4. **Error contract**
   - “Every error MUST suggest a fix” is good, but define a minimal pattern:
     - always include `suggestion` in JSON errors or a `Try:` line,
     - never dump stack traces to stdout.

## Should-fix / improvements
- Add an explicit “untrusted content” handling rule for MCPs that ingest external text (the design doc includes it; plan currently only references it indirectly).
- Add deterministic validation checks in addition to subagent review:
  - reject `print(` to stdout for stdio transport,
  - ensure logs go to stderr,
  - ensure help action exists,
  - ensure annotations exist,
  - ensure action dispatcher uses an allowlist.

## Scope control suggestion (v1)
v1 that actually ships:
- stdio only + single tool + action dispatcher + help action + annotations + fail-helpfully.
- streamable-http + Dockerfile + multi-tool variants as later phases.
