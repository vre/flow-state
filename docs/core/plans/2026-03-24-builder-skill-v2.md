# Builder-skill v2: iterative development loop, editing, portable docs

## Intent

Builder-skill produces structurally valid but content-weak skills. No editing flow exists. No iterative test loop. Docs don't travel with the installed skill. Subagent decisions are ad-hoc.

You can't "program" an LLM skill the way you program software. Skill development is: hypothesis → trial → observe → adjust → repeat. Builder should support this loop, not try to catch every issue with deterministic validation.

## Goal

Builder-skill supports iterative skill development: create → test → observe → refine. Handles both new and existing skills. Docs travel with the skill. Subagent use is deliberate and justified.

## Situational Context

Current builder-skill:
- SKILL.md (37 lines) — dispatcher to skill_only.md or builder_skill.md
- skill_only.md — 5-step flow: Gather → Generate → Enhance → Validate → Semantic Check
- builder_skill.md — 7-step flow: adds Tests, Implement, Smoke Test
- validate_structure.py — structural checks (frontmatter, tokens, naming, paths, prose)
- generate_skill.py — minimal skeleton generator (bypassed by all 3 test runs)
- scenarios/ — hypothesis-driven test framework with 1 scenario

Key docs the builder relies on:
- docs/writing-skills.md — LLM guide, referenced as `docs/writing-skills.md` (breaks when skill is installed elsewhere)
- docs/Designing Skills.md — deep rationale (same problem)

Patterns learned this session (not yet in builder):
- Explicit Steps over prohibitions for subagent prompts
- Background agent graceful degradation (Permission Test → Mode A/B)
- Constrained subagent output ("Do not output text — only make tool calls")
- Warmup Write for permission pre-approval
- Skill = iterative, not waterfall

## Constraints

- Builder skill itself must stay under 500 tokens
- Subskills under practical limits (current 2000 char cap is too low for real skills)
- validate_structure.py must remain backward-compatible (existing skills pass)
- Docs must be accessible both from builder-skill install location and from docs/

## Design

### Core change: iterative development loop

Current flow is waterfall: Gather → Generate → Enhance → Validate → Done.

New flow is iterative:

```
1. Gather requirements (what, when, outputs)
2. Generate 3 skill variants in parallel (subagents, different perspectives)
3. Test all 3 with real input (claude -p)
4. Compare: what worked, what didn't, what was surprising
   - 3 fail at same point = real problem in the brief
   - 1 fails = approach-specific issue
   - Best parts from each → combine into one
5. Refine combined skill, minimize bloat
6. Test → observe → refine (iterate 5-6 until done)
7. Validate structure (final gate)
```

Why 3 variants: LLM's first idea is the average — the most probable response. Same brief repeated 3 times produces near-identical output. Variance comes from different perspectives:

**Strategy A — Solution space:** "Design 3 different approaches to solve this" → different architectures, flow structures, subagent divisions. Explores the design space.

**Strategy B — Surprise gradient:** "Design 3 solutions at levels will/should/might":
- **will** — known to work, conventional approach
- **should** — likely works, less obvious approach
- **might** — unconventional, challenges assumptions

The might-level forces the LLM off its probability peak — it may find solutions that would never emerge from a single attempt. Orchestrator (Opus/Sonnet) evaluates and combines.

The Enhance step (current Step 3) tried to get everything right upfront by applying all writing-skills.md principles at once. This doesn't work — you can't predict subagent behavior from instructions alone. You have to try it.

### Portable docs

Move `docs/writing-skills.md` and `docs/Designing Skills.md` into the builder-skill folder. Symlink from docs/ for backward compatibility using relative paths. Keep original filenames to avoid breaking references across the repo.

```
builder-skill/
├── SKILL.md
├── references/
│   ├── writing-skills.md          ← source of truth
│   └── Designing Skills.md        ← source of truth
├── subskills/
├── scripts/
└── scenarios/

docs/
├── writing-skills.md              ← symlink → ../builder-skill/references/writing-skills.md
└── Designing Skills.md            ← symlink → ../builder-skill/references/Designing Skills.md
```

Relative symlinks work in git. SKILL.md Step 0 changes to `Read "./references/writing-skills.md"`.

