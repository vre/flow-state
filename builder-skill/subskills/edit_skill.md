# Edit Skill: Goal-Driven Changes

Flow: read -> define done -> edit -> test -> observe -> refine -> validate

## Step 1: Read the whole skill

Read:

- `${SKILL_DIR}/SKILL.md`
- every file in `${SKILL_DIR}/subskills/`
- script names in `${SKILL_DIR}/scripts/`
- templates or references touched by the change

Do not edit before you understand the existing flow.

## Step 2: Define the change target

Write `${SKILL_DIR}/edit-brief.md` with:

- the requested change
- the done-condition: `This edit is complete when ...`
- hard constraints: what must not break
- files likely to change

If the request changes scope or architecture, STOP and say it needs a new plan.

## Step 3: Edit for coherence

Update the existing files in place.
Integrate the change into the current structure. Do not bolt on duplicate steps, duplicate routes, or conflicting wording.
If one file changes the contract, update the matching files in the same pass.

## Step 4: Test the changed behavior

Write `${SKILL_DIR}/tests/edit-smoke-prompt.txt` with one real request that proves the edit matters.

```bash
mkdir -p .claude/skills "${SKILL_DIR}/tests"
rm -f ".claude/skills/${SKILL_NAME}"
ln -s "${SKILL_DIR}" ".claude/skills/${SKILL_NAME}"
claude -p "$(cat "${SKILL_DIR}/tests/edit-smoke-prompt.txt")" --allowedTools 'Bash,Read,Write,Task,AskUserQuestion' > "${SKILL_DIR}/tests/edit-smoke.txt"
rm ".claude/skills/${SKILL_NAME}"
```

Creates: `.claude/skills/${SKILL_NAME}` (temporary), `${SKILL_DIR}/tests/edit-smoke.txt`

If the skill has scripts, also run the relevant unit tests.

## Step 5: Observe and refine

Read the changed files and the smoke-test output.
Ask:

- did the edit meet the done-condition?
- did any older path break?
- is the wording still coherent across files?

If not, keep editing and re-testing until the done-condition is true.

## Step 6: Final validation

Run:

```bash
python3 ./scripts/validate_structure.py "${SKILL_DIR}/SKILL.md"
```

Creates: validation result on stdout

Fix issues, re-run, then DONE.
