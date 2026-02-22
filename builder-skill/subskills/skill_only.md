# Skill Only: Create Minimal SKILL.md

## Step 1: Gather Requirements

AskUserQuestion (all 4 at once):

1. question: "Skill name?" header: "Name" options: (free text, kebab-case: `worktree-manager`)
2. question: "When should this skill activate?" header: "Trigger" options: (free text, trigger only — no workflow summary)
3. question: "What files does it produce?" header: "Outputs" options: (free text, comma-separated)
4. question: "Execution flow?" header: "Flow" options: "Sequential", "Parallel"

Set `${SKILL_NAME}` from answer 1. Set `${SKILL_DIR}` = target skill directory.

## Step 2: Generate Skeleton

```bash
echo '{"name":"${SKILL_NAME}","trigger":"...","outputs":[...],"flow_type":"..."}' | python3 ./scripts/generate_skill.py > "${SKILL_DIR}/SKILL.md"
```

Creates: `${SKILL_DIR}/SKILL.md`

## Step 3: Enhance

Read the generated skeleton. Add:
- `allowed-tools:` list in frontmatter (principle of least privilege)
- `keywords:` values (error messages, tool names, symptoms)
- Steps with explicit `Creates:` lines
- Stop conditions: `If X: STOP`
- If modifying existing skill → "Use editing-skills instead", STOP.

Keep under 300 tokens (`len(text)/4`).

## Step 4: Validate

```bash
python3 ./scripts/validate_structure.py "${SKILL_DIR}/SKILL.md"
```

If fail → fix issues from JSON output → re-validate.

## Step 5: Semantic Check

Task tool (subagent_type: "general-purpose", model: "sonnet"):

```
INPUT: {skill_content}

Check:
1. Description summarizes workflow? (FAIL — trigger only)
2. Every script step has Creates: line? (FAIL if missing)
3. Has STOP or DONE condition? (FAIL if missing)
4. Flow makes logical sense?

OUTPUT: JSON {pass: bool, issues: [{line: N, msg: "..."}]}
```

If fail → fix → re-run Step 4 + Step 5. DONE.
