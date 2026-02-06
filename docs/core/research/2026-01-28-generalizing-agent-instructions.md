# Notes on Generalizing Claude Instructions (2026-01-28)

This document analyzes how current Claude-specific instructions (`AGENTS.md`, `mcp-design-principles.md`, etc.) can be generalized to apply to all LLM agents.

The premise is that although the terminology is Claude-specific, **the problems and solutions are rooted in LLM architecture fundamentals** that apply to virtually all current models (GPT-4, Gemini, Llama, Claude).

## 1. Shared Fundamentals (Universal Truths)

These apply to all agents regardless of model. Documentation should be built on these.

*   **Token Economics (Context Window Economics):**
    *   All models have a limited and "expensive" (in cost or quality) context window.
    *   **Principle:** "The less noise in the context, the better the agent performs." This is universal.
    *   *Implication:* The `AGENTS.md` rules about conciseness are not a style choice but a technical necessity.

% Good.

*   **Attention Mechanism:**
    *   "Lost in the middle" phenomenon and beginning/end bias apply to all transformer-based models.
    *   **Principle:** Critical instructions go first. Don't chain references (because the model "forgets" the path).
    *   *Implication:* Instruction structuring (Critical Rules First) is a universally applicable best practice.

% There was a new GPT-5.2 research result where attention stays close to 100% regardless of context size.

*   **Cognitive Load and Tools:**
    *   Models are not computers but "reasoning engines". They make mistakes when tools are too complex or error messages cryptic.
    *   **Principle:** "Fail-fast with guidance" (Error -> Explanation -> Fix suggestion) is the only way an agent can recover from errors autonomously.

% Important, and especially when building skills etc., learning loops should be leveraged. A good principle is that the LLM should be able to test its own creations, perhaps instrumented.
% https://github.com/obra/superpowers/tree/main/skills/writing-skills contains some good ideas, but in my opinion the skills within this superpowers package are somewhat bloated.
% This may relate to the fact that an LLM can't necessarily write instructions for itself well, because they're generally not trained to do so. However, LLMs are capable of reflection cycles, and with instructions they can be guided to try e.g. context-efficient yet sufficiently precise instructions for the next action.

*   **MCP vs. Script Evolution:**
    *   MCP can also be "condensed". Initially there can be atomic tools (`list`, `read`, `filter`). When recurring chains are observed, these can be coded into new higher-level MCP tools (`search_and_summarize`).
    *   This is safer than letting the LLM write ad-hoc Python scripts on the fly, because MCP code is (hopefully) human-tested and versioned.
    *   Ad-hoc scripting is "zero-shot coding" - there's always a bug risk, even though execution is deterministic.
    *   **Development cycle:** Atomic MCP Tools -> Observe Usage Patterns -> Compound MCP Tools.

## 2. What Is Different / Claude-Specific?

These parts require abstraction or modification for generalization.

*   **Terminology and Filenames:**
    *   `CLAUDE.md` -> `SYSTEM_PROMPT.md` or `AGENT_INSTRUCTIONS.md`.
    *   `MCP` (Model Context Protocol) -> `Tool Definition` or `Tool Interface`. Although MCP aims to be a standard, it's still strongly Anthropic-branded. However, the principles (one tool vs. many endpoints) are universally applicable.
    *   "Claude" -> "The Agent", "The Model", "The Assistant".

% We use AGENTS.md and CLAUDE.md here. System prompt generally can't be tuned directly.
% MCP is a standard in this case. This happened after your training cutoff date.
% Should "LLM" be used instead of "Claude"?

*   **Model Capability Variance:**
    *   Documents reference e.g. Claude 3.5 Sonnet's ability to follow 150-200 instructions.
    *   *Generalization:* Different models have different "Instruction Adherence" thresholds. Smaller models (e.g. Llama 8B) require simpler and fewer instructions than frontier models. Documentation should mention that instruction count must be proportional to model size.

% Talking about instruction adherence as a generalization is probably good. Could provide scale and perspective relative to how recent the model is and what techniques are built into it.

