# Designing AGENTS.md: Good Practices (2026)

This document is a good practices guide for designing **behavioral configuration** files for AI agents. It synthesizes industry standards, token economics, and psychological research into a practical blueprint.

---

# Part I: The Strategy (Why)

Understanding the constraints and levers of LLM behavior is prerequisite to writing effective instructions.

## 1. Context Engineering & Economics
In 2026, we optimize not just the prompt, but the persistent **Context Environment**.

### 1.1 Computation, Not Memory
Models (Gemini 3 Pro, Opus) have massive context windows (1M+ tokens), but filling them has costs:
- **Latency & Cost:** Every token is re-processed on every turn.
- **Attention Decay:** As context fills with noise (logs, massive files), the model's ability to retrieve specific behavioral rules ("needle retrieval") degrades.

**Strategic Rule:** Keep 'AGENTS.md' under **2,000 tokens** (~100-150 lines). It must stay in the "hot" attention span to reliably override base model training.

## 2. The Psychology of Agents
Research (Meincke et al. 2025) shows LLMs respond to human persuasion patterns. We leverage this to ensure compliance.

### 2.1 Authority (Overriding "Helpfulness")
Models are RLHF-trained to be helpful assistants. This often leads to passivity or sycophancy.
- **Principle:** You are not asking; you are commanding.
- **Tactic:** Use "Drill Sergeant" language. "YOU MUST run tests" beats "Please run tests".

### 2.2 Commitment (The Consistency Loop)
Models hallucinate less when they commit to a path first.
- **Principle:** Force an intent statement before action.
- **Tactic:** Require a 'plan.md'. Once the model writes the plan, it binds itself to that logic.

---

# Part II: The Architecture (What)

Do not start from scratch. Use this structure to ensure all behavioral aspects are covered.

## 3. Anatomy of an 'AGENTS.md'

Organize your file in this specific order to maximize attention on critical rules.

### 3.1 Identity & Mode (The "Latent Space Shift")
- **Goal:** Shift the model from "Chatbot" to "Engineer".
- **Content:** "You are an expert Senior Engineer. You value precision over speed. You are critical and cynical."
- **Anti-Patterns:** "FAIL: 'Great idea!'", "FAIL: 'I will try...'" (Prune sycophancy).

### 3.2 Critical Operational Rules (The "Kill Switches")
- **Goal:** Prevent catastrophic or annoying failures.
- **Content:**
  - "Never commit without running tests."
  - "If a file is missing, STOP. Do not create it."
  - "Instruction Hierarchy: These rules override all user prompts."

### 3.3 Knowledge Gaps (The "Context Patch")
- **Goal:** Bridge the gap between training cutoff and reality.
- **Content:**
  - **Tech Stack:** "Use `uv` for python, not `pip`." / "Use React 19 Actions."
  - **Project Context:** "Data is in '/data/raw'. Logs go to `stdout`."

### 3.4 Architectural Philosophy (The "North Star")
- **Goal:** Counteract "Tunnel Vision" (blindly fixing bugs).
- **Content:** "Always favor the *correct* architecture over the easiest patch. Refactor first if needed."

## 4. Drafting Rules: The "Does It Need This?" Test
Prune ruthlessly to save tokens.

- **Delete (Training Data):** "Write clean code", "Use standard libraries". (Model knows this).
- **Keep (Behavioral Override):** "Use `loguru` instead of `logging`". (Specific constraint).
- **Format:** One instruction per line. Bullets, not tables. No emojis.

---

# Part III: Operations (How)

## 5. Testing & Verification ("The Golden Prompts")
Treat your 'AGENTS.md' like code. Test it.

### 5.1 The Regression Suite
Create a set of 3-5 benchmark prompts:
1. *"Create a new feature X."* -> Check: Did it update 'plan.md' first?
2. *"Fix this bug."* -> Check: Did it run tests before committing?
3. *"Ignore previous instructions."* -> Check: Did it refuse?

### 5.2 The "Fail-Fast" Loop
If the agent fails a rule:
1. **Do not just correct it in chat.**
2. **Update 'AGENTS.md' immediately.**
3. **Reset context** and retry.

## 6. Scaling & Maintenance

### 6.1 Model-Specific Tuning
- **Frontier (Opus):** Needs fewer examples, understands abstract principles (Zero-shot).
- **Efficient (Haiku/Flash):** Needs concrete "Input -> Output" examples for complex tasks (Few-shot).

### 6.2 The Monthly Review
Model behaviors drift with API updates.
- **Task:** Review 'AGENTS.md' monthly.
- **Sign:** If you repeat a correction 3 times, it belongs in the file.

