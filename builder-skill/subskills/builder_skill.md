# Builder Skill: Scripts, Tests, and Iteration

If the skill does not need scripts, templates, or tests: use `./subskills/skill_only.md` and STOP.

Flow: brief -> tests -> scripts -> SKILL.md -> smoke test -> refine -> validate

## Step 1: Write the package brief

AskUserQuestion once:

1. `Name` — skill name, kebab-case
2. `Trigger` — when the skill should activate
3. `Outputs` — files the skill should create
4. `Scripts` — script names and purpose
5. `Templates` — template files, if any

Set `${SKILL_NAME}` and `${SKILL_DIR}`.
Write `${SKILL_DIR}/brief.md` with the brief, outputs, scripts, test cases, and constraints.

## Step 2: Create the package layout

Create:

- `${SKILL_DIR}/SKILL.md`
- `${SKILL_DIR}/scripts/`
- `${SKILL_DIR}/subskills/`
- `${SKILL_DIR}/templates/` when needed
- `tests/${SKILL_NAME}/`

## Step 3: Write tests first

Write failing tests before scripts:

- unit tests for each script
- one integration test for the full script path
- fixtures with realistic sample input

Run:

```bash
uv run pytest "tests/${SKILL_NAME}/" -v
```

Creates: test result on stdout

## Step 4: Implement scripts and templates

Implement only what the tests require.
Use pure functions, type hints, Google-style docstrings, and thin `main()` glue.
Re-run `uv run pytest "tests/${SKILL_NAME}/" -v` until the tests pass.

## Step 5: Write the skill instructions

Write `${SKILL_DIR}/SKILL.md` and any needed `subskills/*.md`.
Reference only the files that exist.
Keep the dispatcher short and push heavy detail into subskills.
Include allowed-tools, keywords, Creates: lines after bash blocks, and explicit STOP or DONE.

## Step 6: Smoke test the whole skill

Write `${SKILL_DIR}/tests/smoke-prompt.txt` with one minimal real request that should exercise the package.

```bash
mkdir -p .claude/skills "${SKILL_DIR}/tests"
rm -f ".claude/skills/${SKILL_NAME}"
ln -s "${SKILL_DIR}" ".claude/skills/${SKILL_NAME}"
claude -p "$(cat "${SKILL_DIR}/tests/smoke-prompt.txt")" --allowedTools 'Bash,Read,Write,Task,AskUserQuestion' > "${SKILL_DIR}/tests/smoke.txt"
rm ".claude/skills/${SKILL_NAME}"
```

Creates: `.claude/skills/${SKILL_NAME}` (temporary), `${SKILL_DIR}/tests/smoke.txt`

Check:

- expected files created
- no unnecessary tools
- no improvised inline scripts
- no unexpected permission failures

If the smoke test fails, refine the scripts, tests, or SKILL.md and run it again.

## Step 7: Final validation

Run:

```bash
python3 ./scripts/validate_structure.py "${SKILL_DIR}/SKILL.md"
uv run pytest "tests/${SKILL_NAME}/" -v
```

Creates: validation and test results on stdout

Fix issues, re-run, then DONE.
