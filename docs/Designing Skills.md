# Designing Skills: Good Practices (2026)

> **Deep reference.** This document explains the *why* behind skill design decisions with full rationale and references. For the condensed, LLM-optimized instruction set, see [`writing-skills.md`](writing-skills.md).

This document outlines principles for writing effective skill definitions (SKILL.md) for AI agents.

Skills follow the [Agent Skills](https://agentskills.io) open standard, adopted by Claude Code, GitHub Copilot, OpenAI Codex, Cursor, and others [1].

**Note:** As of January 2026 (v2.1.3), Claude Code merged slash commands into skills [2]. Files at '.claude/commands/review.md' and '.claude/skills/review/SKILL.md' both create `/review`. Existing commands keep working; skills add supporting files, frontmatter control, and auto-invocation.

---

# Part I: The Strategy (Why)

Skills are task-specific instruction sets loaded on-demand when invoked. Unlike AGENTS.md (always in context), skills consume tokens only when used—but still matter for efficiency.

**Progressive Disclosure (from Agent Skills spec):**
1. **Metadata (~100 tokens):** `name` + `description` loaded at startup
2. **Instructions (<5k tokens):** Full SKILL.md when skill activates
3. **Resources (as needed):** Scripts/references loaded only when required

## 1. Context Economy for Skills

### 1.1 Skill vs. Script Division

A common mistake: asking the agent to perform logic (looping, parsing, state) in chat.

| Approach | Token Cost | Reliability |
| :--- | :--- | :--- |
| Logic in skill | High (every iteration in context) | Low (agent forgets state) |
| Logic in script | Low (one invocation) | High (deterministic code) |

**Principle:** Minimize Skill, Maximize Script.

- **Skill:** Lightweight orchestration—what to run, in what order, what to expect.
- **Script:** Heavy lifting—parsing, loops, API calls, file I/O.

### 1.2 Token Budget

Skills load into context when invoked. Budget accordingly:

- **Frequently-loaded skills:** <150 words (~200 tokens) - skills that load in many sessions
- **Getting-started workflows:** <200 words each - onboarding/setup skills
- **Standard skills:** <500 tokens (~50 lines) - most skills
- **Scripts:** Not in context until agent reads them (which it often doesn't need to)
- **Docs in scripts:** Self-documenting scripts mean skill doesn't duplicate

The stricter budgets for frequently-loaded skills matter because they consume context in every session where they might be relevant [11].

### 1.3 No Duplication

If a script has usage docs, the skill shouldn't repeat them. The skill shows HOW to invoke; the script documents its own behavior.

```
# Bad: duplicates script docs
Step 1: Run extract.py
  - Accepts URL as first argument
  - Accepts output directory as second argument
  - Creates transcript.md and metadata.json
  - Supports --verbose flag for debugging

# Good: just invokes
Step 1: python3 ./scripts/extract.py "<URL>" "<output_dir>"
Creates: ${BASE_NAME}_transcript.md, ${BASE_NAME}_metadata.json
```

## 2. LLMs Know Skill Patterns

Similar to CLI conventions (see *Designing CLI Tools.md-§2), LLMs are trained on workflow patterns:

- **Standard flow notation is free.** `A → B → C` for sequential, `(A | B) → C` for parallel.
- **Standard placeholders are free.** `<input_file>`, `<output_dir>`, `${VAR}`.
- **Standard stop conditions are free.** `If X: STOP`, `DONE when Y`.

**Implication:** Use familiar notation. Inventing novel syntax forces the LLM to parse your custom format.

---

# Part II: The Architecture (What)

## 3. Skill Structure

Organize skills in this order for predictable parsing.

### 3.1 Description (Trigger & Output)

Format: `[Use when trigger]. [What it produces].`

```
Use when user asks to extract YouTube video content.
Produces structured markdown with transcript and metadata.
```

The trigger helps Claude decide when to invoke. The output helps Claude know what to expect.

**The Description Trap (CRITICAL):**

Testing reveals that when a description summarizes the skill's workflow, Claude may follow the description instead of reading the full skill content [11]. The description becomes a shortcut that bypasses your carefully crafted instructions.

```yaml
# ❌ BAD: Workflow summary - Claude may follow this instead of reading skill
description: Use when creating skills - gathers requirements, generates skeleton, validates output

# ✅ GOOD: Trigger conditions only - forces Claude to read the skill body
description: Use when creating new skills or converting workflows into reusable skills
```

**Rule:** Description = trigger conditions ONLY. Never summarize the process.

### 3.2 Variables

Define once at top, reference with `${VAR}` throughout:

```
Set BASE_NAME = youtube_{video_id}
Set OUTPUT_DIR = ./output/${BASE_NAME}
```

**Benefits:**
*Reduces hallucinated filenames
*`${BASE_NAME}` is recognizable—`${X}` is not
*Single source of truth for paths

### 3.3 Flow Notation

**Sequential:**
```
A → B → C
```
Each step completes before next starts.

**Parallel:**
```
(A | B) → C
```
A and B run concurrently, C waits for both.

**Complex flows: Use Mermaid diagrams—LLMs understand them well (abundant training data) and they're token-efficient [3]:**

| Format | Tokens (simple diagram) |
| :--- | :--- |
| Mermaid | ~50 |
| PlantUML | ~80 |
| JSON (Excalidraw) | ~500 |
| XML (draw.io) | ~1,200 |

Mermaid is 24x more efficient than XML-based formats. Prefer Mermaid over ASCII art for complex flows—it's both more compact and more reliably parsed.

### 3.4 Explicit Outputs

After each step, state what it creates:

```
Step 1: python3 ./scripts/extract.py "<URL>" "${OUTPUT_DIR}"
Creates: ${BASE_NAME}_transcript.md, ${BASE_NAME}_metadata.json

Step 2: python3 ./scripts/summarize.py "${OUTPUT_DIR}/${BASE_NAME}_transcript.md"
Creates: ${BASE_NAME}_summary.md
```

**Why:** Enables failure detection. If expected output doesn't exist, agent can handle it instead of proceeding with missing files.

### 3.5 Stop Conditions

Make termination explicit:

```
If video_unavailable: Inform user "Video not accessible", STOP.
If transcript empty: Inform user "No captions available", STOP.
If all outputs exist and verified: DONE.
```

**Why:** Without explicit stops, agents may continue when they should halt, or ask unnecessary "should I continue?" questions.

## 4. Script Patterns

### 4.1 Parameter Conventions

Follow patterns from established skills:

```bash
# Full paths as arguments
python3 script.py /path/to/input.pdf /path/to/output.xlsx

# Output directory for multiple outputs
python3 script.py /path/to/input.mp4 /path/to/output_dir/
# Script decides filenames internally

# Identifiers extracted from input
python3 script.py "https://youtube.com/watch?v=ABC123"
# Script extracts video ID internally
```

### 4.2 Self-Documenting Scripts

Scripts should validate and guide:

```python
if len(sys.argv) < 3:
    print("Usage: extract.py <url> <output_dir>")
    print("  url: YouTube video URL")
    print("  output_dir: Directory for output files")
    sys.exit(1)
```

The skill doesn't need to document this—the script does.

## 5. Subagent Delegation

When passing work to Task tool (subagents), use INPUT/OUTPUT first:

```
INPUT: ${transcript_file}
OUTPUT: ${summary_file}
TASK: Summarize the transcript focusing on key insights...
```

**Why INPUT/OUTPUT first:** Subagents start fresh without your context. They need file paths immediately, not buried in prose.

**Bad:**
```
Please summarize the transcript. The file you need to read is
located at /path/to/transcript.md and you should write the
output to /path/to/summary.md.
```

## 6. Advanced Patterns

### 6.1 Conditional Subskill Loading

For multi-use skills, keep the main SKILL.md as a lightweight dispatcher. Heavy instructions live in `./subskills/`:

```
skill-name/
├── SKILL.md              # Dispatcher (~60 lines)
└── subskills/
    ├── flow_a.md         # Only loaded for case A
    ├── flow_b.md         # Only loaded for case B
    └── update_flow.md    # Only loaded if resource exists
```

**Pattern:**
```
Step 0: Check state
If exists: Read and follow ./subskills/update_flow.md

Step 1: Ask user which output they want
  A. Summary only
  B. Transcript only
  C. Full

Step 2: Based on choice, read ./subskills/{relevant}.md
```

**Benefit:** User choosing "Summary only" never loads transcript modules. Token savings scale with skill complexity.

### 6.2 Parallel Execution

Use `|` to mark parallelizable work:

```
transcript_extract.md → (transcript_summarize.md | comment_extract.md) → comment_summarize.md
```

Each parallel branch can run as a separate subagent concurrently.

**Benefits:**
*Faster completion—parallel work finishes sooner
*Context isolation—each subagent has clean context
*Orchestrator stays light—heavy LLM work offloaded

### 6.3 Subagent Offloading

Heavy LLM work (summarization, analysis) should run in subagents, not the orchestrator:

```
task_tool:
- subagent_type: "general-purpose"
- model: "sonnet"
- prompt:
  INPUT: ${transcript_file}
  OUTPUT: ${summary_file}
  TASK: Summarize focusing on key insights...
```

**Why:** Orchestrator context stays clean for coordination. Subagent context is disposable after task completes.

### 6.4 Action Directives

Prevent subagents from stalling with explicit action requirements:

```
ACTION REQUIRED: Use the Write tool NOW to save output to OUTPUT file.
Do not ask for confirmation.
```

Without this, subagents may stop to ask permission or present results instead of writing them.

### 6.5 Subagent Workflow Guidance

Subagent prompts are not skills. Skills are reusable and benefit from flexibility (§14 "Don't Railroad"). Subagent prompts are single-use, task-specific, and the subagent has no context beyond the prompt. Different constraints → different design.

**Problem:** Vague task descriptions cause subagents to improvise tools. "Analyze the transcript and identify paragraph breaks" → agent invents `python3 -c` scripts with timestamp parsing. The agent fills gaps in the instructions with its own approach.

**Solution:** Explicit steps that name the tools and the sequence:

```
Steps:
1. Read INPUT with Read tool.
2. Analyze content and identify paragraph breaks at topic shifts, ~500 chars apart.
3. Write line numbers to OUTPUT with Write tool.
```

This is not railroading — the agent still decides *what* the paragraph breaks are (the judgment). The steps constrain *how* it interacts with the system (the workflow). Railroading would be dictating the analysis logic.

**Why prohibitions fail:** "Do not use Bash" gets rationalized ("this is python3, not bash"). "Do not write inline scripts" gets reinterpreted ("this is analysis code, not a script"). Explicit steps leave no gap to fill — the agent follows the given workflow instead of inventing one.

**Guideline:** Constrain the workflow (tools, sequence, I/O). Leave the judgment free (analysis, classification, content generation).

### 6.6 Incremental Update Flows

For skills that may re-process existing data, handle updates explicitly:

```
Step U1: Analyze existing state
Step U2: Show status table (what exists, versions, issues)
Step U3: Ask user how to proceed
  - Re-extract specific component
  - Update metadata only
  - Full refresh
  - Keep existing
Step U4: Backup before overwrite, then execute
```

**Benefit:** Avoids wasteful re-processing. User controls what gets updated.

---

# Part III: Operations (How)

## 7. Simple Markdown

Skills are for LLM consumption. Keep formatting simple:

*Plain headers and bullets
*Code blocks for commands and paths
*No emojis or visual formatting tricks
*No complex table layouts

**Emphasis conventions:**
*`ALL_CAPS` for critical: `STOP`, `DONE`
*`<placeholder>` for required values: `<output_directory>`
*`[optional]` for optional: `[--verbose]`
*`${VAR}` for variables: `${BASE_NAME}_file.md`

## 8. Referencing Scripts

Use relative paths from skill location:

```
python3 ./scripts/extract.py
```

Not absolute paths. Skills may be installed in different locations.

## 9. When NOT to Create a Skill

Not everything needs a skill. Avoid creating skills for:

- **Single CLI commands:** `pdfunite a.pdf b.pdf out.pdf`, `jq '.field' file.json`
- **Standard operations:** Things Claude already knows well
- **One-off tasks:** Unless you'll repeat them
- **Project-specific conventions:** Put in CLAUDE.md instead

**Heuristic:** If it's one command with few options, you don't need a skill.

## 10. Claude Search Optimization (CSO)

Skills must be discoverable. Claude reads all skill descriptions to decide which to load.

### 10.1 Rich Triggers

Include specific conditions, symptoms, and contexts:

```yaml
# ❌ Vague
description: Helps with PDFs

# ✅ Specific
description: Use when extracting text from PDFs, filling PDF forms, or merging PDF documents
```

### 10.2 Keywords

Include words Claude would search for:
- Error messages: "ENOENT", "timeout", "race condition"
- Symptoms: "flaky", "hanging", "inconsistent"
- Tool names: actual commands, library names

### 10.3 Gerund Naming

Use verb-ing form for skill names:
- ✅ `creating-skills` not `skill-creator`
- ✅ `extracting-pdfs` not `pdf-extractor`
- ✅ `debugging-tests` not `test-debugger`

Active voice describes what you're doing, improving discoverability.

## 11. Security: Context Poisoning & Prompt Injection

Skills load instructions into the agent's context. Malicious or poorly-written skills can manipulate agent behavior.

### 11.1 Attack Vectors

**Context poisoning:** Skills inject instructions that override intended behavior or manipulate the agent to take unauthorized actions.

**Indirect prompt injection:** Malicious content in skill files, references, or fetched data can contain hidden instructions [12].

**Data exfiltration:** Skills can instruct agents to send sensitive data to external endpoints [13].

**Privilege escalation:** Skills may request tools or permissions beyond what's needed.

### 11.2 Defenses

**For skill authors:**

- **Use `allowed-tools`:** Restrict which tools the skill can use. Principle of least privilege.
  ```yaml
  allowed-tools:
    - Read
    - Write
    - Bash(git:*)
  ```
- **No dynamic fetches in skills:** Don't fetch external URLs during skill execution—pre-bundle resources.
- **Sanitize references:** If skill loads external files, validate content before processing.
- **Explicit scope:** Skills should only affect intended files/directories.

**For skill consumers:**

- **Only install trusted skills:** Treat skills like executable code—because they are.
- **Review before install:** Read SKILL.md and scripts before adding to your environment.
- **Audit `allowed-tools`:** Check what permissions a skill requests.
- **Sandbox untrusted skills:** Use isolated environments for testing unknown skills.

### 11.3 Red Flags in Skills

- Skills that request broad tool access (`Bash(*)`)
- Skills that fetch external URLs at runtime
- Obfuscated or minified script content
- Skills that ask to modify system files or configs
- References to external services without clear purpose

## 12. Anti-Patterns

- **❌ Duplicating script logic in skill.** If skill explains what script does in detail, you're duplicating.
- **❌ Missing outputs.** If a step produces files but doesn't list them, failure detection fails.
- **❌ Ambiguous stop conditions.** "Continue if needed" is unclear. Be explicit.
- **❌ Overly complex single steps.** If one step has many sub-parts, split into multiple steps.
- **❌ Novel notation.** Inventing `>>` or `=>` when `→` is standard wastes parsing effort.
- **❌ Prose-heavy instructions.** Walls of text lose the agent. Use structured notation.
- **❌ Over-engineering.** "Self-reflecting autonomous super-duper agents" for problems solved by three API calls in sequence [7].
- **❌ Relative paths in tools.** Agent moves out of root directory → relative paths break. Use absolute paths [8].
- **❌ Overloaded prompts.** Mixing classification, reasoning, and action in one prompt. Separate concerns.
- **❌ Vague triggers.** "Build me something cool" gives nothing to anchor on. Specific triggers enable reliable invocation [9].
- **❌ Unmeasurable success criteria.** "Make it engaging" vs "include 3 code examples". 85% success rate with measurable criteria vs 41% without.
- **❌ Temporal requirements.** "Use latest best practices" breaks reproducibility. Specify exact versions and concrete requirements.
- **❌ Workflow in description.** Summarizing the process in description causes Claude to skip the skill body [11].
- **❌ Deploying untested skills.** Skills without pressure testing will have loopholes [11].

---

# Part IV: Reference

## 13. Skill Testing

**Tests first.** Run a baseline test WITHOUT the skill, then WITH the skill. If the agent doesn't fail without it, you don't know if the skill teaches the right thing [11].

1. **Baseline (without skill):** Does the agent make mistakes or take wrong approaches?
2. **With skill:** Does it now comply?
3. **Happy path:** Does the skill complete successfully with valid input?
4. **Error path:** Does it stop correctly when input is invalid?
5. **Output verification:** Are all expected files created?

Test with `claude -p` for manual verification.

## 14. Lessons from Anthropic's Internal Skill Usage

Based on cataloging hundreds of skills in active use at Anthropic [15]:

### Skill Categories

Skills cluster into recurring types. Knowing these helps identify gaps in your organization:

- **Library & API reference** — internal library edge cases, footguns, usage patterns
- **Product verification** — test/verify with external tools (Playwright, tmux), record video of output
- **Data fetching & analysis** — connect to monitoring/data stacks with credentials and query patterns
- **Business process automation** — aggregate ticket tracker + GitHub + Slack into formatted output
- **Code scaffolding** — generate boilerplate with natural language requirements
- **Code quality & review** — deterministic review scripts, adversarial subagent review
- **CI/CD & deployment** — monitor PRs, retry flaky CI, gradual traffic rollout
- **Runbooks** — symptom → investigation → structured report
- **Infrastructure operations** — routine maintenance with guardrails for destructive actions

### Description Is a Trigger, Not a Summary

When Claude Code starts a session, it builds a listing of every skill with its description. This listing is what Claude scans to decide if a skill matches. The description is not a summary — it describes when to trigger [15].

### Don't State the Obvious

If a skill is primarily about knowledge, focus on what pushes Claude out of its default behavior — internal conventions, project-specific patterns, known gotchas. Don't repeat what Claude would do anyway [15].

### Gotchas as Team Scaling Mechanism

For self-authored skills, gotchas are a design smell — fix the skill instead. For shared/team skills, gotchas are a low-barrier amendment zone: a team member adds a gotcha line without understanding the core flow. This is a fast way to fix recurring problems without refactoring [15]. But it is a patch — if the same gotcha keeps being needed, the skill's design should be fixed.

### Don't Railroad

Skills are reusable across many situations. Being too specific prevents Claude from adapting. Give information, not rigid steps [15]. Note: this applies to skill-level instructions, not subagent prompts — subagents benefit from explicit workflow steps (§6.5).

### Setup and Persistent Data

- Store user-specific config in `config.json` in the skill directory. If missing, instruct Claude to ask and create it.
- Use `${CLAUDE_PLUGIN_DATA}` for persistent data that survives skill upgrades (unlike data in the skill directory itself).
- Skills can maintain state across invocations: append-only logs, cached results, accumulated context.

### On-Demand Hooks

Skills can register hooks via frontmatter that are only active during the session. Use for opinionated guards that would be too restrictive as permanent hooks [15].

### Distribution

Two paths: repo-checked (`.claude/skills/`) for small teams, or plugin marketplace for scale. Curate before publishing — bad or redundant skills are easy to create. Let skills prove value organically before promoting [15].

## 15. References

- [1] [Agent Skills Specification](https://agentskills.io/specification) - Open standard for portable skills
- [2] [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills) - Official Anthropic guidance, commands/skills merge
- [3] [Diagramming Tools Token Efficiency](https://dev.to/akari_iku/analyzing-the-best-diagramming-tools-for-the-llm-age-based-on-token-efficiency-5891) - Mermaid vs XML/JSON comparison
- [4] [LLMermaid](https://github.com/fladdict/llmermaid) - Diagram-based task processing for LLMs
- [5] [Designing MCP Servers.md](Designing%20MCP%20Servers.md) - Shared principles: context economy, fail helpfully
- [6] [Designing CLI Tools.md](Designing%20CLI%20Tools.md) - Script parameter patterns, Unix conventions
- [7] Microsoft (2025): [AI Agent Orchestration Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns) - Complexity warnings
- [8] Anthropic (2025): [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) - Absolute paths, tool design
- [9] Addy Osmani (2025): [How to Write a Good Spec for AI Agents](https://addyosmani.com/blog/good-spec/) - Vague prompts study
- [10] [Designing Hooks.md](Designing%20Hooks.md) - Lifecycle hooks for cross-cutting concerns
- [11] [obra/superpowers writing-skills](https://github.com/obra/superpowers) - TDD for skills, description trap, CSO patterns
- [12] Lasso Security (2025): [Detecting Indirect Prompt Injection in Claude Code](https://www.lasso.security/blog/the-hidden-backdoor-in-claude-coding-assistant) - Attack vectors
- [13] PromptArmor (2025): [Claude Cowork Exfiltrates Files](https://www.promptarmor.com/resources/claude-cowork-exfiltrates-files) - Data exfiltration risks
- [14] [Claude Code Security Documentation](https://code.claude.com/docs/en/security) - Official security guidance
- [15] Thariq (2026-03-17): [Lessons from Building Claude Code: How We Use Skills](https://x.com/trq212/status/2033949937936085378) - Anthropic's internal skill patterns, categories, and best practices
