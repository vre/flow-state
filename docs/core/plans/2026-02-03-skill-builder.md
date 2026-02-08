# Plan: Skill Builder

## Goal

Create a meta-skill that produces **minimal, token-efficient, tested** skills using TDD methodology.

## Problem Statement

Most skill-builder tools produce context-wasting skills because they:
- Fill templates with prose instead of structure
- Duplicate information already in scripts
- Include "helpful" explanations that waste tokens
- Treat <500 tokens as a generous budget rather than a hard ceiling
- **Never test skills before deployment**

The LLM will naturally expand to fill available space. The skill-builder must **actively compress** and **test before shipping**.

Token budget scales with activation frequency:
- **Always-on** (every conversation): <150 tokens — cost multiplied by every session
- **Frequent** (weekly): <200 tokens
- **Rare** (on-demand): <300 tokens ceiling

Large skills with multiple paths → modular subskills (separation of concerns).

## Research

See [2026-02-03-skill-builder-research.md](2026-02-03-skill-builder-research.md) for competitive analysis of 10 implementations.

**Key finding**: [obra/superpowers writing-skills](https://github.com/obra/superpowers) is the only implementation that tests skills before deployment. We build on their TDD approach.

## Intent

Produce skills that are:
1. **Minimal**: Every line justifies its existence (<300 tokens)
2. **Script-heavy**: Logic in Python/Node, not instructions
3. **Tested**: Pressure-tested with subagents before deployment
4. **CSO-optimized**: Discoverable via keywords and proper triggers

5. **Environment-aware**: Preflight check for required tools/permissions, clear error if missing
6. **Disambiguated**: Related skills (create/edit/debug) need explicit body checks, not just trigger separation

### Environment Preflight

Generated skills should include a preflight step when they depend on external tools:
```
Step 0: Verify `{tool}` available. If missing: "{tool} required. Install: `{install_cmd}`", STOP.
```
Scriptable: `scripts/validate_structure.py` can check if referenced tools exist.

### Skill Disambiguation

When skills overlap (creating-skills vs editing-skills vs debugging-skills):
- Triggers differentiate at description level
- Body includes explicit check: "If modifying existing skill → use editing-skills instead"
- Prevents wrong skill from running to completion

## Core Principles (from superpowers)

### Iron Law
```
NO SKILL WITHOUT A FAILING TEST FIRST
```

Two testing modes:
- **Skill testing** (nondeterministic): Define desired outcome → verify it fails without skill → add skill → verify it passes. Probabilistic — run multiple times if needed.
- **Script testing** (deterministic): Standard pytest. No special treatment.

### Description Trap (CRITICAL)
> "Testing revealed that when a description summarizes the skill's workflow, Claude may follow the description instead of reading the full skill content."

- Description = trigger conditions ONLY
- NEVER summarize workflow in description
- ❌ BAD: `"Use when creating skills - gathers requirements, generates skeleton, validates"`
- ✅ GOOD: `"Use when creating new skills or converting workflows into reusable skills"`

### TDD for Skills

| TDD Concept | Skill Creation |
|-------------|----------------|
| Test case | Pressure scenario with subagent |
| Production code | Skill document (SKILL.md) |
| RED | Agent violates rule without skill |
| GREEN | Agent complies with skill present |
| Refactor | Close loopholes, add rationalization counters |

## Constraints

- Generated skills MUST be under token budget: `len(text)/4` as approximation (~300 target)
- Description MUST NOT contain workflow summary
- Heavy logic in scripts, not skill instructions
- Validation via pressure testing, not just structure checks
- Gerund naming: `creating-skills` not `skill-creation`
- Keywords in description + one `keywords:` frontmatter field only (not sprinkled throughout)

## v1 Scope

**v1 ships:**
- `SKILL.md` (dispatcher)
- `subskills/skill_only.md`
- `scripts/generate_skill.py`
- `scripts/validate_structure.py`

**v1 defers:**
- `bottle_from_session.md` - manual extraction workflow documented, not automated
- `bottle_from_historian.md` - requires historian MCP, defer
- `extract_to_script.md` - requires creating-scripts skill, defer
- `full_package.md` - packaging is post-v1
- `pressure_test.md` - manual `claude -p` workflow in v1, automate later
- Scenario YAML runner - manual execution in v1, automated runner post-v1

## Reference

- youtube-to-markdown/SKILL.md: Good structure reference
- superpowers/writing-skills/SKILL.md: TDD methodology reference

## Tasks

### Phase 1: Core Dispatcher

**Always present:** Dispatcher + generator/validator scripts. Extraction scripts are optional later.

- [x] Create `skill-builder/SKILL.md` (~30 lines)
  - Step 0: Understand context
    - New skill from scratch?
    - Bottling from current session? (v1: manual workflow)
    - Bottling from historian MCP? (v1: if not installed, skip option)
  - Step 1: Gate check - if single command with ≤2 flags, no pipes/loops → "Are you sure? Could be: `{cmd}`"
  - Step 2: Route to `./subskills/skill_only.md` (always start LLM-only)
  - Step 3: After skill exists and is used, suggest script extraction when patterns emerge

### Phase 2: Subskills (conditional loading)

- [x] `subskills/skill_only.md` - creates minimal SKILL.md
  - Gather: name, trigger, outputs, flow (sequential/parallel)
  - Generate skeleton via script
  - Validate via subagent

- [>] `subskills/bottle_from_session.md` - extract workflow from context (deferred: v1 scope)
  - Analyze current conversation for repeatable patterns
  - Identify tools used, sequence, outputs
  - Generate skill structure from extracted workflow

- [>] `subskills/bottle_from_historian.md` - extract from historian MCP (deferred: requires historian MCP)
  - Detection: check if `mcp__claude-historian-mcp__*` tools available
  - If not installed: "Historian MCP not available", STOP (don't attempt)
  - Search past sessions for relevant workflows
  - Present candidates to user
  - Extract and structure chosen workflow

- [>] `subskills/extract_to_script.md` - extract LLM logic to Python (deferred: requires creating-scripts skill)
  - Analyze existing skill for repeated/deterministic patterns
  - Identify candidates: parsing, validation, file I/O, API calls
  - Suggest: "This step could be a script because {reason}"
  - If user agrees: delegate to creating-scripts skill
  - Update SKILL.md to invoke script instead of LLM logic

- [>] `subskills/full_package.md` - complete skill package (deferred: post-v1, delegates to project-builder)
  - Skill must already exist and be tested
  - Delegate infrastructure scaffolding to project-builder (tests, marketplace.json, CHANGELOG, pyproject.toml)
  - Add skill-builder-specific concerns only: pressure test config, rationalization table

### Phase 3: Scripts (from start)

These are deterministic operations - scripts from day 1, not extracted later:

- [x] `scripts/generate_skill.py`
  - Input: JSON with name, trigger, outputs, flow_type
  - Output: writes SKILL.md skeleton
  - Internal templates, minimal structure

- [x] `scripts/validate_structure.py`
  - Token estimation: `len(text)/4` (approximation)
  - Frontmatter validation: name, description, keywords present
  - Description format: starts with "Use when", no workflow verbs
  - Prose detection: regex for "This step...", "The script...", "This will..."
  - Gerund naming: pattern check for `verb-ing-noun`
  - Referenced paths: warn if `./scripts/*.py` or `./subskills/*.md` referenced but missing
  - Output: JSON `{pass: bool, issues: [{line: N, msg: "..."}]}`

**Script generation for user's skills** delegated to separate skill (creating-scripts). When skill-builder needs to add scripts to a user's skill:
```
If user's workflow has deterministic patterns:
  If creating-scripts skill exists:
    Invoke creating-scripts skill for each needed script
  Else:
    Inform user: "Script extraction available with creating-scripts skill"
    Continue LLM-only, mark extraction as deferred
```

This follows composition pattern - skill-builder orchestrates, creating-scripts handles script logic.

### Phase 4: Validation (script + subagent)

**Script validation** (deterministic checks):
```bash
python3 ./scripts/validate_structure.py SKILL.md
```
Handles: token count, frontmatter, prose patterns, gerund naming.

**Subagent validation** (semantic checks scripts can't do):
```
task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
  INPUT: {skill_content}

  Check semantic issues:
  1. Does description summarize workflow? (trigger only, no process)
  2. Every step with script has "Creates:" line?
  3. Has clear STOP or DONE condition?
  4. Flow makes logical sense?

  OUTPUT: JSON {pass: bool, issues: [{line: N, msg: "..."}]}
```

### Phase 5: Pressure Testing (TDD RED-GREEN)

After structural validation, test skill effectiveness:

**RED Phase** (baseline without skill):
```
task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
  You are testing whether a skill is needed.

  TASK: {task_that_skill_addresses}

  Complete the task WITHOUT any special instructions.
  Document your approach and any mistakes you make.
```

Document: What went wrong? What rationalizations did the agent use?

**GREEN Phase** (with skill):
```
task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
  SKILL: {skill_content}

  TASK: {same_task}

  Follow the skill instructions to complete the task.
```

Compare: Does the skill fix the baseline problems?

**Pass/Fail Rubric:**
- FAIL: Description contains workflow verbs (generates, validates, creates sequence)
- FAIL: Missing `Creates:` line after script invocation
- FAIL: No STOP or DONE condition
- FAIL: Token budget exceeded (`len(text)/4 > 300`)
- FAIL: Prose patterns detected ("This step...", "The script...")
- PASS: All invariants hold + all required outputs exist

**REFACTOR Phase**:
- If agent finds new loopholes, add explicit counters
- Build rationalization table from test iterations
- Re-test until bulletproof

### Phase 6: Rationalization Table Generation

For discipline-enforcing skills, generate a table of common excuses:

```markdown
| Excuse | Reality |
|--------|---------|
| "Too simple to need a skill" | Simple tasks get skipped. Skill ensures consistency. |
| "I'll just do it manually" | Manual = inconsistent. Skill = repeatable. |
| "This is a one-off" | One-offs become patterns. Capture now. |
```

Add to skill's "Common Mistakes" or "Red Flags" section.

Alternative: `claude -p "validate this skill: $(cat SKILL.md)"` for manual testing

### Phase 7: Hypothesis-Driven Skill Testing

Skills are nondeterministic — they guide LLM behavior, not compute results. Standard unit tests verify scripts (Phase 3). This phase formalizes **what behavioral change each skill should produce** and how to measure it.

**Problem:** Phase 5 pressure testing defines the RED-GREEN mechanism but not:
- What hypotheses to test per skill iteration
- How to express expected behavioral changes as verifiable assertions
- How to make results reproducible enough for regression

**Hypothesis format:**

Each skill iteration produces a testable hypothesis:

```yaml
# tests/skill-builder/scenarios/description-trap.yaml
name: description-trap
hypothesis: "Without skill, agent puts workflow summary in description"
task: "Create a skill for building REST APIs"
rubric:
  - check: description_no_workflow_verbs
    assert: true
  - check: token_budget
    max: 300
  - check: has_done_condition
    assert: true
runs: 3
pass_threshold: 0.66  # 2/3 must pass (nondeterministic)
```

**Mapping to TDD concepts:**

| TDD Concept | Skill Equivalent |
|---|---|
| Hypothesis | "Without skill, agent does X wrong" |
| RED test | `claude -p` task WITHOUT skill → observe failure |
| GREEN test | Same task WITH skill → observe compliance |
| Assertion | Rubric checks on output (deterministic where possible) |
| Flaky test | Inherent — hence `pass_threshold < 1.0` and multiple `runs` |

**Three verification layers:**

1. **Deterministic** (scripts): Token count, frontmatter, prose patterns → `validate_structure.py`
2. **Semi-deterministic** (rubric on LLM output): Parse generated SKILL.md, apply structural checks → scriptable
3. **Qualitative** (human judgment): Does the skill actually help? Does agent find loopholes? → manual or expensive multi-run

**v1 approach:** Scenario YAML files as documentation. Manual execution via `claude -p`. No automated runner yet.

**Post-v1:** Runner script that:
- Iterates scenario files
- Executes RED/GREEN via `claude -p` or Task tool
- Applies rubric checks (reuse `validate_structure.py` where possible)
- Reports pass rate per scenario
- Marks `@pytest.mark.pressure` for optional CI integration (slow, costly)

**Open questions:**
- Cost per scenario (~2 API calls × N runs) — acceptable for pre-deploy, not CI
- Model pinning — scenarios may pass on Sonnet but fail on Haiku
- Rubric expressiveness — how much can be checked structurally vs. needs human review

## Acceptance Criteria

1. Generated SKILL.md files MUST be <300 tokens
2. skill-builder/SKILL.md itself MUST be <150 tokens (dispatcher only)
3. Description contains NO workflow summary (trigger conditions only)
4. Every generated skill passes RED-GREEN pressure test
5. Simple tasks trigger "are you sure?" confirmation
6. Bottled processes (existing workflows) handled gracefully
7. CSO keywords present: error messages, symptoms, tool names

## Anti-Success Criteria (what MUST NOT happen)

- Skill contains explanatory prose ("This step...", "The script...")
- Skill repeats what scripts already document internally
- Skill uses more than 5 lines for any single step
- Description summarizes workflow (causes Claude to skip skill body)
- Generated skill needs manual editing to be usable
- User creates a skill for `pdfunite a.pdf b.pdf out.pdf`
- Skill deployed without pressure testing

## CSO (Claude Search Optimization) Requirements

Generated skills must include:

1. **Rich triggers in description**: Specific conditions, symptoms, contexts
2. **Keywords throughout**: Error messages, tool names, symptoms
3. **Gerund naming**: `creating-X` not `X-creator`
4. **No workflow in description**: Trigger = when, not how

## Files Created

```
skill-builder/
├── SKILL.md                      # <150 tokens, dispatcher only
├── subskills/
│   ├── skill_only.md             # Minimal SKILL.md creation (default)
│   ├── bottle_from_session.md    # Extract workflow from current context
│   ├── bottle_from_historian.md  # Extract from historian MCP
│   ├── extract_to_script.md      # Extract LLM logic to Python (iterative)
│   ├── full_package.md           # Package for distribution
│   └── pressure_test.md          # TDD baseline vs with-skill
├── scenarios/                    # Hypothesis-driven test scenarios (Phase 7)
│   └── *.yaml                   # Task + rubric + pass threshold per scenario
└── scripts/
    ├── generate_skill.py         # SKILL.md skeleton generator
    └── validate_structure.py     # Deterministic validation (tokens, prose, naming)
```

**Flow:** Create LLM-only → use → identify patterns → extract to scripts → package

**Dependencies:**
- `creating-scripts` skill when extracting to Python
- `project-builder` skill for packaging (replaces `full_package.md` scaffolding)

**Security rationale:** Python-only. Node.js/npm dependency trees are harder to audit.

## Resolved Questions

1. **Bottling flow**: Allow both approaches:
   - From current session context (default)
   - From historian MCP if installed and user requests

2. **"Doesn't need a skill" threshold**: Single CLI command with few options. E.g., `pdfunite`, `ffmpeg -i a.mp4 b.mp4`, `jq '.field'`. Trigger "are you sure?" confirmation.

3. **Test framework**: User's choice. Ask during full_package flow: pytest or plain assert scripts.

4. **Validation approach**: Two-phase:
   - Structure validation (token count, description format, prose detection)
   - Pressure testing (RED-GREEN-REFACTOR with subagents)

## Risk

1. **Agent verbosity**: The agent creating skills will naturally add "helpful" explanations. Structure validation catches prose patterns.

2. **Description trap**: Agent may summarize workflow in description. Explicit check: "Does description contain workflow steps?"

3. **Skipping tests**: Agent may claim "too simple to test". Iron Law enforcement: NO SKILL WITHOUT FAILING TEST FIRST.

4. **Rationalization**: Agent may find loopholes. Build rationalization table during testing, add explicit counters.

## Reflection

### v1 Acceptance Criteria

1. [x] Generated SKILL.md files <300 tokens — all 3 test runs: 279-284 tokens
2. [x] skill-builder/SKILL.md <150 tokens — 176, accepted as first iteration
3. [x] Description contains NO workflow summary — validated by structure + semantic checks
4. [x] Every generated skill passes RED-GREEN pressure test — 3 runs (haiku/sonnet/opus), all pass
5. [>] Simple tasks trigger confirmation — gate step exists, not tested with simple task
6. [>] Bottled processes handled — deferred subskills
7. [x] CSO keywords present — all generated skills include keywords

### What went well

- TDD worked: tests-first caught 3 bugs during implementation (YAML list parsing, code block prose, workflow verb connectors)
- Cross-skill integration test (project-builder → skill-builder) passed on first attempt
- Three-model comparison yielded actionable insight: haiku unusable for semantic checks (6/6 FPs), sonnet best for UX, opus most disciplined on scope
- Scenario YAML format emerged naturally from testing — captures hypothesis + rubric + results

### What changed from plan

- `generate_skill.py` is bypassed by all 3 test agents — they write SKILL.md directly. The skeleton is too minimal to be useful as a starting point. Consider making it optional or richer.
- Semantic check model changed from haiku to sonnet based on test evidence
- SKILL.md dispatcher at 176 tokens (budget was 150) — accepted for first iteration, compress later
- Phase 7 (hypothesis-driven testing) added during implementation based on user feedback
- Agents create scripts alongside skills without being instructed to — scope creep but pragmatic

### Lessons learned

- Token budget `len(text)/4` is a rough heuristic — good enough for gating but not precise
- `claude -p` with HEREDOC single-quotes prevents `$(cat ...)` expansion — use a temp file instead
- Haiku's semantic reasoning is unreliable for nuanced checks — save cost elsewhere, not on validation
- Testing with `claude -p` is the real acceptance test — structural validation necessary but not sufficient

## Post-Integration: Cross-Skill Alignment with cli-tool-builder (2026-02-07)

### Concern Borders

- **skill-builder** owns: SKILL.md creation, validation (structure + semantic + pressure), naming conventions for generated workflow skills
- **skill-builder does NOT own**: builder skill naming (project-builder, mcp-builder, cli-tool-builder use `{noun}-builder` pattern)
- **Integration**: skill-builder validates any SKILL.md including those in builder skills. `full_package.md` delegates infrastructure to project-builder.

### 1. Gerund naming: recommendation for workflow skills, not enforced on builders

`validate_structure.py` checks gerund naming (`verb-ing-noun`). Builder skills intentionally use `{noun}-builder` pattern for discoverability in the builder family. The gerund check should:
- WARN (not FAIL) when name contains `-builder` suffix
- FAIL for other non-gerund names (workflow skills)

**Files:** skill-builder/scripts/validate_structure.py (modify gerund check)

### 2. `validate_structure.py` used by cli-tool-builder

cli-tool-builder's SKILL.md should pass `validate_structure.py`. Currently missing `keywords:` field — needs adding.

**Files:** cli-tool-builder/SKILL.md (add keywords)

### 3. SKILL.md naming in this skill

Current SKILL.md uses `name: building-skills`. The builder family uses `{noun}-builder`. Two valid approaches:
- A) Keep `building-skills` — skill-builder IS a workflow skill (it creates things)
- B) Rename to `skill-builder` — consistent with sibling naming

Decision: keep `building-skills` for the SKILL.md name (it's what gets matched by CSO), but the directory stays `skill-builder/`. The skill name and directory name can differ.

### 4. Builder skill SKILL.md files need `keywords:` frontmatter

All three builder skills need `keywords:` in frontmatter to pass validate_structure.py:
- cli-tool-builder: `keywords: cli, tool, generator, scaffold, python, argparse`
- project-builder: already has frontmatter but verify `keywords:` present
- mcp-builder: verify separately

**Files:** respective SKILL.md files

## Post-Build Findings: Gaps Exposed by cli-tool-builder (2026-02-07)

Building cli-tool-builder revealed that skill-builder is tuned for simple workflow skills but lacks guidance for **builder skills** — skills with scripts, templates, tests, and cross-skill dependencies.

### Gap 1: No routing for builder skills

SKILL.md routes: new skill → `skill_only.md`, bottling, historian. No path for "skill that has scripts + templates + tests." cli-tool-builder needed `scripts/`, `templates/`, `tests/`, `subskills/` — skill_only.md only generates the SKILL.md file itself.

**Impact:** Builder skill authors get zero guidance on directory structure, what scripts to create, or how to organize templates.

### Gap 2: No script/template scaffolding

`generate_skill.py` produces one file. Builder skills need 10+ files. The reflection already notes "agents create scripts alongside skills without being instructed to" — the skill should guide this, not leave it to agent improvisation.

### Gap 3: No test guidance

Building cli-tool-builder was 60%+ test writing (73 tests for 2 scripts). skill-builder mentions pressure testing for SKILL.md content but has zero guidance for testing the skill's scripts. The validate_structure.py checks text, never runs or syntax-checks referenced scripts.

### Gap 4: No cross-skill awareness

We spent significant effort resolving concern borders (project-builder owns infrastructure, cli-tool-builder owns CLI patterns, skill-builder owns SKILL.md validation). skill-builder doesn't check how a new skill relates to existing ones — no overlap detection, no routing to complementary skills.

### Gap 5: validate_structure.py only validates text

Current checks: token budget, frontmatter, prose patterns, gerund naming, referenced path existence. Missing checks:
- Referenced `./scripts/*.py` are valid Python (syntax check)
- Referenced `./subskills/*.md` are themselves valid SKILL.md files (recursive validation)
- Skills with scripts have corresponding test files

### Gap 6: Token budget too tight for builders

cli-tool-builder SKILL.md is ~350 tokens. The 300 token budget is correct for workflow skills but forces compression that hurts builder skills documenting generated output structure and multiple workflow paths. Need a tiered budget.

### What should change (scope for v1.1)

1. **Add `subskills/builder_skill.md`** — route for creating skills with scripts/templates
   - Guides: directory structure, script naming, template design, test requirements
   - References project-builder for infrastructure, but adds skill-specific patterns
   - Stop condition: "If no scripts needed → use `skill_only.md` instead"

2. **Enhance `validate_structure.py`**:
   - `check_script_syntax()`: Python `ast.parse()` on referenced scripts
   - `check_subskill_validity()`: Recursive validation on referenced subskills
   - `check_test_coverage()`: Warn if `scripts/` exists but no `tests/` directory
   - Tiered token budget: 300 for workflow skills, 500 for builder skills (detect via `-builder` suffix or `scripts/` directory)

3. **Update SKILL.md routing** — add builder path:
   - Builder skill (has scripts/templates) → `./subskills/builder_skill.md`

4. **Add cross-skill check to validation** (optional, v1.1+):
   - Check if new skill's keywords overlap with existing skills
   - Suggest existing skills for delegation instead of duplication
