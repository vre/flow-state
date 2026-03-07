# Design Skill Survey

Date: 2026-03-07

## Context

Evaluated whether to build a custom `/design` skill for collaborative UI/UX exploration (propose >2 HTML mockups, iterate with human). Surveyed existing Claude Code design skills on GitHub.

## Findings

### 1. Anthropic Official: `frontend-design`

- Source: `anthropics/claude-code` repo, installable via plugin marketplace
- Focus: distinctive, production-grade frontend — avoid "AI slop" aesthetics
- Approach: bold aesthetic direction first (tone, purpose, differentiation), then implement
- Scope: web components, pages, applications
- Small SKILL.md (~21 lines), philosophy-driven

### 2. `interface-design` (Dammyjay93) — most sophisticated

- Focus: dashboards, admin panels, SaaS apps (explicitly not marketing sites)
- Reference system with 4 files:
  - `principles.md` — surface/token architecture, elevation hierarchy, subtlety principle
  - `critique.md` — "correct vs crafted" design review (composition, spacing, typography, surfaces)
  - `validation.md` — cross-session memory via `.interface-design/system.md`, pattern reuse rules
  - `example.md` — craft examples with reasoning (Vercel/Supabase/Linear as references)
- Slash commands: `/audit`, `/critique`, `/extract`, `/init`, `/status`
- Key insight: maintains design decisions across sessions via memory file

### 3. `ui-ux-pro-max-skill` (nextlevelbuilder)

- Database approach: 100 reasoning rules, 67 UI styles
- Searchable lookup for color palettes, font pairings, chart types, UX guidelines
- More reference tool than design process

### 4. `bencium-marketplace`

- Collection of 6 design plugins including "controlled UX designer"
- 13 skills total across design, architecture, productivity

## Assessment

All surveyed skills focus on **implementation quality** — making built UI look polished and consistent. None address the **collaborative exploration** process (propose multiple mockups, discuss tradeoffs, iterate before committing).

However, the collaborative exploration workflow is already captured in CLAUDE.md discovery rules:
- "Interface change -> propose design exploration, iterate 3-5 designs with HC"
- "Delegate to subagent: create mockups with realistic content"

A separate skill would duplicate what CLAUDE.md already instructs. When flow-state needs UI, Anthropic's official `frontend-design` plugin handles the implementation quality side.

## Decision

Mark `/design` skill as superseded. Use official plugin marketplace when UI work begins.
