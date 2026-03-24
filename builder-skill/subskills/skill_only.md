# Skill Only: Create and Iterate

Flow: Brief -> 3 variants -> test -> compare -> refine -> validate

## Step 1: Write the brief

AskUserQuestion once:

1. `Name` — skill name, kebab-case
2. `Trigger` — when the skill should activate
3. `Outputs` — files the skill should create
4. `Flow` — `Sequential` or `Parallel`

Set `${SKILL_NAME}` and `${SKILL_DIR}`.
Write `${SKILL_DIR}/brief.md` with the exact brief, constraints, and target outputs.

## Step 2: Generate 3 drafts in parallel

Create `${SKILL_DIR}/drafts/`.

Task tool, three runs in parallel:

```text
INPUT: ${SKILL_DIR}/brief.md
OUTPUT: ${SKILL_DIR}/drafts/will.md
TASK: Write a conventional SKILL.md draft that will work with the stated brief. Keep it compact. Include allowed-tools, keywords, explicit STOP or DONE, and Creates: lines after bash blocks.
Steps:
1. Read INPUT with Read.
2. Write the full draft to OUTPUT with Write.
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
will: wrote ${SKILL_DIR}/drafts/will.md
will: FAIL - <reason>
```

```text
INPUT: ${SKILL_DIR}/brief.md
OUTPUT: ${SKILL_DIR}/drafts/should.md
TASK: Write a less obvious draft that should work, using a different step structure or routing choice from will.md.
Steps:
1. Read INPUT with Read.
2. Write the full draft to OUTPUT with Write.
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
should: wrote ${SKILL_DIR}/drafts/should.md
should: FAIL - <reason>
```

```text
INPUT: ${SKILL_DIR}/brief.md
OUTPUT: ${SKILL_DIR}/drafts/might.md
TASK: Write an unconventional draft that might work and may challenge the first obvious approach. Keep it coherent and still within scope.
Steps:
1. Read INPUT with Read.
2. Write the full draft to OUTPUT with Write.
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
might: wrote ${SKILL_DIR}/drafts/might.md
might: FAIL - <reason>
```

## Step 3: Test each draft with real input

For each draft:

1. Copy the draft to `${SKILL_DIR}/SKILL.md`.
2. Write `${SKILL_DIR}/tests/${variant}-prompt.txt` with one minimal real request.
3. Load the skill and run it.

```bash
mkdir -p .claude/skills "${SKILL_DIR}/tests"
rm -f ".claude/skills/${SKILL_NAME}"
ln -s "${SKILL_DIR}" ".claude/skills/${SKILL_NAME}"
claude -p "$(cat "${SKILL_DIR}/tests/${variant}-prompt.txt")" --allowedTools 'Bash,Read,Write,Task,AskUserQuestion' > "${SKILL_DIR}/tests/${variant}.txt"
rm ".claude/skills/${SKILL_NAME}"
```

Creates: `.claude/skills/${SKILL_NAME}` (temporary), `${SKILL_DIR}/tests/${variant}.txt`

If `claude -p` is unavailable or the test did not run, STOP and report that the loop is blocked.

## Step 4: Compare and combine

Read all drafts and test outputs.
Write `${SKILL_DIR}/comparison.md` with:

- what worked
- what failed
- what surprised you
- which parts to keep

Decision rule:

- all 3 fail at the same point -> fix the brief or the test
- 1 draft fails alone -> fix that draft's approach
- best parts split across drafts -> combine them into one new `${SKILL_DIR}/SKILL.md`

## Step 5: Refine until the skill behaves

Repeat:

1. tighten `${SKILL_DIR}/SKILL.md`
2. rerun the real test
3. read the output
4. remove unused steps or wording

Stop only when the test passes, the skill stays within scope, and no obvious bloat remains.

## Step 6: Final validation

Run:

```bash
python3 ./scripts/validate_structure.py "${SKILL_DIR}/SKILL.md"
```

Creates: validation result on stdout

Fix issues, re-run validation, then DONE.
