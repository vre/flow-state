# CLAUDE-spec.md — Rationale for Every Line in CLAUDE.md

This document explains WHY each rule in CLAUDE.md exists and why it is worded the way it is. Its purpose is to prevent well-meaning edits from breaking functional rules whose rationale is not obvious from the text alone.

## Lineage

CLAUDE.md evolved through five projects and frameworks:
1. **HomeworkTrackerCC** (Sep 2025) — React Native app where the first AGENTS.md was created
2. **Out-In-Vibe-Flow v1-v4** (Sep-Oct 2025) — framework extraction with ~30 files, BDD/Gherkin, Mission Command
3. **flow-state initial** (Nov 2025) — condensed to single CLAUDE.md, dropped BDD ceremony
4. **flow-state multi-agent** (Jan-Feb 2026) — Plan/Implement/Review/Merge phases, HC/ORC/IMP roles, worktrees
5. **flow-state current** (Mar 2026) — process improvements from cycle reflections

The predecessor's design rationale (`Out-In-Vibe-Flow/docs/understanding/design-rationale.md`) identifies the core problem: **"The AI Knows But Doesn't Apply"** — LLMs have access to all engineering knowledge but don't apply it steadily. Training data contains predominantly undisciplined code. Knowledge ≠ behavior. The framework exists to bridge this gap with structural guardrails.

Evidence quality markers:
- **[incident]** — traced to a specific documented incident or reflection
- **[git]** — traced to a git commit with clear context
- **[inferred]** — rationale is clear from context but no conversation record found
- **[founding]** — present from project inception (2025-11-09), pre-dates conversation history
- **[predecessor]** — traced to Out-In-Vibe-Flow or HomeworkTrackerCC

---

## Line 3: "NEVER START IMPLEMENTATION BEFORE APPROVAL. Autopilot is FAILURE."

**[founding]** Present from initial commit `ecad5f0` (2025-11-09). Original wording: "DO NOT START to edit the file before the user approved the idea." Promoted to line 3 (top of file) and strengthened to ALL CAPS in `467f8a9` (2026-01-31).

**Why top of file:** The writing guide (`docs/writing-claude-agents-md.md`) documents that instructions at the beginning receive stronger LLM attention. This is the single most important rule — an LLM that starts implementing before approval wastes entire cycles.

**Why the wording:** "NEVER" + ALL CAPS is the strongest available emphasis. "Autopilot is FAILURE" names the anti-pattern concretely so the LLM can match against it.

**Predecessor context:** Out-In-Vibe-Flow's AGENTS.md (line 69-71) already had: "Framework development: Ask user what they want before proceeding" and "Never auto-fill templates or make domain assumptions." The flow-state version is stronger because Out-In-Vibe-Flow's softer phrasing ("Ask user") was insufficient — the agent still proceeded without waiting for approval. The escalation to "NEVER" + "FAILURE" reflects learned insufficiency of polite instructions.

---

## Line 5: "Speak like a Finn or a Dutch..."

**[founding → evolved]** Original (2025-11-09): "Speak with Finnish directness." Evolved through two iterations:
- `58701f5` (2026-01-26): Added "Dutch" as second cultural reference
- `9b81a70` (2026-02-05): Added explicit adjectives "blunt, direct, concise and factual"

**Predecessor:** Out-In-Vibe-Flow AGENTS.md (line 13): "Speak with Finnish directness - no flattery or empty compliments." Same rule, same wording. This survived the entire framework → single-file condensation unchanged.

**Why "Finn or Dutch":** "Finnish directness" alone may not be understood by all models. Adding Dutch broadens cultural recognition. Both cultures are stereotyped for directness without rudeness — the desired behavior.

**Why explicit adjectives:** "Finnish directness" is abstract. "blunt, direct, concise and factual" are concrete behavioral instructions the LLM can follow. Each adjective was added because the LLM found ways to be indirect while technically being "Finnish."

**Banned phrase list:** Started with 6 phrases (2025-11-09), grew to 9 by 2026-02-05. Each addition (`"Good feedback"`, `"Excellent find"`, `"This is excellent"`) was triggered by the LLM finding new sycophantic phrasings that bypassed the existing list. The list is a behavioral blocklist, not exhaustive — it trains the LLM away from the pattern.

