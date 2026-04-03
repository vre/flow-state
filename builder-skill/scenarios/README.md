# Test Scenarios

Hypothesis-driven test scenarios for the builder-skill.

## Running a scenario

From `builder-skill/` directory:

```bash
# Build prompt with skill content inlined
cat > /tmp/prompt.txt <<PROMPT
You have a skill for building skills. Follow it exactly.

SKILL (building-skills):
$(cat SKILL.md)

SUBSKILL (skill_only.md):
$(cat subskills/skill_only.md)

TASK: {task from scenario yaml}

PRE-SUPPLIED ANSWERS (skip AskUserQuestion):
1. Name: {name}
2. Trigger: {trigger}
3. Outputs: {outputs}
4. Flow: {flow_type}

Output directory: /tmp/skill-test-output

Follow the skill steps. Write the final SKILL.md to the output directory.
Use scripts at $(pwd)/scripts/ for generation and validation.
PROMPT

# Run
cat /tmp/prompt.txt | claude -p --allowedTools 'Bash,Read,Write,Task'

# Validate output
python3 ./scripts/validate_structure.py /tmp/skill-test-output/SKILL.md
```

## Scenario format

Each `.yaml` file defines:

- `hypothesis`: what we expect the agent to do/avoid
- `inputs`: pre-supplied answers for non-interactive mode
- `rubric`: structural + semantic checks
- `results`: recorded outcomes from actual runs
- `observations`: findings that feed back into skill improvement