Renaming `Designing *.md` → `designing-*.md` is desirable but requires repo-wide reference updates (CLAUDE.md, DEVELOPMENT.md, builder-cli-tool, etc.). Deferred to a separate cleanup task — not in scope here.

### Three modes: Create, Edit, Validate

```
Step 2: Route
- New skill → ./subskills/skill_only.md
- Builder skill (scripts/templates/tests) → ./subskills/builder_skill.md
- Edit/improve existing skill → ./subskills/edit_skill.md     ← NEW
- Validate existing skill → Step 3 directly                    ← shortcut
- Bottling session → Document, then skill_only.md
- From historian → Needs mcp tools
```

### Edit flow (edit_skill.md)

```
1. Read entire skill: SKILL.md + all subskills + scripts inventory
2. Understand the change request — what is the goal?
3. Define done-condition: "This change is complete when ___"
4. Define constraints: what must NOT break (existing flows, coherence, token budget)
5. Apply changes — integrate into existing structure, don't append
6. Test: run changed skill via claude -p with real input
7. Observe: did it achieve the goal? Did constraints hold?
8. Refine (iterate 5-7 until done-condition met)
9. Validate structure (final gate)
```

Key: edit is goal-driven with explicit done-condition and constraints. The orchestrator reads the whole skill first, understands its architecture, then makes changes that fit — not patches bolted on.

### Subagent decisions

Most builder work is straightforward — the orchestrator can do it directly:

| Task | Subagent? | Why |
|------|-----------|-----|
| Structural validation | No — script | Deterministic, fast |
| Semantic check (description trap, missing Creates) | No — orchestrator | Small input (<500 tokens), simple rules |
| Minimize skill | No — orchestrator | Reads skill, removes obvious bloat, writes back |
| Coherence check after edit | No — orchestrator | Cross-reference files, find mismatches |
| Write subagent prompts in new skill | No — orchestrator | Orchestrator has all context |
| Smoke test analysis | No — orchestrator | Reads test output, identifies issues |

Subagents only for:
- **Variant generation** — 3 parallel skill drafts from same brief (core of iterative loop Step 2)
- **Heavy LLM analysis** of large inputs (>5K tokens) that would bloat orchestrator context
- **Parallel independent tasks** that genuinely benefit from concurrent execution

Current semantic check subagent (Step 5) should become direct orchestrator work.

### Content awareness (extend validate_structure.py)

Keep structural validation deterministic. Add targeted content checks that catch the most common problems:

| Check | What | Severity |
|-------|------|----------|
| subagent_has_io | task_tool blocks have INPUT/OUTPUT paths | error |
| subagent_output_constrained | task_tool blocks end with constrained final message format | warning |
| creates_after_bash | bash blocks have Creates: lines | warning |
| background_has_degradation | run_in_background has Permission Test pattern | warning |

Not 8 checks — 4. Add more only when real problems are observed (iterative, not speculative). All 4 checks must be implemented, tested, and referenced in AC5.

### Minimize as part of test loop

Not a separate step or subagent. After each test iteration, the orchestrator asks: "Did anything in the skill not get used? Can I remove it and still pass?" This is part of the observe → refine cycle, not a bolt-on phase.

### Test loop — builder runs the created skill

Builder invokes the created skill via `claude -p` to test it with real input. This is not a separate smoke test step — it's the core of the iterative loop.

```
claude -p "invoke ${SKILL_NAME} with: <minimal real input>" --allowedTools '...'
```

Builder reads the output and evaluates:
- Did all expected files get created?
- Were there unexpected permission prompts?
- Did any subagent fail or improvise (python3 -c, inline scripts)?
- Was context compacted (sign of bloat)?
- Did the skill achieve its goal?

If problems: refine skill and test again. If clean: validate structure and done.

A skill is just instructions the LLM loads — there's no barrier to a skill invoking another skill for testing.

**Test harness:** For `claude -p` to find the created skill, it must be loadable. Two approaches:
1. **Symlink into `.claude/skills/`** — `ln -s ${SKILL_DIR} .claude/skills/${SKILL_NAME}` before test, remove after
2. **Prompt-inline** — paste SKILL.md content into the test prompt (current scenario approach, works without installation)

Builder uses approach 1 for smoke tests (tests real skill loading) and approach 2 for scenario regression tests (no side effects).

### generate_skill.py