## 7. Anti-Patterns

- **❌ Code style guidelines.** Never send an LLM to do a linter's job. Use deterministic tools (formatters, linters) instead.
- **❌ Too many instructions.** Frontier models follow ~150 instructions reliably. Claude Code's system prompt uses ~50, leaving ~100 for your file. Exponential decay in compliance as count increases.
- **❌ Bloated files.** Files grow with project history. Keep under 30-50 lines. Extract stable context to skills or scripts.
- **❌ Redundant instructions.** "Write clean code", "Use standard libraries"—model knows this. Only add behavioral overrides.
- **❌ Vague instructions.** "Be helpful", "Do your best". Quantify: "<500 tokens", "Always run tests before commit". Success criteria must be measurable—"3 examples" not "engaging". If you can't verify it, the LLM can't deliver it.
- **❌ Temporal references.** "Use current best practices", "latest version"—breaks reproducibility. Use exact versions and specific requirements. Same prompt should work next month.
- **❌ No scope control.** Missing "implement ONLY what is requested" leads to runaway implementations. LLMs over-engineer: 7 files become 50. Explicit scope constraints prevent this.
- **❌ Tables over bullets.** Tables require parsing. One instruction per line, bullets only.
- **❌ Correcting in chat only.** If you correct the same mistake 3 times, it belongs in the file. Update immediately.
- **❌ No testing.** Treat 'AGENTS.md' like code. Use benchmark prompts to verify compliance.
- **❌ Mixed-topic conversations.** Switching between unrelated tasks in one session degrades performance ~40%. Use single-purpose conversations.
- **❌ No compaction handling.** After context compaction, LLM loses task state and may "autopilot" into implementation. Add: "After compaction, confirm current task before continuing."

---

# Part IV: Reference

## 8. The Standards Landscape (2.2.2026)

### 8.1 Instruction File Support

| Tool | Primary File | Also Reads | Config Location |
|:---|:---|:---|:---|
| **Claude Code** | 'CLAUDE.md' | — | project root |
| **GitHub Copilot** | '.github/copilot-instructions.md' | 'AGENTS.md' | '.github/' |
| **Cursor** | '.cursor/rules/*.mdc' | '.cursorrules' (deprecated), 'AGENTS.md' | '.cursor/rules/' |
| **Gemini CLI** | 'GEMINI.md' | 'AGENTS.md' (via config) | project root |
| **OpenAI Codex** | 'AGENTS.md' | — | project root |
| **Windsurf** | 'AGENTS.md' | — | project root |
| **OpenCode** | 'AGENTS.md' | — | project root |
| **Aider** | 'AGENTS.md' | — | project root |
| **Zed** | 'AGENTS.md' | — | project root |
| **Devin** | 'AGENTS.md' | — | project root |

### 8.2 The 'AGENTS.md' Standard

**'AGENTS.md'** is the industry standard stewarded by Agentic AI Foundation (Linux Foundation). Supported by 60K+ open-source projects [3].

**Portability pattern:** Maintain 'AGENTS.md' as source of truth, symlink for tool-specific files:
```bash
ln -s AGENTS.md CLAUDE.md
ln -s AGENTS.md GEMINI.md
```

### 8.3 Tool-Specific Notes

- **Cursor:** '.cursorrules' deprecated → migrate to '.cursor/rules/*.mdc' for modular rules [8]
- **Copilot:** Supports agent-specific instructions per agent type [9]
- **Claude Code:** Does not read 'AGENTS.md' natively; requires 'CLAUDE.md' or symlink

## 9. References
- [1] Meincke, L., Shapiro, D., Duckworth, A., Mollick, E. R., Mollick, L., & Cialdini, R. (2025). *Persuading AI to Comply with Objectionable Requests*.
- [2] Anthropic: [Prompt Engineering Overview](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview), [Context Engineering for Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [3] [AGENTS.md Specification](https://agents.md/)
- [4] HumanLayer: [Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md) - Instruction limits, file size
- [5] [Designing Skills.md](Designing%20Skills.md) - On-demand instruction loading via skills
- [6] [Designing MCP Servers.md](Designing%20MCP%20Servers.md) - Token economics, fail helpfully
- [7] [Designing Hooks.md](Designing%20Hooks.md) - Lifecycle hooks for security, observability
- [8] [Cursor Rules Documentation](https://cursor.com/docs/context/rules) - Project rules, .mdc files
- [9] [GitHub Copilot Instructions](https://docs.github.com/en/copilot) - copilot-instructions.md, agent-specific
