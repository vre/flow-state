# Two-Agent Development Automation

## Roles

- **Agent A** — Planner. Writes plans, fixes plans after review, reviews implementation.
- **Agent B** — Implementer. Reviews plans, implements from plan context, fixes implementation after review, does reflection and merge.
- **C (Job Applicant)** — Not a separate agent. Whichever of A/B is reviewing the other's work takes this role. Their input is treated as fallible — valuable but not authoritative.
- **D (Human)** — Orchestrator. Controls decision points, triggers agents, routes reviews, approves phase transitions.

## Flow

```
D orchestrates all transitions. No agent proceeds to next phase without D's approval.

PLAN PHASE
  D → A: "Plan the task"
  A: researches, writes plan, self-reviews as skeptic
  A → D: "Plan ready for review"
  D → B (fresh agent): "Review the plan docs/plans/xxx.md"
  B: reviews as job applicant C (thorough but fallible)
  B → D: review findings
  D → A: feeds B's review back
  A: addresses findings, updates plan
  A → D: "Plan updated"
  D: approves plan, transitions to Implementation Phase

IMPLEMENTATION PHASE
  D → B (same agent, has plan context from review): "Implement the plan"
  B: implements, self-reviews as skeptic
  B → D: "Implementation ready for review"
  D → A (has original plan context): "Code review worktree, then review against plan"
  A: reviews as job applicant C — code quality first, plan compliance second
  A → D: review findings
  D → B: feeds A's review back
  B: addresses findings

REFLECTION + MERGE
  B: marks acceptance criteria status, writes reflection
  B: does merge phase (rebase, squash, docs)
  D: final acceptance testing, approves merge
  B: removes worktree and branch
```

## Why Two Agents

- **Context separation.** A has planning context (intent, alternatives considered, constraints). B has implementation context (what worked, what surprised, technical decisions). Neither has the other's full context — this makes reviews genuine.
- **The C rotation.** When A reviews B's code, A doesn't know the implementation struggles — they see the result fresh. When B reviews A's plan, B doesn't know the research journey — they see the plan as the implementer who must execute it. The "job applicant" framing keeps reviews honest: good enough to be useful, not trusted blindly.
- **D stays in control.** Agents don't hand off to each other directly. Every transition goes through D. This prevents runaway automation and keeps the human as the decision maker.

## Context Preservation

- **B reviews plan then implements.** Same agent session. B's plan review context (understanding of the plan, questions raised, concerns) carries into implementation. This is intentional — the implementer's first act is understanding the plan critically.
- **A writes plan then reviews implementation.** A retains the planning context — what was intended, what tradeoffs were made, what the acceptance criteria mean. This makes A's implementation review deeper than a cold read.

## What CLAUDE.md Covers vs What D Does

CLAUDE.md defines *what happens in each phase* — the rules, review prompts, coding standards, commit conventions. It doesn't specify *who* runs each phase.

D (human) handles orchestration: which agent gets which task, routing reviews between agents, deciding when to approve transitions. This is manual and intentional — automation of orchestration is a future consideration, not a current goal.

## Automating the Review Handoffs

The review steps (B reviews plan, A reviews implementation) can be automated. Both benefit from retained session context — B's plan understanding carries into implementation, A's planning intent informs the code review. This rules out cold-start approaches.

### The Pattern: Headless Resume + Letterbox Files

Each tool has a headless mode that processes a prompt and exits, and a session resume that preserves prior context:

| Tool | Headless mode | Session resume | No-permission mode |
|------|--------------|----------------|-------------------|
| Claude Code | `claude -p` | `--resume <session-id>` | `--dangerously-skip-permissions` |
| Codex CLI | `codex exec` | `codex exec resume <session-id>` | `--full-auto` + sandbox |
| Copilot CLI | `copilot -p` | `--continue` (last) / `--resume` (picker) | `--allow-all-tools` |
| OpenCode | `opencode run` | `-s <session-id>` (unreliable in headless as of Feb 2026) |

Communication between agents uses files as letterboxes — no MCP, no FIFOs, no polling needed:

```
.reviews/
  plan-review.md          # B writes plan review findings here
  code-review.md          # A writes implementation review findings here
```

### Automated Flow Example (Claude Code as both A and B)

```bash
# A is interactive, session ID is <A-id>
# D triggers B to review plan:
claude -p --session-id <B-id> --dangerously-skip-permissions \
  "Review the plan at docs/plans/xxx.md as a senior developer. Be critical." \
  > .reviews/plan-review.md

# A reads .reviews/plan-review.md, fixes plan (interactive)

# D triggers B to implement (same session, has plan review context):
claude -p --resume <B-id> --dangerously-skip-permissions \
  "Implement the plan" > .reviews/impl-log.md

# D triggers A to review implementation (has planning context):
claude -p --resume <A-id> --dangerously-skip-permissions \
  "Review the implementation in .worktrees/xxx against the plan" \
  > .reviews/code-review.md

# B reads .reviews/code-review.md, addresses findings (resumed session)
```

### Cross-Tool Variation (e.g. Claude Code as A, Codex as B)

The letterbox pattern is tool-agnostic. Replace the headless command per tool:

```bash
# B is Codex, reviews plan:
codex exec --full-auto \
  "Review the plan at docs/plans/xxx.md as a senior developer. Be critical." \
  -o .reviews/plan-review.md

# B implements (Codex, resumed session with plan context):
codex exec resume <B-id> --full-auto \
  "Implement the plan" -o .reviews/impl-log.md
```

The plan must be self-contained (already a requirement in CLAUDE.md) since the implementing agent may be a different tool with different capabilities.

Copilot CLI follows the same pattern:

```bash
# B is Copilot CLI, reviews plan:
copilot -p "Review the plan at docs/plans/xxx.md as a senior developer. Be critical." \
  --allow-all-tools > .reviews/plan-review.md

# B implements (resumed, has plan review context):
copilot -p --continue --allow-all-tools \
  "Implement the plan" > .reviews/impl-log.md
```

Copilot CLI sessions are stored server-side (GitHub), enabling cross-machine resume. It also supports ACP server mode (`copilot --acp`) for machine-to-machine integration, and ships with multi-model support (Claude, GPT, Gemini).

### Alternative: Agent-as-Server

Both Codex and Copilot CLI can run as protocol servers, enabling direct invocation from another agent without letterbox files:

- **Codex MCP server** (`codex mcp-server`) — exposes `codex(prompt)` and `codex-reply(prompt, threadId)`. Any MCP client (Claude Code, OpenCode, Copilot) can invoke it.
- **Copilot ACP server** (`copilot --acp`) — Agent Client Protocol over stdin/stdout using NDJSON. Machine-to-machine interface for orchestration tools.

### Constraints

- **Resuming an active session blocks.** `claude -p --resume` on a session that's open in another terminal hangs silently (file lock). Agents must take turns, not run concurrently on the same session.
- **OpenCode headless resume is unreliable.** Session memory not consistently passed through in `opencode run` as of Feb 2026 (issues #917, #2404).
- **Context window is the limit, not storage.** Sessions are stored as JSONL files with no TTL or size cap. On resume, long histories trigger compaction (summarization of older messages). Recent context survives; deep early details may compress.
- **`--fork-session`** (Claude Code) creates a new session ID from an existing session's context. Useful if you need to branch a session without locking the original.
