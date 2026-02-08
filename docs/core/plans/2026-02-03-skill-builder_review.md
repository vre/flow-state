# Review: 2026-02-03-skill-builder.md

## Summary
Good direction: strict token budgets, “description trap” awareness, modular subskills, and explicit validation/pressure-testing. Biggest risk is scope creep: the plan tries to be a full framework (generator + validator + pressure tests + rationalization tables + packaging) and will likely violate its own token/complexity goals unless you lock the v1 boundary hard.

## Alignment with AGENTS.md
- ✅ Has measurable constraints + acceptance criteria.
- ✅ Explicit validation approach (script checks + subagent checks).
- ⚠️ “Never start implementation before approval” is compatible; plan is implementable in phases.
- ⚠️ The plan reads like a spec + implementation notes; still ok, but make sure the produced SKILL.md stays tiny (<150 tokens) and pushes detail into scripts/subskills.

## What’s solid
- **Description trap** called out as CRITICAL and reflected in constraints.
- **Progressive disclosure** via subskills; default path is minimal.
- **Skill vs script split** is consistent with `docs/Designing Skills.md`.
- **Anti-success criteria** is concrete (prose, duplication, workflow-in-description).

## Must-fix / clarify
1. **Token counting heuristic is too weak**
   - `word_count * 1.3` will produce noisy false positives/negatives across short texts.
   - Pick one:
     - A) Accept “approximate only” and reword requirements to “heuristic budget” (less strict), or
     - B) Add an optional dependency for accurate tokenization (dev-only), or
     - C) Use a more stable heuristic (e.g., `len(text)/4` for English-ish text) and document it as *approximation*.

2. **Pressure testing needs an explicit pass/fail rubric**
   - “Agent complies” is vague. Define pass as: *no violations of listed invariants* + *all required outputs exist*.
   - Specify what the subagent must return (already JSON) and what counts as a failure (missing STOP/DONE, description contains workflow verbs, missing Creates: lines, etc.).

3. **Dependency on `creating-scripts` skill is a hard external coupling**
   - Plan says extraction delegates to `creating-scripts`. If that skill doesn’t exist yet, you need a fallback behavior: either “STOP and ask user to install” or “continue LLM-only and mark extraction deferred”.

4. **“Are you sure?” threshold is underspecified**
   - Add a deterministic rule for the gate (examples are not a rule). E.g. “single command with ≤2 flags and no branching/piping” or “≤1 invocation, no loops, no config files”.

5. **Dispatcher vs “scripts from day 1” is slightly contradictory**
   - Phase 1 says route to LLM-only first; Phase 3 says some scripts are from day 1.
   - Make it explicit: “Dispatcher always exists; generator/validator scripts are always created; extraction scripts are optional later.”

## Should-fix / improvements
- **Keep v1 smaller**: consider v1 = dispatcher + `skill_only.md` + `validate_structure.py` only. Pressure testing can be “manual workflow” in v1; automate later.
- **CSO vs token ceiling tension**: “keywords throughout” can bloat. Add a rule: keywords only in description + one dedicated “keywords” line, not sprinkled everywhere.
- **Historian MCP path**: define detection + failure mode (if MCP not installed, do not try; ask user; STOP).
- **Validation script should validate referenced file paths**: even minimal “does this referenced script exist?” checks catch many foot-guns.

## Specific edits I’d do to the plan (not implementation)
- Replace “MUST be <300 tokens” with “MUST be under budget as measured by <chosen method>” and define the method.
- Add a “v1 scope” section listing exactly which subskills/scripts ship first.
- Add a “pressure test rubric” bullet list so tests aren’t subjective.
