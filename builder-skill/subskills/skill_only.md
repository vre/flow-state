# Skill Only: Create Minimal SKILL.md

Flow: Gather → Generate → Enhance → Validate → Semantic Check

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

Apply writing-skills.md principles:
- Skill = folder: add `references/`, `assets/`, `scripts/` dirs if needed for progressive disclosure
- Description is a trigger, not a summary — describe WHEN to activate
- Don't state the obvious — only what pushes Claude out of default behavior
- Don't railroad — give information, let Claude adapt
- If skill needs user config → add `config.json` pattern (ask if missing, read if present)
- If skill stores data across runs → use `${CLAUDE_PLUGIN_DATA}` (survives upgrades)
- If skill needs opinionated guards → register on-demand hooks via frontmatter

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