**Why "Nothing is done before proven done":** Prevents premature declarations of completion. LLMs tend to declare success before verification.

---

## Line 7: "Base answers on scientific facts... Show your reasoning when making claims."

**[founding]** Present from initial commit. Citation format (`[1]` in body) added in `467f8a9` (2026-01-31).

**Why "Show your reasoning":** Requiring the model to show reasoning when making claims reduces hallucination — the model catches its own errors when forced to justify inline instead of stating as facts. This was critical with pre-reasoning models (pre-o1/o3) where hallucination was rampant, and remains a preventive measure with current models.

**Why citation format is specified:** Without a format, the LLM either omits citations or uses inconsistent styles. The `[1]: <url> "description"` format is compact and machine-parseable.

---

## Line 9: "Present findings... Prioritize precision over simplification... Reply in user's language..."

**[founding → incident]**

**Why "Prioritize precision over simplification":** When models summarize or simplify, information is lost. This is a common and costly failure mode — the model produces a clean, readable summary that omits critical details. The instruction inverts the default priority: keep precision even at the cost of longer output.

**Why "No unnecessary jargon. Use analogies and explain domain-specific concepts":** This is a general instruction written for a cross-domain assistant. The user works across scientific, technical, and other domains where they are not always a specialist. The instruction ensures the model makes complex topics accessible without requiring the user to first learn domain-specific terminology. Originally written as a system prompt instruction for a general-purpose conversational assistant, then carried into CLAUDE.md.

**Why "Reply in user's language":** Present from initial commit. Almost accidentally deleted in a 2026-03-14 session — another agent removed it thinking it was a duplicate, not understanding that it serves a specific function: the user communicates in both Finnish and English, and the LLM must match.

**Why two language rules in one line:** "Reply in user's language" = dialogue language follows HC. "Write text in English unless file is in other language" = file content defaults to English. These are different scopes (conversation vs. file output) and both are needed.

**Why this line motivated CLAUDE-spec.md:** The accidental deletion proved that functional rules get removed when the editor doesn't understand the rationale. This file exists to prevent that.

---

## Line 11: "You are a deep expert..."

**[founding]** Present from initial commit as the opening line. Demoted from line 1 to line 11 in `467f8a9` (2026-01-31) — the anti-autopilot and anti-flattery rules were deemed more critical (attention decays with position).

**Why "including disagreements when needed":** LLMs default to agreement. Explicit permission to disagree is required to activate critical thinking behavior. Knowledge ≠ behavior — LLMs know they should push back but won't without explicit activation.

**Why "detect hidden assumptions":** LLMs think inside the box (see `docs/writing-claude-agents-md.md`, "LLMs Think Inside the Box"). Without this instruction, the LLM will not spontaneously question premises.

---

## Line 13: Roles HC/ORC/IMP

**[git]** Introduced `215c27b` (2026-02-25) when `session-codex` skill enabled multi-agent delegation. Before this, only "human companion" existed.

**Why three roles:** The two-agent workflow (Claude plans, Codex implements) needed explicit role separation. HC = human sets direction. ORC = Claude orchestrates. IMP = Codex executes. Without this, Claude would try to implement directly instead of delegating.

**Predecessor:** Out-In-Vibe-Flow used implicit roles: "AI guides, user decides (checkpoints)." No delegation — single AI did everything. The MathTrainer comparison session (2026-03-06) documented the shift: OIVF had "Mission-agent pattern with TodoWrite" while flow-state has "session-codex subagent delegation." The explicit role system was required because multi-agent delegation needs clear ownership of planning vs implementation.

**Why "present options, don't use dialogs to push to proceed":** The LLM's natural behavior is to propose and immediately proceed. This inverts the dynamic: present options, then wait. Original version (`58701f5`, 2026-01-26) had a typo ("do push to proceed" instead of "don't push") — the correction in `9b81a70` confirms this was important enough to fix immediately.

**Lineage:** out-in-vibe-flow (predecessor, ~2025-10-01) used implicit roles. flow-state made them explicit because delegation requires clear ownership.

---

