# Writing CLAUDE.md and AGENTS.md

This document explains principles for writing project-level LLM instruction files, with rationale for each practice.

## Context Window Economics

An LLM's context window is a finite resource measured in tokens. Every instruction you add competes with:
- Tool descriptions and their results
- Code files being read
- Conversation history
- The actual task at hand

Token usage typically affects pricing - more tokens in context means higher cost per request. This makes instruction efficiency both a quality and cost concern.

Model capabilities vary significantly. GPT-5.2 (as of 01/2026) shows good recall across the entire context window. Older models may drop to 50% recall for content in the middle of long contexts. This "lost in the middle" effect means instructions can be ignored simply due to their position.

### Instruction Limits

Research indicates frontier LLMs reliably follow ~150-200 instructions with reasonable consistency. Claude Code's system prompt already contains ~50 individual instructions. This leaves roughly 100 instructions for your CLAUDE.md before quality starts to degrade.

Key research findings:
- Smaller models degrade exponentially as instruction count increases
- Larger models show linear decay in instruction-following quality
- Instructions at the beginning of a prompt receive stronger attention
- As context fills up during a conversation, the "end" of your instructions moves further from attention - the beginning remains stable

This is why critical rules should be placed at the beginning of your file.

### The "Does Claude Need This?" Test

Before adding any instruction, ask yourself: does Claude actually need to be told this?

LLMs have been trained on vast amounts of text - most of Western literature, programming documentation, style guides, best practices. But there's a critical distinction: LLMs KNOW things but BEHAVE as they were trained to behave. Knowledge and behavior are not the same.

Claude knows what clean code looks like. But telling Claude "write clean code" doesn't change its behavior - it already tries to do this based on training. Instructions only help when they:
- Override default trained behavior
- Specify project-specific conventions
- Provide information Claude couldn't infer

For example, "write clean code" is wasted tokens. But "use uv instead of pip for Python" is valuable because it's project-specific and overrides what Claude might otherwise choose.

## Two Types of Content

CLAUDE.md files typically contain two different types of content that follow different rules.

### Role/Persona

Role instructions define WHO Claude is in this context. They answer questions like: What expertise does Claude have? What communication style should it use? What values guide its decisions?

Role instructions use declarative form ("You are...") rather than imperative form ("Do..."). Research shows that direct persona assignment ("You are an expert in X") works better than indirect framing ("Imagine you are an expert in X").

Effective role/persona content:
- Groups related traits by concern (identity, communication style, behavioral rules)
- Provides enough detail for Claude to generalize to new situations
- Includes scenario examples showing expected responses
- Uses "FAIL: ..." examples to train Claude away from unwanted behaviors

The "FAIL:" pattern is particularly useful. Instead of just saying "don't be sycophantic," you can show specific phrases to avoid: `FAIL: "Great idea", "You're right", "Good thinking"`. This gives Claude concrete examples to match against.

Research note: Role prompting reliably improves tone, structure, and style of responses. However, it does NOT improve factual accuracy - Claude can still hallucinate regardless of what role it's playing.

### Task Instructions

Task instructions define WHAT Claude should do and HOW. They are operational rules for completing work.

Task instructions use imperative form: "Use X", "Never Y", "Always Z". This is clearer and more direct than descriptive form ("X is used for..." or "We prefer Y").

Effective task instruction practices:

One instruction per line. Each instruction should stand alone and be independently understandable. Don't combine multiple rules into one sentence - this makes them harder to follow and harder to maintain.

Every prohibition needs an alternative. "Don't use pip" leaves Claude stuck when it needs to install packages. "Don't use pip, use uv instead" gives Claude a clear path forward.

Brief inline rationale is OK. "Use uv - prevents dependency conflicts" helps Claude understand when the rule applies. But long explanations waste tokens - put those in separate documentation.

Quantified constraints are clearer. "<10% of original length" is unambiguous. "Short" or "minimal" are vague and lead to inconsistent results.

## Structure

### Critical Rules First

Since instructions at the beginning receive stronger attention, place your most important rules there. Non-negotiable rules like "NEVER START IMPLEMENTATION BEFORE APPROVAL" belong at the very top of the relevant section.

### Simple Markdown

LLMs digest simple markdown effectively. They don't need the visual formatting tricks that help human eyes:
- No emojis for emphasis
- No bold/italic for structure
- No complex table layouts
- Plain bullets and numbered lists work well

For emphasis and structure, use text conventions LLMs parse easily:
- ALL_CAPS for critical emphasis: "NEVER start before approval"
- `<placeholder>` for required values: `<output_directory>`
- `[optional]` for optional parameters: `[--verbose]`
- `{choice|choice}` for alternatives: `{json|yaml}`

The CLAUDE.md file is primarily for LLM consumption. Save visual formatting for human-facing documentation.

### Bullets Over Tables

Tables require parsing to extract information. Bullets are direct and scannable. For LLM consumption, prefer:

```
- Use uv for python: uv sync --dev
- Run tests with: pytest
```

Over:

```
| Tool | Command |
|------|---------|
| uv   | uv sync --dev |
| pytest | pytest |
```

### No Chained References

When you reference another file, Claude has to read that file to get the information. If that file references yet another file, you've created a chain that wastes tokens and can lose context.

Bad pattern:
```
See docs/setup.md for configuration details
```
(And setup.md says "See docs/advanced-config.md for more options")

Good pattern:
```
For FooBarError troubleshooting, read docs/troubleshooting.md section 3
```

Tell Claude:
1. What specific file to read
2. When to read it (the trigger condition)
3. What section or information to look for

## Anti-patterns

### Too Many Instructions

If your CLAUDE.md exceeds ~100 instructions, Claude's ability to follow all of them degrades. You'll see inconsistent behavior as some instructions get "forgotten."

Solution: Prioritize ruthlessly. Move less critical guidance to separate files that Claude reads only when relevant.

### Obvious Instructions

Don't tell Claude what it already knows from training:
- "Write clean, readable code"
- "Use meaningful variable names"
- "Handle errors appropriately"
- "Follow best practices"

These waste tokens and add noise that dilutes your important project-specific instructions.

### Contradictory Traits

Conflicting instructions confuse the model:
- "Be concise" + "Provide detailed explanations"
- "Move fast" + "Be thorough and careful"
- "Be direct" + "Be diplomatic and gentle"

If you need context-dependent behavior, be explicit about when each mode applies.

### Negative-Only Constraints

"Never use the --force flag" leaves Claude stuck when it thinks --force is needed. Always provide an alternative:

"Don't use --force, use --force-with-lease instead"

### Auto-generated Content

The `/init` command creates generic CLAUDE.md content. This is a starting point, not a finished product. Replace generic content with project-specific instructions that actually add value.

## References

- [Writing a good CLAUDE.md | HumanLayer](https://www.humanlayer.dev/blog/writing-a-good-claude-md) - Detailed analysis of instruction limits and best practices
- [Keep Claude in character | Anthropic](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/keep-claude-in-character) - Official guidance on role prompting
- [Role Prompting | LearnPrompting](https://learnprompting.org/docs/advanced/zero_shot/role_prompting) - Research on persona effectiveness
