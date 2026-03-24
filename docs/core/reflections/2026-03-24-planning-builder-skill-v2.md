# Planning Reflection: Builder-skill v2

## Problems encountered

1. **Started with wrong mental model** — First draft was "add more validation checks" (programmatic thinking). User corrected: skill development is iterative/experimental, not waterfall. You can't program an LLM skill the way you program software.

2. **Symlink direction debate** — Initially proposed builder-skill as source, then reversed on self-review (wrongly claiming symlinks are fragile in git). User corrected: relative symlinks are fine.

3. **Subagent overuse** — Plan proposed subagents for semantic check, minimize, coherence — all under 500 tokens of input. User's principle: most problems are straightforward, don't use subagents when orchestrator can handle it directly.

4. **"Do not use Bash" doesn't work** — Discovered empirically during youtube-to-markdown session. Prohibitions get rationalized away. Explicit Steps (Read → process → Write) work because they leave no gap for the agent to fill with improvised tools.

5. **Variant generation insight** — User pointed out that LLM's first answer is the probability peak (average). Same brief 3 times ≈ same output. Variance requires different perspectives: will/should/might gradient or "3 different approaches". This is a fundamental LLM usage pattern, not just a builder feature.

6. **"Should = more complex" bias** — I equated "should" with "better but more complex". User corrected: should just means less certain, not more complex. Complexity is orthogonal to confidence.

## How resolved

- Rewrote plan around iterative loop (hypothesis → trial → observe → adjust)
- Kept symlinks with original filenames (no rename = no broken references)
- Reduced subagent table to justified cases only (variant generation, heavy analysis)
- Added §6.5 to Designing Skills.md documenting Steps over prohibitions
- Added will/should/might variant strategy with correct definitions

## What was learned about planning

- **Start from the user's mental model, not the tool's capabilities.** User thinks in experiments and iterations. Plan should support that loop, not impose a validation pipeline.
- **Docs as portable assets** — If a skill depends on docs, docs should travel with the skill. Symlinks solve backward compatibility.
- **Prohibition → instruction** is a general pattern. "Don't X" fails for LLMs. "Do Y instead" succeeds. This applies to subagent prompts, skill instructions, and plan constraints.
- **Codex review caught real issues** — rename breaking references, test loop needing harness, validation count inconsistency. Worth the delegation cost.