## Line 17: "More than 5 tool calls or file changes"

**[git]** Originally "more than 3 calls or 500 tokens" in `467f8a9` (2026-01-31). Changed to "5 tool calls or file changes" same day in `ae5d7e3`.

**Why the change:** "500 tokens" is not observable at decision time — the LLM cannot count tokens. "File changes" is concrete. Threshold raised from 3 to 5 because 3 triggered plan phases for trivial changes.

---

## Line 18: "ORC informs HC what the next step is. Do not just say what you did."

**[git]** Introduced `d32164a` (2026-02-25).

**Why forward-looking:** The LLM's default is to summarize what it just did (backward-looking). HC needs to approve the *next* action, not acknowledge the *last* one. "Do not just say what you did" explicitly names and prohibits the default behavior.

---

## Line 24: "Untested assumption... test early, document results."

**[incident]** Introduced `215c27b` (2026-02-25). Earlier form in `9b81a70` (2026-02-05): "Critical assumption in plan — test with quick experiment."

**Triggering incident:** The 2026-02-15 planning session for constrained subagent output. The assumption "TaskOutput returns the full conversation log" survived two plan versions. One test disproved it and made both plans unnecessary. Cost of testing: ~$0.50, 5 min. Cost of implementing on a false assumption: hours, ~$10+. Documented in `docs/youtube-to-markdown/reflections/2026-02-15-planning-constrained-subagent-output.md`.

**Second incident:** `.is_multipart` on plain tuples (2026-02-24). The plan claimed "plain tuples work in tests" without testing. `hasattr(tuple(), 'is_multipart')` is False. Documented in `docs/core/reflections/2026-02-24-planning-competitive-research-discovery.md`.

---

## Line 25: "HC defines scope and problem — iterate understanding together"

**[founding]** This is a collaboration clause. Both sides bring perspective and knowledge to the table. It is not a model where only the human proposes ideas or only the human spots flaws — the LLM does both too. Combined with line 11's "including disagreements when needed" and the anti-flattery rule, this ensures the LLM identifies flaws in ideas rather than just agreeing. The instruction activates bidirectional collaboration.

---

## Line 26: "Interface change → propose design exploration, iterate 3-5 designs"

**[inferred → HC rationale]** When you ask an LLM for a solution, it gives the statistically most likely answer matching the local context. But the full solution space is larger than what the LLM's session context contains. Requesting 3-5 alternatives forces the LLM to search more broadly. By combining and iterating these alternatives, the human — who has the full domain context — can identify the best option. A single proposal from the LLM converges on the average; multiple proposals reveal the space.

---

## Line 27: ADR process

**[predecessor]** ADRs (Architecture Decision Records) were already defined in Out-In-Vibe-Flow 8 months earlier — `create-adr.sh` script and templates were part of Phase 1 (Sep 2025). Recently added to flow-state CLAUDE.md as the project grows to a size where architectural decisions with meaningful tradeoffs need to be tracked. Proactive — no specific incident required; architectural governance becomes necessary at this project scale.

---

## Line 33: "Define measurable and observable acceptance criteria"

**[inferred]** Basic software engineering: acceptance criteria should be binary — pass or fail, measurable and observable. Without this, "done" becomes subjective and the LLM will declare success prematurely (see line 5: "Nothing is done before proven done").

---

## Line 36: "API/library assumptions → delegate to subagents: verify"

**[incident]** There are documented incidents in conversation history. During planning, the LLM makes assumptions about library functions or API behavior based on its training data. These assumptions may be wrong due to hallucinated knowledge or library version changes since training cutoff. When unverified, the plan leads the implementation down a wrong path. The fix: verify assumptions against actual documentation or behavior during planning, not after implementation has started. Related to line 24 (test assumptions early).

---

## Line 30: "DO NOT USE OR CHANGE TO AGENT PLAN MODE"

**[git]** Introduced `467f8a9` (2026-01-31), same commit that introduced the custom plan process.

**Why prohibited:** Claude Code's `EnterPlanMode` writes to `.claude/plans/` — a tool-specific location that is not version-controlled, not self-contained, not reviewable by external agents, and not organized by plugin. The custom process requires plans in `docs/<plugin/core>/plans/` as committed deliverables. Agent Plan Mode would bypass the entire plan-as-deliverable workflow.