*   **Tool Calling Interface:**
    *   OpenAI's "Functions", Anthropic's "Tools", and open-source solutions operate with slightly different logic (e.g. JSON schema vs. XML).
    *   *Generalization:* Focus on *semantics* (how a tool is described) not *syntax* (in what format it's sent).

% MCP uses RPC-JSON for tool calling. There are no other options here. But generally, different AI models do call their tools differently, and different AI models and different editors where models are used have different tools. This shows e.g. when using models via API directly in Roo Code, Kiro, etc. rather than in the AI maker's own tool for which the model is most likely trained.

## 3. Document-by-Document Analysis

### `AGENTS.md` (The Rules)
This is "The Manifesto". It's surprisingly universal because it describes *ways of working* rather than technology.
*   **Important:** "Communication Rules" and "Implementation Approach" are pure gold for any agent. They prevent hallucination and "looping".
*   **To change:**
    *   References to `CLAUDE.md` and `AGENTS.md` in titles.
    *   Commands like `claude -p` or `/init`. These should be replaced with generic `run-agent` or `initialize-project` terms.

% Why would you remove AGENTS.md and CLAUDE.md from the title - these are exactly the artifacts this section applies to.

### `docs/writing-claude-agents-md.md` (The Explanation)
This explains *why* the rules exist.
*   **Core:** "The 'Does Claude Need This?' Test" is excellent, but should be "Does The Model Need This?".
*   **Missing:** Mention that weaker models need more "hand-holding" (few-shot examples) than strong models that understand plain descriptions (zero-shot).
*   **Irrelevant:** Claude Code product-specific constraints (e.g. the exact ~50 instruction system prompt).

% Yes, remove Claude. Adding hand-holding guidance is also a good addition as described. Remove that specific constraint if it's been addressed elsewhere.

### `docs/mcp-design-principles.md` (The Tools)
This is the most technical and perhaps most valuable document to generalize.
*   **Core:** "Atomic vs Compound" and "Help Action - Progressive Documentation". These solve the context problem on all platforms.
*   **Especially important:** The idea that an API should return a *fix suggestion* in error messages, not just an error code. This is vital for all autonomous agents.

% I'm thinking this could also discuss when to use a skill+script combination versus building an MCP server. A script can be wrapped in e.g. a Python script that the LLM builds around it and perhaps other tools to improve efficiency and determinism.
% As I understand it, MCP cannot be wrapped into a script this way - the LLM uses it and reads from it directly through the environment like VS Code, Copilot-CLI, Opencode, etc. This then means the LLM has to think through parsing, looping, etc. itself, which e.g. Python can do automatically. The LLM has to consider after each return value what to query next. -> More thinking tokens and error possibilities if something is forgotten. And the smaller the model, the more likely things go wrong. E.g. about Claude's Haiku it's been said that it hallucinates and makes errors so much that it's not worth using because it actually costs more. Similar things have been said about Opus vs Sonnet.
% Additionally, even though MCP is getting dynamic loading / discovery for different tools, is it really sensible to run everything as MCP? Especially since MCP is quite "always-on", but skill + script can be run and loaded on demand.
% Is MCP's biggest need when e.g. some kind of user session is needed, login has latency or some other "cost", or ..? You can look for boundary conditions for this.

### `docs/writing-skills.md` (The Workflows)
*   **Core:** Moving logic to scripts away from prompts ("Minimize Skill, Maximize Script"). This saves tokens and makes behavior deterministic.
*   **To change:** The term "Skill" is quite specific. "Workflow" or "Task Definition" could be more general.

% Here too things have progressed. Skills are now a standard and are included in e.g. GitHub Copilot etc. Anthropic has just been ahead on these.

## 4. Proposal for a Universal Structure

If you want to make this "The Universal Guide to LLM Agents", I propose the following structure:

1.  **Core Philosophy (Foundation)**
    *   The agent is a colleague, not a search engine.
    *   Context is expensive -> Optimize everything.
    *   Determinism in code, reasoning in the model.

2.  **Instruction Engineering (ex-CLAUDE.md)**
    *   How to write a "System Prompt" for a project.
    *   Persona vs. Task instructions.
    *   Prioritization (Critical first).

3.  **Tool Design Patterns (ex-MCP Principles)**
    *   Designing APIs for Machines.
    *   The "String to Pull" pattern (Progressive context loading).
    *   Recoverable Errors.

4.  **Workflow Definitions (ex-Skills)**
    *   How to define multi-step tasks.
    *   Sub-agents & delegation.

% Would this be a general guide in DEVELOPMENT.md with references to sub-guides?

## Missing Piece: Evaluation

One thing that's missing is **Evaluation**. How to measure whether a generic instruction works? The Claude documents assume "it works if Claude obeys". In a general model there should be a chapter: "How to test your agent instructions across models".

% This circles back to what was mentioned above about learning loops and self-testing.

## 5. Market Overview and Standards (July 2025 - January 2026)

Recent research (conducted 2026-01-29) shows significant consolidation and standardization:

*   **AGENTS.md has won:**
    *   `AGENTS.md` (plural) has risen as the de-facto standard, displacing `CLAUDE.md` and `AGENT.md`.
    *   Supporters include OpenAI Codex, Google Jules, Roo Code, Cursor, Zed.
    *   **Conclusion:** `AGENTS.md` is adopted as the primary standard (as previously discussed). `CLAUDE.md` is retained alongside as a secondary file/support.

*   **MCP Evolution (v2026):**
    *   **MCP Apps (Jan 2026):** New extension enables interactive UI components within conversations. This transforms a "text-based" tool into an "application".
    *   **Streamable HTTP:** Replaces Server-Sent Events (SSE) for heavy usage.
    *   **Foundation governance:** MCP has been transferred to the Linux Foundation's "Agentic AI Foundation". It's no longer just an Anthropic project.

*   **Persuasion Principles:**
    *   Research (Meincke et al. 2025) shows that LLMs respond to human-like influence techniques (Authority, Commitment, Social Proof).
    *   E.g. "YOU MUST" and "No exceptions" work better than polite requests when ensuring rule compliance.
    *   This supports the idea of "Critical rules first and in imperative form".