Remove script and its tests. All 3 test runs bypassed it. Orchestrator writes the initial skeleton directly — it's 10 lines of markdown, not worth a script.

### Subskill char limit

Raise from 2000 to 8000 in validate_structure.py. Real subskills (youtube-to-markdown) are 3000-6000 chars. Subskills load on-demand — their token cost is bounded by conditional loading.

## Acceptance Criteria

- [x] AC1: Iterative loop — builder guides user through test → observe → refine cycle, not one-shot generation
- [>] AC2: Edit mode — builder modifies existing skill while preserving coherence (scenario test). Scenario file added; scenario execution not run in this session.
- [x] AC3: Portable docs — writing-skills.md and Designing Skills.md live in builder-skill, symlinked to docs/
- [x] AC4: No unnecessary subagents — semantic check, minimize, coherence are direct orchestrator work
- [x] AC5: Content validation — validate_structure.py implements all 4 checks: subagent_has_io, subagent_output_constrained, creates_after_bash, background_has_degradation
- [x] AC6: Smoke test — concrete test-observe-refine pattern in both skill_only.md and builder_skill.md
- [x] AC7: generate_skill.py removed, Step 2 simplified
- [>] AC8: Subskill char limit raised — builder validator limit is 8000; full `youtube-to-markdown` validation still fails on pre-existing out-of-scope issues.
- [>] AC9: Existing scenario still passes. Not run in this session.
- [x] AC10: New scenario: edit existing skill

## Testing Strategy

- **Unit tests:** validate_structure.py new checks — deterministic, crafted inputs
- **Scenario:** create-pr-review-skill.yaml — regression
- **Scenario NEW:** edit-youtube-skill.yaml — add subagent pattern to existing skill
- **Manual:** create a new skill with builder, verify iterative loop works

## Out of Scope

- Renaming `Designing *.md` → `designing-*.md` — requires repo-wide reference updates, separate cleanup task
- run.py dispatcher pattern — complex-skill-specific, not a builder concern
- Plugin installation/distribution mechanics
- MCP server builder (separate tool)
- Exhaustive content validation rules — add iteratively as problems are observed

## Tasks

- [x] 1. Move writing-skills.md and Designing Skills.md to builder-skill/references/, symlink from docs/
- [x] 2. Update SKILL.md — references to ./references/, add Edit and Validate-only routes
- [x] 3. Rewrite skill_only.md — iterative loop (write → test → observe → refine), remove generate_skill.py call, remove subagent semantic check
- [x] 4. Rewrite builder_skill.md — iterative loop, concrete smoke test pattern
- [x] 5. Create edit_skill.md — read whole skill, change request, coherence-preserving edit, test loop
- [x] 6. Remove generate_skill.py
- [x] 7. Raise subskill char limit in validate_structure.py (2000 → 8000)
- [x] 8. Add all 4 content checks to validate_structure.py (subagent_has_io, subagent_output_constrained, creates_after_bash, background_has_degradation)
- [x] 9. Tests for all 4 new validation checks
- [x] 10. Test harness: symlink-based skill loading for smoke tests in iterative loop
- [x] 10. New scenario: edit-youtube-skill.yaml
- [>] 11. Verify existing scenario still passes. Not run in this session.
- [x] 12. Self-validate: run validate_structure.py on builder-skill itself

## Files Changed

- `builder-skill/references/writing-skills.md` ← moved from docs/
- `builder-skill/references/Designing Skills.md` ← moved from docs/
- `docs/writing-skills.md` ← symlink → ../builder-skill/references/
- `docs/Designing Skills.md` ← symlink → ../builder-skill/references/
- `builder-skill/SKILL.md` — new routes, reference paths
- `builder-skill/subskills/skill_only.md` — iterative loop rewrite
- `builder-skill/subskills/builder_skill.md` — iterative loop, test pattern
- `builder-skill/subskills/edit_skill.md` — NEW
- `builder-skill/scripts/validate_structure.py` — content checks, subskill limit
- `builder-skill/scripts/generate_skill.py` — REMOVE
- `tests/builder-skill/test_generate_skill.py` — REMOVE (with script)
- `builder-skill/scenarios/edit-youtube-skill.yaml` — NEW

## Reflection

<!-- Written post-implementation by IMP -->
<!-- ### What went well -->
<!-- ### What changed from plan -->
<!-- ### Lessons learned -->