**Why alternative was added (2026-03-14):** The writing guide says every prohibition needs an alternative. Original form had none. Updated to: "write plans to `docs/<plugin/core>/plans/` files instead."

---

## Line 32: "Single source of truth... never .claude/plans/ or .copilot/session-state/"

**[git]** Introduced `ae5d7e3` (2026-01-31).

**Why specific paths are named:** Claude Code defaults to `.claude/plans/`. GitHub Copilot defaults to `.copilot/session-state/`. Naming these paths explicitly blocks the default behavior of both tools. Without explicit prohibition, the LLM follows its tool's default.

---

## Line 34: "Mission Command: include intent, goal, constraints..."

**[git]** Introduced `58701f5` (2026-01-26).

**Why Auftragstaktik:** The plan is executed by a delegated agent (IMP/Codex) who has only the plan as context. Mission Command doctrine: give the subordinate intent and constraints, let them choose methods. This is literally the delegation model — IMP operates autonomously within the plan's constraints.

**Lineage:** HomeworkTrackerCC (Sep 2025) → Out-In-Vibe-Flow `research/` directory contained extensive Mission Command research (v0-v13 iterations). The framework's Phase 1 Origin doc states: "Mission Command Approach: Principal-Agent model for autonomous extraction." Out-In-Vibe-Flow used "MISSION COMMANDER'S INTENT" and "MISSION COMMAND PROTOCOL" patterns in versioned AGENTS.md files (ver2-AgentB through ver5-AgentE). flow-state simplified this from a multi-file protocol to a single plan documentation requirement.

---

## Line 35: "Use exact requirements, no temporal references"

**[inferred]** Introduced `467f8a9` (2026-01-31).

**Why:** Plans are delegated to agents who may execute them days later. "Current best practices" depends on training data. "Latest version" changes between plan writing and implementation. Exact versions and requirements are reproducible; temporal references are not.

---

## Line 37: "Implementation is delegated to an agent who has only the plan as context"

**[git → incident]** Introduced `467f8a9` (2026-01-31). Original verbose form: "an agent who is as knowledgeable and skilled as you are but does not have anything above when starting."

**Why this is the core design constraint:** The planning agent (ORC/Claude) has full conversation context. The implementing agent (IMP/Codex) starts fresh with only the plan file. If the plan references undocumented assumptions, the implementer guesses wrong or wastes time re-researching. The 2026-02-24 reflections confirmed this worked: Codex caught issues that ORC's self-review missed because it read the plan as a standalone document.

---

## Line 40: "When you think that the plan is ready ask if there is something else or proceed to self-review"

**[HC rationale]** This is a pre-condition gate. The LLM may think the plan is ready and want to proceed, but the human may not agree. This line forces a check: is it ready from the human's perspective too? It asks and suggests — "can we continue to self-review, or do you have more?" This ensures the human has the opportunity to add, challenge, or redirect before the review cascade begins.

**How PLANNING END emerged:** The implementation phase was split into phases first (setup, rules, loop, end). Then the planning phase grew long enough to warrant similar structure. PLANNING END was created as a mirror — a structured exit from planning with gates and reviews, just as implementation has a structured exit.

---

## Line 41: "With clear mind take role of a skeptic"

**[founding]** Present from second commit `80209e6` (2024-11-14) as "3. With clear mind validate."

**Why "clear mind":** Found online as a prompt technique. Helps the model think as a third party while retaining its knowledge of the work. Partially removes contextual bias — the model has just created the plan and is biased toward defending it. This is a cheap and effective first content review.

**Why "skeptic":** Explicitly instructing a perspective shift activates critical evaluation. Used in two places (PLANNING END and IMPLEMENTATION END) because the bias exists in both phases.

---

## Line 42: "Delegate plan review via session-codex"

**[git → HC rationale]** Introduced `215c27b` (2026-02-25). Replaced the earlier "Print instruction to HC: Ask the job applicant to critically review the plan" pattern.

**Why two different models:** Different training produces different blind spots. Using a second model (Codex) for review catches things the first model (Opus) misses. This is empirically validated across multiple planning cycles.

