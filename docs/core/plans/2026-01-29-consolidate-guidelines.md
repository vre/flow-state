# DONE: Consolidate LLM Agent Documentation

## Problem
We have gathered significant insights (AGENTS.md standardization, MCP evolution, persuasion principles, tool architecture) which are currently scattered in `docs/2026.01.28-gemini3pro-huomiot.md` and `DEVELOPMENT.md`. The core documentation files (`writing-claude-agents-md.md`, `mcp-design-principles.md`, `writing-skills.md`) are outdated or specific to older practices.

## Goal
Update the core documentation to reflect "LLM Agent Guidelines" while preserving legacy compatibility where agreed (e.g. keeping `CLAUDE.md` as secondary).

## Constraints
- **Duplication is Acceptable:** `AGENTS.md` (the concise instruction file) will necessarily duplicate some rules from the detailed "Designing..." documentation (the "why" files). This is intentional.
- **Format:** Plain Markdown only. No complex HTML or non-standard rendering.
- **Source of Truth:** All new content must be derived from `docs/2026.01.28-gemini3pro-huomiot.md`.
- **Scope:** Only touch the files listed in Workplan.

## Acceptance Criteria
- [x] `docs/Designing AGENTS.md.md` exists and covers: AGENTS.md vs CLAUDE.md, Persuasion, Instruction Adherence.
- [x] `docs/Designing MCP Servers.md` exists and covers: Decision Matrix, MCP Apps, Streamable HTTP, Recoverable Errors.
- [x] `docs/Designing Skills.md` exists and covers: Determinism (Script vs Skill), Fail-Fast.
- [x] Original files (`writing-claude-agents-md.md`, etc.) are removed/renamed.
- [x] `DEVELOPMENT.md` links are updated to point to new filenames.

## Content Details & Clarifications

### MCP Apps & Streamable HTTP (2026 Updates)
The `Designing MCP Servers.md` must explain these new capabilities clearly to readers who haven't been in this session:
- **MCP Apps:** Explain that MCP is no longer just text-in/text-out. It now supports interactive UI components (dashboards, forms) within the chat interface. This changes *when* you might choose MCP over a script (e.g., when you need user interaction).
- **Streamable HTTP:** Explain that for high-load or long-running tools, SSE (Server-Sent Events) is being replaced/augmented by Streamable HTTP. This is a technical detail relevant for robust server implementation.
*Context:* These were identified in the Jan 2026 market research as key differentiators for the new MCP version.

## Workplan
- [x] Update `docs/writing-claude-agents-md.md`
  - [x] Rename to `docs/Designing AGENTS.md.md`.
  - [x] Incorporate "AGENTS.md" as primary standard. Keep CLAUDE.md as secondary reference.
  - [x] Add section on Persuasion Principles (Authority, Commitment).
  - [x] Mention "Instruction Adherence" variance across models.
- [x] Update `docs/mcp-design-principles.md`
  - [x] Rename to `docs/Designing MCP Servers.md`.
  - [x] Add "Decision Matrix" (Atomic vs Script vs Compound).
  - [x] Mention MCP Apps & Streamable HTTP (2026 updates).
  - [x] Reinforce "Recoverable Errors".
- [x] Update `docs/writing-skills.md`
  - [x] Rename to `docs/Designing Skills.md`.
  - [x] Refine "Minimize Skill, Maximize Script" with the new insights on determinism.
  - [x] Link to the Decision Matrix in MCP docs.
- [x] Ensure `DEVELOPMENT.md` links to the updated deep-dive docs (Already done in previous step, but verify).

## Implementation Details
1. **Refactor `writing-claude-agents-md.md`**:
   - Shift focus from "Claude" to "Generic LLM Agent".
   - Explicitly define `AGENTS.md` vs `CLAUDE.md` roles.
2. **Refactor `mcp-design-principles.md`**:
   - Integrate the "Evolution Cycle" concept.
3. **Refactor `writing-skills.md`**:
   - Emphasize the "Fail-Fast" and "Explicit Output" patterns.

## Notes
- Working in `.worktrees/creating_documentation/`. which is the current pwd.
- `docs/2026.01.28-gemini3pro-huomiot.md` is the source of truth for new insights.
