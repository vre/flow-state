# Planning Reflection: Builder-project v2

Date: 2026-03-24

## Problems Encountered

### 1. Iterative convergence took 12 review rounds
Codex found issues in every round for 11 iterations. Each fix exposed the next hidden assumption. The plan started as a "small" change list and grew into a 180-line document with 14 acceptance criteria, 19 tasks, and detailed edge-case specifications.

Root cause: the initial plan used small-plan template for a standard-plan sized change. Missing sections (Situational Context, Constraints, Testing Strategy, Out of Scope, Files Changed) meant design decisions were implicit and had to be extracted through adversarial review.

### 2. `.gitignore` semantics required precise understanding
Three iterations were spent on `.claude/` vs `.claude/*` and how git un-ignore rules interact with parent directory patterns. The initial assumption (`.claude/` ignored + `!` un-ignore) was wrong. Codex caught this and demanded behavioral verification (`git check-ignore`).

### 3. Downstream impact analysis was inaccurate
Initial plan claimed all three builder skills called `build_project.py`. Only `builder-cli-tool` does. This inflated the perceived blast radius and created false "acceptable breakage" framing.

### 4. Skill-linking specification was progressively tightened
Started as "scan siblings, offer selection." Ended with: scan root definition, ≤4 vs >4 AskUserQuestion behavior, exact-name matching, unknown-name re-prompt, empty/none skip, relative symlinks to directories (not files), no-overwrite semantics.

## How Resolved

- Switched from plan-small to plan-standard structure after round 2
- Added Codex as iterative reviewer (process already defined in CLAUDE.md)
- Each round fixed all findings before re-submitting — no debt carried forward
- Disagreements resolved by ORC with justification (e.g., skill always implies plugin)

## Lessons Learned

1. **Use plan-standard template from the start when changes touch >3 files or alter contracts.** The small template omits sections that prevent exactly the class of bugs Codex found.

2. **Downstream impact claims must be verified, not assumed.** `grep` for actual call sites before writing "these builders depend on this."

3. **`.gitignore` patterns are behavioral, not declarative.** String-presence tests are insufficient — behavioral tests with `git check-ignore` catch the real failure mode.

4. **Interactive SKILL.md behavior needs the same specification rigor as code.** "Ask the user" is not a spec. Edge cases (>4 options, skip, re-prompt, overwrite) must be explicitly defined or the implementer will invent behavior.

5. **Review convergence follows a pattern:** first rounds catch structural issues (missing sections, wrong contracts), middle rounds catch consistency issues (contradictions between sections), final rounds catch edge-case gaps. Budget 8-12 rounds for contract-changing plans.