**Why Codex specifically:** Codex does plan review first, then implementation in the same session — two birds with one reading and context usage. The plan review gives Codex deep understanding of the plan before it starts coding. This originated from the observation that Opus is better at planning and conversation, while Codex (5.3 era, xhigh setting) was better at precise implementation from a finished plan.

**Why `session-codex`:** Before this, plan review required the human to manually copy-paste prompts. The skill automated delegation. Research document `docs/core/research/2026-02-25-agent-sandbox-session-delegation.md` documents the technical foundation.

---

## Line 43: "Review iteration: fix all findings, no debt... Disagreement → you decide with justification"

**[HC rationale]** When the review finds problems, ALL are fixed — even cosmetic ones. The goal is a diamond-quality plan. There is no reason to leave anything unfixed at this stage; it is genuinely expensive to carry defects into implementation where the plan defines the scope boundary. `continue` reuses the same Codex session so it retains memory of the previous review round.

**Why iterate until reviewer passes:** Sometimes 3+ rounds are needed as each fix reveals new issues. If the process stopped after the first round's fixes, subsequent problems would only be discovered during implementation — where the LLM would work around them instead of fixing them properly (because the plan defines the box, and thinking inside the box is the default).

**Why "you decide with justification":** ORC (the orchestrator) has more context than Codex — it has the full conversation with HC. When there is genuine disagreement between ORC and Codex, ORC must make the call and explain why. The decision authority follows the context advantage.

---

## Line 44: "ORC writes planning reflection"

**[HC rationale]** Only ORC has conducted the dialogue with HC. Only ORC can reflect on how planning progressed — the turns, the changes, the HC challenges, the Codex review findings. It is the only party with full planning context. The trailing clause ("ORC drove the planning; Codex only reviewed") exists to prevent a rewrite from reassigning ownership to Codex or IMP, which happened in at least one CLAUDE.md edit attempt.

---

## Line 45: "Ask HC to approve plan for Implementation Phase"

**[founding]** This is a gate. Implementation cannot start until the human explicitly approves. At this point the plan has been through self-review, external review, and multiple fix iterations. The human likely reads the plan carefully at this stage — now that it is clean — and may raise new concerns that send it back to the planning table. This connects directly to line 3: "NEVER START IMPLEMENTATION BEFORE APPROVAL."

---

## Lines 50-53: Worktree setup

**[git → incident]** Worktrees introduced `58701f5` (2026-01-26). Path changed from `.git/worktrees/` to `.worktrees/` in `23161d1` (2026-01-27).

**Why worktrees:** Isolation for parallel development without polluting main. Before worktrees, the original flow-state (Nov 2025) worked directly on main. out-in-vibe-flow had no isolation at all.

**Line 51 — "Copy plan file to worktree, rm from main":** **[incident]** Multiple incidents where the plan remained on main and also existed in the worktree, causing merge conflicts every time. Especially problematic when the plan on main wasn't even committed — just sitting as an untracked file. The word "move" was tried first but the LLM copied instead of moving. Current wording "copy... rm" is explicit about both actions. Arguably could be "move and delete" but copy+delete is unambiguous.

**Line 52 — "run `uv sync` in dirs with pyproject.toml":** The flow-state project has multiple separate Python plugins (youtube-to-markdown, imap-stream-mcp), each built independently. `uv` was chosen from the start for modern, fast, clean package management. `pyproject.toml` is the modern way to manage dependencies with `uv`.

**Why `.env*` copy:** Environment files are not committed (`.gitignore`) but needed for tests and tools.

**Codex sandbox workaround (line 53):** **[incident]** Added `42e2832` (2026-03-07). Three cycles documented the problem:
- imap-stream-mcp v0.7.0: `index.lock` error — Codex can't write to `.git`
- youtube-to-markdown v2.12.0: `.git` metadata outside writable roots
- imap-stream-mcp v0.7.1: same issue, third time

Codex's Seatbelt sandbox blocks `(subpath ".git")`. Renaming to `.git-codex-sandbox-workaround` bypasses this while keeping filesystem isolation. Documented in `docs/core/research/2026-02-25-agent-sandbox-session-delegation.md`.

