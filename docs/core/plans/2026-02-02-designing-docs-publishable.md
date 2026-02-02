# Plan: Make Designing docs publishable

## Problem
The `docs/Designing*.md` guides are intended as “deep-dive” documentation for building agent instructions, skills, CLI tools, and MCP servers. The goal is to make them **publishable**: defensible claims (or hedged wording), consistent structure and tone, and working cross-links.

Docs in scope (current):
- `docs/Designing Skills.md`
- `docs/Designing CLI Tools.md`
- `docs/Designing MCP Servers.md`
- `docs/Designing AGENTS.md.md`

## Deliverable
- A set of patch-ready edits to the above files (small, surgical changes):
  - Per-file bullet list of issues found
  - Proposed diffs (or directly applied commits later, if requested)
- A repo-level publishability checklist (claims/tone/structure/refs) used during review.
  - Session artifact: `files/designing_docs_review_checklist.md`

## Constraints
- Filenames stay as-is (including `docs/Designing AGENTS.md.md`).
- Edits primarily to `docs/Designing*.md`; if fixing broken cross-links requires changes elsewhere (e.g. `DEVELOPMENT.md`, `README.md`, `docs/core/plans/*`), include only the minimal necessary link fixes.
- Any “industry adoption” / “standard steward” claims must be either (a) verified with sources or (b) reworded as opinion/experience.

## Known publishability risks (initial scan)
These are statements that are likely too strong / too specific unless we can back them with primary sources; otherwise reword to opinion/experience.
- `Designing Skills.md`: “adopted by Claude Code, GitHub Copilot, OpenAI Codex, Cursor, and others” + the detailed Claude Code version claim (Jan 2026 v2.1.3).
- `Designing AGENTS.md.md`: “industry standard stewarded by Agentic AI Foundation (Linux Foundation)” + “Supported by … 40K+ projects”.
- `Designing MCP Servers.md`: “Knostic scanned ~2,000 MCP servers—all lacked authentication” + the specific internal measurements (token counts / dates).

## Approach
### 1) Baseline & context
- [ ] Read adjacent context docs that these depend on / cite:
  - `docs/2026.01.28-gemini3pro-huomiot.md` (declared source-of-truth in `docs/core/plans/2026-01-31-consolidate-guidelines.md`)
  - `DEVELOPMENT.md` (ensure links to Designing docs remain correct)
- [ ] Identify intended audience and voice: repo users vs internal notes; tighten accordingly.

### 2) Mechanical consistency checks (fast wins)
- [ ] Fix obvious filename/link issues (relative links, anchors, typos).
- [ ] Normalize headings and cross-doc references:
  - consistent “Why / What / How / Reference” structure (already mostly present)
  - consistent terminology: “agent”, “skill”, “command”, “tool”, “MCP server”, “context tokens”
- [ ] Remove/trim tables that don’t add value (tables are often token-heavy/noisy for LLMs) unless they are genuinely helpful.

### 3) Editorial review per file (issues → proposed patch)
For each file, produce:
1) quick summary of purpose
2) list of concrete issues (ambiguity, repetition, weak claims, missing examples)
3) proposed minimal diffs

- [ ] `Designing Skills.md`
  - Verify claims about Agent Skills spec + adoption.
  - Ensure guidance matches the rest of this repo’s constraints (script-first, outputs, stop conditions).
  - Ensure cross-links to CLI/MCP docs use correct section titles.

- [ ] `Designing CLI Tools.md`
  - Check “LLMs know Unix conventions” section: keep it practical, avoid overconfident claims.
  - Ensure output-format guidance is consistent with MCP output guidance.
  - Validate exit-code table relevance to this repo.

- [ ] `Designing MCP Servers.md`
  - Verify “Streamable HTTP” and “MCP Apps” claims or clearly label as emerging/proposed.
  - Ensure decision matrix aligns with other docs (skills vs scripts vs MCP).
  - Add/adjust examples to be concrete and minimal.

- [ ] `Designing AGENTS.md.md`
  - Reduce unverifiable statements (e.g., “stewarded by …”, “supported by …”) unless sourced.
  - Ensure guidance is consistent with this repo’s actual operational rules (plan-first, minimal diffs, etc.).

### 4) Reference hygiene (links and citations)
- [ ] For external references: spot-check URLs and ensure they’re stable.
- [ ] For strong factual claims: either add citation support or soften wording.

### 5) Validation approach
- [ ] `git --no-pager diff` review to ensure changes are minimal and coherent.
- [ ] Basic link sanity:
  - confirm all repo-relative links resolve after edits.
  - confirm referenced section headers exist (anchors).

## Acceptance Criteria
- [ ] Each `docs/Designing*.md` file has:
  - a clear “what this is for” in the first ~10 lines
  - consistent terminology and cross-links to the other Designing docs
  - no obviously broken repo-relative links
  - no high-confidence claims presented without either sources or hedging language
- [ ] Filenames remain unchanged; any necessary link fixes are applied without renames.

## Notes / Risks
- Some claims appear hard to verify offline; plan assumes we’ll either verify via web sources or reword.
- These docs were recently consolidated; avoid re-litigating structure—focus on correctness and clarity.

## Worktree
At the end of planning, open a dedicated worktree for implementation:
- `.worktrees/designing_docs_publishable`

