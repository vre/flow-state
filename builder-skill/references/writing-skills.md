# Writing Skills (SKILL.md)

> **LLM-optimized guide.** Condensed instructions for writing SKILL.md files. No references here — references and deep rationale belong in [`Designing Skills.md`](Designing%20Skills.md) which is written for humans.

This document is consumed by LLMs. Keep it concise, actionable, and free of citations.

## What Skills Are

Skills are task-specific instruction sets that Claude loads when needed. Unlike CLAUDE.md which is always in context, skills are loaded on-demand when a user invokes them or when Claude determines they're relevant.

This on-demand loading is important: skill content only consumes context when actually used. This means skills can be more detailed than CLAUDE.md instructions, but should still be efficient.

Token usage affects both quality and cost. Larger context means higher pricing and potentially degraded recall on older models. Keep skills focused on the workflow, move logic to scripts.

## Description Format

The skill description appears in listings and helps Claude decide when to use the skill. Format: trigger conditions only. Do not summarize the process.

"Use when [trigger condition]"

- "Use when user asks to extract YouTube video content" — clear trigger
- "Use when creating CLI tools with action dispatcher pattern" — clear trigger
- NOT "Extracts YouTube videos and writes markdown" — this summarizes the process

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

### Guide subagent workflow with explicit steps

Subagents improvise when instructions are vague. "Analyze the transcript" → agent invents `python3 -c` scripts. Explicit steps prevent this:

```
Steps:
1. Read INPUT with Read tool.
2. Analyze content and identify [specific output].
3. Write results to OUTPUT with Write tool.
```

Why steps over prohibitions: "Do not use Bash" gets rationalized away ("this is python3, not bash"). Explicit steps leave no room for invention — the agent follows the given workflow.

### Constrain subagent output

TaskOutput returns the agent's final text message to the coordinator's context. Without constraints, agents produce verbose final messages ("I've analyzed the transcript and written a comprehensive summary covering...") that inflate coordinator context by ~30K chars per call — causing compaction every 2-3 subagent dispatches.

Always end subagent prompts with:

```
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
  {step}: wrote {output_file} [optional metadata]
  {step}: FAIL - {what went wrong}
```

This reduces TaskOutput from ~30K to ~40-130 chars. The subagent still writes full output to files — only the status message is constrained.

Note: Haiku copies instruction format literally — keep formatting tight for small models.

### Background agent permissions may be unreliable

Background agents (`run_in_background: true`) may lose access to Write and Bash. This has varied across Claude Code versions. Always design background agents with graceful degradation:

```
PERMISSION TEST: First, Write "test" to OUTPUT. If succeeds → Mode A (normal). If fails → Mode B (return content).

Mode A: Write results to files. Final message: one-line status.
Mode B: Return content in final message:
  CONTENT:<path>
  <content>
  END_CONTENT

Parent agent parses CONTENT: blocks and writes files.
```

### Subagents cannot launch sub-subagents

Subagents do not have access to the Agent tool. If a module needs parallel Agent calls (e.g., chunk cleaning), the orchestrator must read and execute that module directly — not delegate it to a subagent. Only leaf modules (no internal Agent calls) can be delegated.

## Skill Is a Folder

A skill is a folder, not just a markdown file. Use the file system for progressive disclosure — tell Claude what files exist, it reads them when needed:

- `references/` — domain-specific reference docs (API signatures, design rationale)
- `assets/template.md` — output templates to copy
- `scripts/` — helper scripts Claude executes
- `config.json` — user-specific configuration (see Setup below)

## Don't State the Obvious

Focus on what pushes Claude out of its default behavior — internal conventions, project-specific patterns, known failure points. Don't repeat what Claude would do anyway.

## Don't Railroad

Skills are reusable across many situations. Give information, not rigid steps. Let Claude adapt to the situation. Too-specific instructions prevent adaptation.

## Setup and Configuration

Some skills need user-specific setup. Store this in `config.json` in the skill directory. If missing, instruct Claude to ask the user and create it. Subsequent runs read the config without asking.

## Persistent Data

Use `${CLAUDE_PLUGIN_DATA}` for data that must survive skill upgrades. The skill directory itself may be replaced on upgrade — `${CLAUDE_PLUGIN_DATA}` is stable.

Examples: append-only logs of previous runs, cached results, accumulated context.

## On-Demand Hooks

Skills can register session-scoped hooks via frontmatter. Use for opinionated guards that would be too restrictive as permanent hooks (e.g., block destructive commands only when touching production).

## Simple Markdown

Skills are for LLM consumption. Use simple markdown:
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

## Environment-Dependent Skills

Skills that orchestrate external tools (sandboxes, CLIs, remote agents) must verify the environment before acting. Do not assume — check.

**Check before act:** Verify toolchain and env vars inside the target environment, not just on the host. Missing tool → install on host. Missing env var → configure in target profile.

**Quoting resilience:** Nested shell invocation (host → sandbox → tool) breaks quoting. For anything beyond simple commands, write a script to shared location and execute it. Pass prompts via stdin, not argv. Precompute derived variables (`${REPO%.git}` → `${PROJECT_DIR}`) to avoid parameter expansion inside nested quotes.

**State across boundaries:** No shared filesystem between different users/machines. Use git bare repo as bridge, parse session IDs for resume, include dependency install step after clone.

See `Designing Skills.md` §6.7 for full rationale and examples.

## Anti-patterns

### Duplicating Script Logic in Skill

If your skill explains what a script does in detail, you're duplicating. The skill should show how to invoke the script. If Claude needs to understand the script's behavior, it can read the script.

### Missing Outputs

If a step produces files but doesn't list them, Claude can't detect failures. Always list what each step creates.

### Ambiguous Stop Conditions

"Continue if needed" is ambiguous. Be explicit about what conditions trigger continuation vs. completion.

### Overly Complex Single Steps

If one step has many sub-parts, split it into multiple steps. Each step should do one thing and produce clear outputs.