---

## Lines 56-58: PRE-IMPLEMENTATION GATE

**[git → inferred]** Originally part of "IMPLEMENTATION START" in `215c27b` (2026-02-25). Promoted to separate gate (2026-03-14) based on the insight that LLMs think inside the box — they patch incrementally and do not spontaneously question whether the approach itself is right.

**Why a separate gate:** Knowledge instructions ("consider alternatives") do not produce behavior. A process gate — a mandatory step before any code is written — forces evaluation. See `docs/writing-claude-agents-md.md`, "LLMs Think Inside the Box".

**Why "Do not patch around friction — fix the friction":** The LLM's default is to work around problems rather than address root causes. Explicit prohibition of the default behavior + direction to the alternative.

---

## Lines 60-68: Implementation Rules

**[founding → predecessor → HC rationale]** These rules are needed for the model to behave as intended. Without them, the model does not follow these practices. Tested empirically through Opus 4.0/4.5 — not yet verified whether Opus 4.6 would comply without them, but earlier models did not.

### Line 61: "NO CODE before tests"

A/B tested — this was the cheapest (fewest tokens) and most effective wording for TDD activation. The reason for tests-first is not classical TDD's "design emerges from tests" — an LLM thinks about the code solution holistically and cannot separate design phases like a human. But empirically, writing tests first produces more testable code. When code is written first, the tests written afterward tend to be superficial because everything is already committed to a structure. Tests first forces testability thinking as a separate step.

**Predecessor rationale:** Out-In-Vibe-Flow's `design-rationale.md` (lines 19-31): "The AI understands TDD conceptually but implements code without tests first because that pattern dominates the training examples. This creates a knowledge-action gap."

### Line 61: "YAGNI + KISS + DRY + avoid Wordiness"

**YAGNI/KISS:** Clear tendency to over-spec and over-solve. Reference code in training data tends toward large solutions. The instruction steers bottom-up instead of top-down. The 2026-02-15 planning reflection confirms: "Over-engineering is the default failure mode."

**DRY:** Duplication still appears despite this instruction — it doesn't fully prevent it, but reduces it.

**Wordiness:** Earlier Claude models (Opus 4.0, Sonnet 4.0) were excessively verbose in all output. This is hammered repeatedly (also line 68) because the tendency is strong.

Out-In-Vibe-Flow AGENTS.md (lines 72-83) had the same principles split across 6 items. flow-state condensed to one line — same activation, fewer tokens.

### Line 62: "When a bug is found: write a failing test first, then fix"

**[incident]** Observed LLM behavior: when a bug is reported, the model immediately fixes it without writing any regression test. This instruction forces the test first, which ensures: (1) the fix is verifiable through the test, (2) the bug cannot silently regress, (3) testability is maintained.

### Line 63: "Testability: Pure functions + thin main() glue. No DI frameworks."

The simplest way to produce testable Python code with minimal instruction tokens. Pure functions are inherently testable. Thin `main()` glue keeps orchestration separate from logic. "No DI frameworks" prevents over-engineering — Python doesn't need dependency injection frameworks for testability.

### Line 64: "Test manual cases with claude -p / copilot -p"

This project has many skills and MCPs installed locally. Without this instruction, the human would have to manually run test cases — an unnecessary intermediary. This gives the AI the ability to test how a feature actually works end-to-end by invoking the CLI with a prompt.

### Line 65: "Use uv"

Project tool choice from the start. Best known way to handle Python package management and dependencies. See also line 52.

### Line 66: "Type hints throughout"

Coding standard. Relates to testability (lines 62-63) and code quality. Without this, the model produces untyped Python.

### Line 67: "Google style docstrings"

One consistent documentation format. Without specifying, the model alternates between styles (Sphinx, NumPy, Google, or none). Eliminates variance.

### Line 68: "NOT writing documentation or a book — concise everywhere"

Repeated emphasis on conciseness because earlier Claude models had a serious problem with excessive text production. Related to "Wordiness" in line 61. Applied specifically to Merge Phase docs because documentation-writing triggers the model's verbosity more than code-writing.

---

## Line 71: "Implement ONLY what is explicitly requested"

