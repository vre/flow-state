# Writing Model-Specific Prompts

This document explains how prompt structure should differ across Claude model sizes, with rationale and references.

## Why Model Size Matters

Larger models (Opus, Sonnet) tolerate ambiguity, infer intent, and self-correct. Smaller models (Haiku) need tighter constraints — they match instructions more literally and lose context faster. A prompt that works on Opus may produce inconsistent output on Haiku.

The practical consequence: when delegating subtasks to Haiku, your prompt needs different structure than what you'd write for Opus orchestration.

## Haiku Prompts

Haiku excels at classification, extraction, formatting, and batch processing. It fails at planning, multi-step reasoning, and long sessions [5]. Use it for execution, not thinking.

### Structure

Put critical instructions in the first 200 tokens. Attention decays faster in small models than large ones [2].

Use XML tags to separate prompt sections:

```xml
<instructions>
What to do, constraints, goal.
</instructions>

<output_format>
Exact schema with 1-2 examples.
</output_format>

<context>
Input data.
</context>
```

Without XML tags, Haiku mixes up instructions and input data. Claude is fine-tuned to pay attention to XML tag boundaries [1].

### Rules for Haiku Prompts

- **Motivate rules**: "Skip URLs because they don't describe video content" — Haiku generalizes from explanations better than from bare imperatives [2]
- **Positive phrasing**: "Write plain text" not "Don't use markdown" — negative instructions are followed less reliably [2]
- **Strict output schema**: Specify exact format with example. "Format nicely" produces inconsistent results across calls
- **1-2 examples**: Diminishing returns past 2, and each example costs tokens [6]
- **Batch, don't loop**: Process all items in one call rather than one per call [6]
- **No aggressive language**: `CRITICAL`, `YOU MUST` cause overtriggering on Haiku — it's more eager than Opus. Use neutral phrasing: "Use X when Y" [2]
- **Short tasks**: Haiku drifts in long sessions — forgets variable names, changes class names. Keep each task completable in a short context [5]

### What Haiku Fails At

These should be routed to Sonnet/Opus instead:

- Deep planning and architecture decisions [5]
- Multi-step debugging with cascading dependencies [5]
- Sustained context tracking across many files [5]
- Tasks requiring coherent state across a long session [2]

## Constrained Output for Subagents

When subagents write results to files, their final text message is the only content returned to the coordinator via TaskOutput [9]. Unconstrained agents produce verbose final messages — confirmations, content echoing, reasoning summaries — bloating coordinator context by ~30K chars per call [10].

Add a constrained output instruction to every subagent prompt:

```
Do not output text during execution — only make tool calls.
Your final message must be ONLY one of:
  {step}: wrote {output_file} [optional metadata]
  {step}: FAIL - {what went wrong}
```

This reduces TaskOutput from ~30K to ~40-130 chars per call [11]. Tested with both Sonnet and Haiku (2026-02-15).

### Model differences in constraint following

Haiku copies instruction formatting literally [12]. A dash-list format like:
```
- Success: summarize: wrote file.md [TYPE]
- Failure: summarize: FAIL - reason
```
produces `Success: summarize: wrote file.md` — Haiku includes the label prefix. Use plain indented format without labels to avoid this.

Sonnet interprets the list as choices and picks the correct branch without copying labels.

Both models reliably suppress intermediate text output when instructed [12].

## Sonnet and Opus Prompts

Larger models handle ambiguity, parse unstructured prompts, and maintain state across long conversations. Key differences from Haiku:

- XML tags helpful but not critical
- Handles negative instructions correctly
- Plans and reasons multi-step without losing track
- Opus supports `effort` parameter for controlling reasoning depth [7]

Use for orchestration, planning, code review, and complex reasoning.

## Orchestration Pattern

When combining models, the recommended pattern [3] [4], validated by MIT research [8]:

```
Opus/Sonnet: plan → break into subtasks → validate results
Haiku: execute subtasks in parallel, short context each
```

This outperforms single-model approaches because each model operates in its strength zone.

## References

[1]: https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags "XML tags in prompts"
[2]: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices "Claude prompting best practices"
[3]: https://caylent.com/blog/claude-haiku-4-5-deep-dive-cost-capabilities-and-the-multi-agent-opportunity "Claude Haiku 4.5 deep dive"
[4]: https://www.anthropic.com/news/claude-haiku-4-5 "Introducing Claude Haiku 4.5"
[5]: https://medium.com/@ayaanhaider.dev/sonnet-4-5-vs-haiku-4-5-vs-opus-4-1-which-claude-model-actually-works-best-in-real-projects-7183c0dc2249 "Sonnet vs Haiku vs Opus comparison"
[6]: https://portkey.ai/blog/optimize-token-efficiency-in-prompts/ "Optimize token efficiency"
[7]: https://platform.claude.com/docs/en/build-with-claude/effort "Effort parameter"
[8]: https://news.mit.edu/2025/enabling-small-language-models-solve-complex-reasoning-tasks-1212 "MIT DisCIPL: small models solve complex tasks"
[9]: https://github.com/anthropics/claude-code/issues/16789 "TaskOutput returns final result text"
[10]: https://www.richsnapp.com/article/2025/10-05-context-management-with-subagents-in-claude-code "Context management with subagents"
[11]: Empirical finding, youtube-to-markdown context analysis, session f3ce1cae, 2026-02-15
[12]: Empirical finding, youtube-to-markdown testing, 2026-02-15
