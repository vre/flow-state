# Writing Skills (SKILL.md)

This document explains principles for writing task-specific skill files, with rationale for each practice.

## What Skills Are

Skills are task-specific instruction sets that Claude loads when needed. Unlike CLAUDE.md which is always in context, skills are loaded on-demand when a user invokes them or when Claude determines they're relevant.

This on-demand loading is important: skill content only consumes context when actually used. This means skills can be more detailed than CLAUDE.md instructions, but should still be efficient.

Token usage affects both quality and cost. Larger context means higher pricing and potentially degraded recall on older models. Keep skills focused on the workflow, move logic to scripts.

## Description Format

The skill description appears in listings and helps Claude decide when to use the skill. It should follow the format:

"[Use when trigger]. [What it produces]."

The trigger tells Claude when this skill applies. The output tells Claude what to expect. Both parts matter:

- "Use when user asks to extract YouTube video content" - clear trigger
- "Writes video details and transcription into structured markdown file" - clear output

This format helps Claude make good decisions about when to invoke the skill without reading the full skill body.

## Minimize Skill, Maximize Script

The skill file guides Claude's behavior and workflow. Heavy processing logic belongs in scripts that Claude executes.

Why this matters:

1. Skill content consumes context tokens every time it's loaded
2. Script content is only loaded when Claude reads the script (which it often doesn't need to do)
3. Scripts can be tested independently of Claude
4. Scripts can handle edge cases without cluttering the skill

Structure your skill as a workflow that calls scripts:

```
## Step 1: Extract

python3 ./scripts/extract.py "<URL>" "<output_dir>"

Creates: ${BASE_NAME}_transcript.md, ${BASE_NAME}_metadata.md
```

The skill tells Claude WHAT to do (run this script) and WHAT to expect (these files). The script handles HOW (all the actual extraction logic).

## Variables

Define variables once at the beginning, then reference them with ${VAR} throughout. This serves two purposes:

1. Reduces repetition and typo risk
2. Makes the variable recognizable - ${BASE_NAME} clearly refers to something defined earlier

```
Set BASE_NAME = youtube_{video_id}

Step 1 creates: ${BASE_NAME}_transcript.md
Step 2 reads: ${BASE_NAME}_transcript.md
Step 3 creates: ${BASE_NAME}_summary.md
```

Use recognizable names. ${BASE_NAME} is clear. ${X} is not.

## Flow Notation

Complex workflows benefit from compact notation that shows the execution order at a glance.

Sequential steps:
```
A → B → C
```
This means: do A, then B, then C. Each step must complete before the next starts.

Parallel steps:
```
(A | B) → C
```
This means: A and B can run in parallel, then C runs after both complete.

For complex flows with conditions and branches, use mermaid diagrams. They're more verbose but handle complexity that text notation cannot.

Why this matters: Without clear flow notation, Claude may run steps in wrong order or miss parallelization opportunities.

## Explicit Outputs

After each step that produces files, list what it creates:

```
Creates: file1.md, file2.md
```

This serves a critical purpose: it enables failure detection. If Claude runs a step and the expected output doesn't exist, Claude can detect the problem and handle it. Without explicit outputs, Claude may proceed with missing files and produce confusing errors later.

This is particularly important for scripts that may fail silently or produce partial output.

## Stop Conditions

Make termination conditions explicit. Claude should know exactly when to stop, not just when to continue.

```
If video_available: false → Inform user "Video unavailable", STOP.
```

```
If all components exist and no issues found → DONE, no action needed.
```

Why this matters: Without explicit stop conditions, Claude may continue processing when it should stop, or ask unnecessary questions about whether to continue.

## Subagent Prompts

When delegating work to the Task tool (subagents), structure the handoff clearly:

```
INPUT: ${transcript_file}
OUTPUT: ${summary_file}
TASK: Summarize the transcript focusing on key insights...
```

Start with INPUT and OUTPUT file paths. This tells the subagent exactly what it's working with and where to put results. The TASK description comes after.

Why INPUT/OUTPUT first: Subagents start fresh without your context. They need to know immediately what files to read and where to write. Burying this information in a paragraph of instructions leads to missed outputs.

### Constrain subagent output

TaskOutput returns the agent's final text message to the coordinator's context [1]. Without constraints, agents produce verbose final messages ("I've analyzed the transcript and written a comprehensive summary covering...") that inflate coordinator context by ~30K chars per call [2] — causing compaction every 2-3 subagent dispatches.

Always end subagent prompts with:

```
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
  {step}: wrote {output_file}
  {step}: FAIL - {what went wrong}
```

This reduces TaskOutput from ~30K to ~40-130 chars [3]. The subagent still writes full output to files — only the status message is constrained.

See `docs/writing-model-specific-prompts.md` for model-specific formatting differences (Haiku copies instruction format literally).

### Background agents cannot use Write

Background Tasks (`run_in_background: true`) cannot prompt for tool permissions [4]. The Write tool is auto-denied with "prompts unavailable". Use blocking Tasks when subagents need to write files. Background Tasks can use Bash for file writes, but this is fragile for large or complex content.

## Simple Markdown

Skills are for LLM consumption [5]. Use simple markdown:
- Plain headers and bullets
- No emojis or visual formatting tricks
- No complex table layouts
- Code blocks for commands and file paths

For emphasis and structure, use text conventions:
- ALL_CAPS for critical: "If X: STOP"
- `<placeholder>` for required values: `<output_directory>`
- `[optional]` for optional: `[--verbose]`
- `${VAR}` for variables: `${BASE_NAME}_file.md`

Save visual formatting for human-facing documentation like README files.

## Referencing Scripts

Use relative paths from the skill location:

```
python3 ./scripts/extract.py
```

Not absolute paths or paths relative to working directory. Skills may be installed in different locations.

Scripts should be self-documenting - include usage information that Claude can read if needed. But the skill shouldn't duplicate what's in the script. The skill shows HOW to invoke; the script documents its own behavior.

## Anti-patterns

### Duplicating Script Logic in Skill

If your skill explains what a script does in detail, you're duplicating. The skill should show how to invoke the script. If Claude needs to understand the script's behavior, it can read the script.

### Missing Outputs

If a step produces files but doesn't list them, Claude can't detect failures. Always list what each step creates.

### Ambiguous Stop Conditions

"Continue if needed" is ambiguous. Be explicit about what conditions trigger continuation vs. completion.

### Overly Complex Single Steps

If one step has many sub-parts, split it into multiple steps. Each step should do one thing and produce clear outputs.

## References

[1]: https://github.com/anthropics/claude-code/issues/16789 "TaskOutput returns final result text"
[2]: https://www.richsnapp.com/article/2025/10-05-context-management-with-subagents-in-claude-code "Context management with subagents"
[3]: Empirical finding, youtube-to-markdown context analysis, session f3ce1cae, 2026-02-15
[4]: https://apidog.com/blog/claude-code-background-tasks/ "Background tasks limitations"
[5]: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices "Skill authoring best practices"