**[git]** Introduced `cbc34af` (2026-01-31).

**Why "New idea → new plan":** Scope creep is the LLM's natural tendency. The 2026-02-15 planning reflection: "Over-engineering is the default failure mode." Giving scope creep an explicit escape route ("new plan") channels the impulse productively instead of suppressing it.

---

## Line 72: "STOP if not solved by 3 rounds"

**[git]** Introduced `fa73a4d` (2026-02-15). Escalation chain added `215c27b` (2026-02-25).

**Why 3 rounds:** LLMs retry the same failing approach indefinitely, burning tokens without progress. 3 rounds is enough to confirm a problem is not trivially fixable. The escalation chain (IMP → ORC → HC) uses the role system to bring progressively more context to the problem.

---

## Line 73: "Repeated friction or workarounds = wrong direction"

**[inferred]** Added 2026-03-14 based on the "LLMs Think Inside the Box" insight.

**Why:** LLMs do not spontaneously change direction. They accumulate workarounds until the structure collapses. This rule names the signal (repeated friction) and prescribes the action (STOP and evaluate). Without it, the LLM will keep patching.

---

## Line 74: "Document surprises and decisions — the plan is a living document"

**[HC rationale]** The LLM does not have emotions, but it can recognize statistical surprises — when something unexpected happens during implementation. This instruction activates the recognition and recording of those surprises. On Opus 4.0 and Sonnet 4.0 era models, this was particularly important because attention on the process drifted during long implementation sessions. Writing surprises to the plan file anchored the model's awareness.

---

## Line 75: "Update plan task and acceptance criteria status: [/] [x] [+] [-] [>]"

**[predecessor]** Originated from Out-In-Vibe-Flow's strict delegation process. Before TodoWrite existed, progress had to be tracked in files. The markers were the simplest way to track task state in a plan document — without them, the LLM (and the human) lost track of what was done and what remained. `[+]` (discovered and done) and `[-]` (cancelled with reason) and `[>]` (deferred with reason) were added when it became clear that plans always change during implementation — new tasks appear, some become unnecessary. Recording the rationale for cancellations and deferrals prevents the same decisions from being revisited.

**Practical limitation:** The model likely updates these only at the end of a session rather than incrementally. Codex in particular tends to code first (unless TDD is enforced) and only update the plan before returning. This could be verified by examining atomic commits in old worktree branches.

---

## Line 76: "git add new files, git commit -a -m '<minimal description, no co-auth>'"

**[HC rationale]** Exact git commands are specified to eliminate variance. This is not complex enough to warrant a script, and sometimes other git operations are needed alongside these. Since worktree commits get squash-merged, long commit messages serve no purpose. "no co-auth" prevents co-author spam in the squashed commits.

---

## Lines 84-85: Review Phase — cross-check with living plan

**[git]** Introduced `215c27b` (2026-02-25).

**Why "living plan":** The plan is updated during implementation (tasks marked `[x]`, `[+]`, `[-]`, `[>]`). Review must compare against the evolved plan, not the original. The plan captures decisions and surprises that occurred during implementation.

---

## Lines 101-102: Merge — rebase, squash, Linux-style commit

**[incident]** Rebase-in-worktree introduced `58701f5` (2026-01-26). Refined `42e2832` (2026-03-07) after two documented failures:
- imap-stream-mcp v0.7.0: diverged remote roots caused rebase failure
- youtube-to-markdown v2.12.0: worktree branched from old fork point, rebase attempted 100+ already-applied commits

**Why squash merge:** Worktree development creates many small incremental commits. Squash produces one clean commit on main. "Linux-style" refers to kernel convention: descriptive subject line + optional body.

**Why "Run tests on main after merge, before commit":** Added `42e2832` (2026-03-07). v0.7.0 didn't test after squash merge, v2.12.0 did. The rule codified the v2.12.0 approach.

---

## Line 103: Cycle reflection

**[git → incident]** Introduced `215c27b` (2026-02-25). Ownership refined `42e2832` (2026-03-07): IMP writes, ORC delegates.

**Why IMP writes:** HC feedback: the implementing agent has the most accurate knowledge of what happened during implementation. ORC delegates, does not write either reflection type.

