# Plan Template Survey

Date: 2026-03-07

## Context

Derived plan templates from 77 real plans across 3 own projects + 8 external GitHub projects. Goal: codify organic patterns into lightweight guidance without over-engineering.

## Sources Analyzed

### Own Projects (77 plans total)

**Project A — Claude Code plugin monorepo** (48 plans, Jan–Mar 2026):
- Small (36–80 lines): Goal → Tasks → AC
- Medium (80–300 lines): + Design, Validation Approach, Risks
- Large (300–545 lines): + Anti-Success Criteria, Scope Boundaries, Post-Integration findings
- AC placement: after Tasks
- Evolution: early plans minimal, recent plans include Reflection, status markers, file paths

**Project B — full-stack MCP server** (26 plans, Feb 2026):
- Consistent pattern: Intent → Context → AC → Constraints → Tasks → Files Changed → Reflection
- AC placement: before Tasks (contract-first)
- Unique: "Files Changed" with line numbers always present, "Situational Context" replaces generic Background, "Open Questions" for unresolved HC decisions
- "Out of Scope (v2+)" prevents scope creep

**Project C — Android app** (3 plans, Mar 2026 — most mature):
- Pattern: Intent → Goal → Constraints → Current/Target Architecture → AC (BDD/Gherkin) → Testing Strategy → Out of Scope → Tasks → Reflection
- AC placement: before Tasks, after Architecture
- BDD scenarios (Given/When/Then) inside each AC
- "Current Architecture" + "Target Architecture" side-by-side for refactors
- Explicit UI mockup references

### External Projects (8 surveyed)

| Project | Key Pattern | Worth Adopting |
|---|---|---|
| OpenAI Codex ExecPlan | Fully self-contained prose, living document | Already in CLAUDE.md |
| planning-with-files | 3-file split (plan/progress/findings), 2-Action Rule | Overkill for us |
| codex-playbook | Different policies per task type (bug/feature/refactor) | Interesting — not yet |
| devin.cursorrules | Persistent "Lessons" error memory across tasks | Gap in our process |
| Bhartendu rules_template | Multi-attempt reasoning loop before committing | Partially in discovery |
| sammcj/agentic-coding | MVP-first, anti-sycophancy rules | Already in CLAUDE.md |
| pedrohcgs workflow | Quality scoring (80/100 threshold), `[LEARN]` tags | Too academic |
| APM framework | Role-based agents, session handoff | Already in our ORC/IMP model |

Sources:
- [OpenAI Codex ExecPlan](https://github.com/openai/openai-cookbook/blob/main/articles/codex_exec_plans.md)
- [planning-with-files](https://github.com/OthmanAdi/planning-with-files)
- [codex-playbook](https://github.com/an1creator/codex-playbook)
- [devin.cursorrules](https://github.com/grapeot/devin.cursorrules)
- [Bhartendu rules_template](https://github.com/Bhartendu-Kumar/rules_template)
- [sammcj/agentic-coding](https://github.com/sammcj/agentic-coding)
- [pedrohcgs workflow](https://github.com/pedrohcgs/claude-code-my-workflow)
- [APM framework](https://github.com/sdi2200262/agentic-project-management)

## Key Findings

### 1. AC Placement: Before or After Tasks?

**Before tasks works when** design/architecture is written first — AC is informed by what's possible. Projects B and C both do this successfully.

**After tasks fails because** it allows tasks to drive scope rather than the contract driving tasks.

**Recommendation:** AC after Design, before Tasks. Design informs what can be promised; tasks fulfill the promise.

### 2. Section Order Consensus

Cross-project pattern that emerged from all three own projects:

```
Intent/Problem → Goal → [Situational Context] → [Constraints] → [Design/Architecture] →
Acceptance Criteria → [Testing Strategy] → [Out of Scope] → Tasks → [Files Changed] →
[Reflection]
```

Brackets = optional based on plan size.

### 3. Size Categories

| Category | Lines | Typical Use | Required Sections |
|---|---|---|---|
| Small | <80 | Bugfix, config change, small refactor | Problem, Goal, AC, Tasks |
| Standard | 80–300 | Feature, integration, pipeline change | + Context, Constraints, Design, Testing Strategy, Out of Scope |
| Large | 300+ | New plugin, architecture change | + Current/Target Arch, Files Changed, Open Questions, Risks |

### 4. Status Markers (consistent across all projects)

- `[x]` done
- `[ ]` pending
- `[/]` in progress
- `[>]` deferred — why
- `[+]` discovered and done
- `[-]` cancelled — why

### 5. Identified Gaps

**Cumulative error memory:** Reflections are written but never read in subsequent plans. devin.cursorrules solves this with a persistent "Lessons" section. Our reflections accumulate in `docs/*/reflections/` but there's no mechanism to surface them during planning.

**Task-type routing:** All plans use the same structure regardless of whether it's a bugfix or a new plugin. codex-playbook routes different task types to different policies. Not critical yet — size categories handle most variation.

## Decision

Write 2 lightweight templates (small + standard) based on the consensus order. Reference from CLAUDE.md planning rules. Do not enforce — guide.
