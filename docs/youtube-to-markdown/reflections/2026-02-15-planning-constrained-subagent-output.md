# 2026-02-15 Planning Reflection: Constrained Subagent Output

Plan: `docs/youtube-to-markdown/plans/2026-02-15-fire-and-forget-subagents.md`

## How the planning went

Three plan versions in one session. Each killed by testing or HC challenge.

**v1 — Single video_extract.md agent (all Sonnet inline)**. I proposed a new file that merges 4 subskills into one agent, doing all LLM work inline. HC caught two problems: (1) "uses same model for everything" — lost Haiku cost savings, (2) "why can't coordinator isolate context directly?" — forced me to articulate that context is append-only and Task is the only isolation mechanism, but also that isolation wasn't necessary.

**v2 — Background Tasks with status files and polling**. Keep existing subskills, add `run_in_background: true`, poll for status files via Bash. HC said "test it now" — the critical assumption about notification behavior and background task capabilities was untested. Testing revealed: (1) background agents can't use Write tool (auto-denied), (2) notifications are small (~250 chars), and (3) TaskOutput returns only the agent's final message, not the full conversation log.

**v3 — Constrained output instruction (2 lines per prompt)**. Finding #3 collapsed the entire architecture problem into a prompt engineering fix. Two lines added to 7 prompts. No new files, no new infrastructure.

## HC's part

- Challenged over-engineering twice (model diversity loss, unnecessary isolation)
- Brought external advice on subagent patterns (file-based artifacts, constrained output, isolated context)
- Insisted on testing assumptions before finalizing — "test it now, it is an assumption we have to verify now"
- Asked about output format for the constrained message — pushed for informative status on both success and failure paths
- Requested cross-model testing (Haiku + Sonnet) which caught the literal-copying behavior
- Drove the review process via external reviewer, which caught file paths, task count math, insertion anchor contradictions

## My part

- Ran the context analysis (3 background agents) that identified TaskOutput as the dominant consumer
- Proposed and iterated the three plan versions
- Designed and executed the tests (notification behavior, Write permission, TaskOutput content, success/failure cases, cross-model)
- Wrote and revised the plan through self-review and external review
- Updated docs (writing-model-specific-prompts.md, writing-skills.md) with findings
- Added the "test assumptions" rule to CLAUDE.md

## What I learned about planning

1. **Test assumptions during planning, not after.** The assumption "TaskOutput returns the full conversation log" survived two plan versions. One test disproved it and made both plans unnecessary. The cost of three quick tests (~$0.50, 5 minutes) vs implementing v1 or v2 (~hours, ~$10+) is not close.

2. **Over-engineering is the default failure mode.** Each version was more complex than needed. HC's challenges ("why can't the coordinator do this directly?") forced me to question whether the complexity was justified. It wasn't.

3. **External review catches what self-review misses.** I missed the file path issue, the task count math, and the contradictory insertion anchor. Self-review found scope creep (Task 4) and missing risks, but not factual errors in the instructions the implementing agent would follow.

4. **The plan should be writable by a skeptic.** Every claim in the plan was eventually challenged. Having test evidence inline (the results table) made the plan defensible. Claims without evidence ("~30K chars") required caveats.