**Why the reflection exists:** The process improvement plan `docs/core/plans/2026-03-07-process-improvements-from-reflections.md` was itself driven by reflection evidence from two cycles — demonstrating the feedback loop works. The MathTrainer comparison (2026-03-06) explicitly noted that the competing approach had "Reflections: None."

---

## Lines 108-128: Writing AGENTS.md / CLAUDE.md

**[git]** Entire section introduced `cbc34af` (2026-01-31). Source: `docs/Designing AGENTS.md.md` (164 lines), distilled into CLAUDE.md. The Designing doc was written post-hoc to document existing practices — it is not the original source of the rules.

**Note:** A Feb 2, 2026 review session found fabricated references in the Designing docs ("Meincke et al. (2025)", "Anthropic System Prompt Engineering Guide"). The CLAUDE.md distillation dropped these references. The current `docs/writing-claude-agents-md.md` is the verified replacement.

**Line 108 — Budget <2000 tokens:** From context window economics analysis. System prompt uses ~50 instructions of ~150 effective limit, leaving ~100 for CLAUDE.md.

**Predecessor:** Out-In-Vibe-Flow AGENTS.md had a "META: When Editing This File" section (lines 17-47) with the same insight expressed differently: "Audience: AI agents (token-limited). NOT human documentation." and rules like "Dense > Verbose — Maximum meaning per token", "Commands > Teaching — 'Do X' not 'You should X because...'", "Show > Tell — Example code beats paragraphs." The flow-state Writing section is a distillation of these OIVF meta-rules combined with the `docs/Designing AGENTS.md.md` research (Jan 31, 2026). The OIVF version also had an "Outcome-Driven vs Output-Driven" principle: "Focus on outcomes (what we learn), not outputs (what we produce)" — this did not transfer to flow-state but influenced the acceptance criteria style.

**Line 117 — "Does the LLM actually need this?":** Knowledge ≠ behavior distinction. "Write clean code" = wasted tokens (matches default). "YAGNI + KISS + DRY" = valuable (activates known-but-unfollowed behavior). "Use uv" = valuable (project-specific override).

**Line 119 — "Critical rules at beginning":** Research shows beginning-of-prompt instructions receive stronger attention. As context fills during conversation, middle/end instructions lose attention. Beginning remains stable.

**Line 122 — "Every prohibition needs alternative":** "Don't use pip" leaves the LLM stuck. "Don't use pip, use uv instead" gives a path forward. This rule was itself violated by line 30 until 2026-03-14 when the alternative was added.

**Line 128 — "No code style rules - use linters":** Linters are deterministic. LLM instruction-following is probabilistic. Using tokens for formatting rules that a linter enforces is waste.

---

## Lines 130-139: Writing Skills

**[git]** Source: `docs/Designing Skills.md` (478 lines), distilled `cbc34af` (2026-01-31).

**Line 134 — "Minimize skill, maximize script":** Skills consume context tokens on every invocation. Scripts run externally at zero token cost. Logic in skills = duplicated cost per call. Logic in scripts = one-time execution.

---

## Lines 141-147: Writing MCPs

**[git]** Source: `docs/Designing MCP Servers.md` (279 lines), distilled `cbc34af` (2026-01-31).

**Line 143 — "One tool per domain, 70% token savings":** Measured from imap-stream-mcp. 8 separate tools × ~400 tokens = 3,200 tokens at startup. 1 tool with action routing × ~200 tokens = 200 tokens. Actual saving depends on tool count, but the pattern is validated by the project's own MCP (`use_mail` with 8 actions).

**Line 147 — "Log unknown queries":** From operational experience with `imap-stream-mcp`. The parser encounters unexpected LLM query patterns. Logging these reveals what syntax to support next. Without logging, parser gaps are invisible.

---

## Lines 149-154: Writing CLI Scripts

**[git]** Source: `docs/Designing CLI Tools.md` (501 lines), distilled `cbc34af` (2026-01-31).

**Line 152 — "Errors MUST suggest fix":** Same principle as MCP error messages (`docs/mcp-design-principles.md`). An LLM encountering an error cannot re-read documentation mid-operation. The error message must contain the recovery path.
