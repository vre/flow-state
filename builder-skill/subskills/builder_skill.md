# Builder Skill: Create Skill with Scripts/Templates/Tests

If no scripts needed, use `./subskills/skill_only.md` instead. STOP.

Flow: Gather → Structure → Tests → Implement → Write SKILL.md → Validate → Smoke Test

## Step 1: Gather Requirements

AskUserQuestion (all at once):

1. "Skill name?" header: "Name" (kebab-case)
2. "When should this skill activate?" header: "Trigger"
3. "What does it produce?" header: "Outputs"
4. "What scripts are needed?" header: "Scripts"
5. "Any templates?" header: "Templates"

Set `${SKILL_NAME}`, `${SKILL_DIR}`.

## Step 2: Create Directory Structure

```
${SKILL_DIR}/
├── SKILL.md
├── scripts/
│   └── ${scripts from step 1}
├── subskills/
└── templates/
```

## Step 3: Write Tests First (TDD)

Create `tests/${SKILL_NAME}/conftest.py` with `sys.path.insert(0, str(Path(__file__).parent.parent.parent / "${SKILL_NAME}" / "scripts"))`.
Create `tests/${SKILL_NAME}/test_*.py`. Tests fail until scripts implemented. One test class per script.
If scripts pipe to each other: define shared output schema (field names, types). Write integration test that runs the pipeline end-to-end.

## Step 4: Implement Scripts

Pure functions, type hints, Google docstrings. Thin `main()` glue.
Each script: `#!/usr/bin/env python3`, stdin/stdout, JSON output, exit codes.

If script is a CLI tool with actions, use builder-cli-tool `--flat`:

```bash
python3 ./builder-cli-tool/scripts/generate_cli.py --name ${SCRIPT} --operations '["action1", "action2"]' --output ${SKILL_DIR}/scripts/ --flat
```

Then fill in action stubs with real logic.

## Step 5: Write SKILL.md

Use `./subskills/skill_only.md` Step 2-3 for the SKILL.md skeleton.
Budget: 500 tokens (`len(text)/4`). Include `./scripts/` and `./subskills/` refs.

## Step 6: Validate

```bash
python3 ./scripts/validate_structure.py "${SKILL_DIR}/SKILL.md"
```

Fix issues, re-validate. Run tests: `uv run pytest tests/${SKILL_NAME}/ -v`.

## Step 7: Smoke Test

Run full pipeline with sample data. Verify output. DONE.