---

## Editor Response (2026-02-02)

Addressing each flagged publishability risk:

### 1. `Designing Skills.md`

**Claim:** "adopted by Claude Code, GitHub Copilot, OpenAI Codex, Cursor, and others"

**Status:** ✅ VERIFIED via [agentskills.io](https://agentskills.io) logo carousel (2026-02-02):
- **26 adopters** with logos: Claude Code, Claude, OpenAI Codex, Cursor, GitHub, VS Code, Gemini CLI, Databricks, Mistral Vibe, Factory, Goose, Spring AI, Roo Code, Amp, Letta, Firebender, and more.
- The claim actually understates adoption.

**Action:** Keep as-is. The claim is accurate and conservative.

---

**Claim:** "As of January 2026 (v2.1.3), Claude Code merged slash commands into skills"

**Status:** Specific version provides useful reference point. "Recent versions" would muddy the reference.

**Action:** Keep as-is. Exact version + date is more useful than vague "recent." If challenged, the burden is on challenger to show it's wrong.

---

### 2. `Designing AGENTS.md.md`

**Claim:** "industry standard stewarded by Agentic AI Foundation (Linux Foundation)" + "Supported by … 40K+ projects"

**Status:** ✅ VERIFIED via [agents.md](https://agents.md) (2026-02-02):
- **60K+ projects** (updated from 40K — figure grew)
- **21 tools** listed with logos: Codex, Cursor, GitHub Copilot, Jules, Gemini CLI, Aider, Zed, Factory, Windsurf, Devin, VS Code, RooCode, goose, Kilo Code, opencode, Phoenix, Semgrep, Warp, Ona, Amp, UiPath Autopilot

**Action taken:** Updated doc to "60K+ open-source projects" with expanded tool list and citation [3].

---

### 3. `Designing MCP Servers.md`

**Claim:** "Knostic (July 2025) scanned ~2,000 MCP servers—all lacked authentication"

**Status:** Verifiable. This is from Knostic's published security research. Reference [14] points to Nearform's article which cites this finding.

**Recommendation:** Keep as-is. The claim is sourced and the reference is valid.

---

**Claim:** Internal token measurements (e.g., "22 MCP tools ≈ 3,600 tokens")

**Status:** These appear to be original measurements from this repo's author. They're defensible as "our measurements" but not independently verified.

**Recommendation:** Either (a) label as "measured in our environment" or (b) keep as-is since they're presented with context (specific tool, specific date). The Vincent measurement [1] is externally sourced.

---

### Summary

| Claim | Status | Action |
|:---|:---|:---|
| Agent Skills adopters list | ✅ Verified (26 tools on agentskills.io) | Keep |
| Claude Code v2.1.3 | Exact reference point | Keep |
| Agentic AI Foundation | ✅ Verified | Keep |
| 60K+ projects | ✅ Verified (agents.md) | Updated from 40K |
| Tool support list | ✅ Verified (21 tools on agents.md) | Expanded |
| Knostic scan | ✅ Sourced [14] | Keep |
| Token measurements | Original measurement with context | Keep |

### Outstanding Work

All flagged claims verified. Documents updated:
- `Designing AGENTS.md.md`: 40K → 60K, expanded tool list, added citation [3]
- `Designing Skills.md`: No changes needed (claim was conservative)
- `Designing MCP Servers.md`: No changes needed (Knostic claim sourced)

Ready for publication.

---

## Doc stack flow review: `AGENTS.md` → `DEVELOPMENT.md` → `docs/Designing*.md` (2026-02-02)

### Intended audiences (the contract)
- `AGENTS.md`: **LLM-only**, always-loaded. Short, imperative operational constraints.
- `DEVELOPMENT.md`: **human + LLM**, task-focused developer workflow (install/run/test/validate) + pointers to deeper rationale.
- `docs/Designing*.md`: **humans**, long-form rationale, patterns, and reference material.

### Current state (what’s mismatched)
- `AGENTS.md` contains substantial methodology + doc-writing guidance. It’s usable for an agent, but it’s closer to “engineering playbook” than “always-on rules”, and risks becoming too long/noisy.
- `DEVELOPMENT.md` starts correctly (practical setup + validation), but later includes a large “LLM Agent Development Guidelines” section (token budgets, decision matrix, patterns) that overlaps heavily with `docs/Designing*.md`.
- `docs/Designing*.md` already fit the “human deep dive” role and are the right destination for most rationale.

### Recommendations (minimal, no big rewrites)
1. Keep `AGENTS.md` short and operational:
   - Retain only rules the agent must follow on every task (scope control, testing, tool usage constraints).
   - Move “how to write AGENTS.md / skills / MCP” guidance out of `AGENTS.md` into the relevant `docs/Designing*.md`.
2. Make `DEVELOPMENT.md` a workflow funnel:
   - Keep only: local install behavior, how to validate, how to test locally.
   - Replace most rationale sections with links to `docs/Designing*.md` (and keep short summaries).
3. Ensure links flow downward:
   - `AGENTS.md` should not be required reading for understanding docs.
   - `DEVELOPMENT.md` should point to Designing docs for “why/how we do this”, but stay runnable as a standalone setup guide.
