# Designing Hooks: Good Practices (2026)

> **Deep reference.** This document explains the *why* behind hook design decisions with full rationale and references. No separate condensed guide exists — hooks are configured in `settings.json`, not in CLAUDE.md.

This document outlines principles for designing lifecycle hooks in AI coding agents.

Hooks are user-defined commands that execute automatically at specific points in an agent's lifecycle. They're supported across major platforms: Claude Code [1], GitHub Copilot [2], Cursor [3], OpenCode [4], and others.

---

# Part I: The Strategy (Why)

## 1. The Control Gap

AI agents execute autonomously. Without hooks, you have two options:
- **Full trust:** Agent runs everything, you review after
- **Constant approval:** Agent asks permission for every action

Hooks provide a third option: **programmatic control**. Define rules once, enforce automatically. The demand is clear [5].

## 2. Use Cases

| Category | Hook Type | Example |
|:---|:---|:---|
| **Security** | PreToolUse | Block `rm -rf`, validate paths |
| **Quality** | PostToolUse | Run formatter after edits |
| **Observability** | All | Log actions for audit trail |
| **Notifications** | SessionEnd, Stop | Play sound, send Slack message |
| **Context** | SessionStart | Load project-specific environment |
| **Guardrails** | PreToolUse | Require approval for destructive ops |

## 3. The Hook Lifecycle

```
SessionStart → [UserPrompt → PreToolUse → Tool → PostToolUse]* → SessionEnd
                    ↑                                      |
                    └──────────── loop ────────────────────┘
```

**Three lifecycle stages:**
1. **Session:** Start, end, resume
2. **Tool:** Before execution (can block), after execution (can log/modify)
3. **Message:** User prompt submitted, before/after LLM call

---

# Part II: The Architecture (What)

## 4. Cross-Platform Hook Types (2.2.2026)

Hook patterns appear across frameworks [6] [7]:

| Event | Claude Code | Copilot | Cursor | OpenCode |
|:---|:---|:---|:---|:---|
| Session start | ✓ | sessionStart | ✓ | ✓ |
| Session end | ✓ | sessionEnd | ✓ | ✓ |
| Pre-tool | PreToolUse | preToolUse | ✓ | tool.execute.before |
| Post-tool | PostToolUse | — | ✓ | tool.execute.after |
| User prompt | — | userPromptSubmitted | — | chat.message |
| Subagent stop | SubagentStop | — | — | — |

**Most powerful hook:** PreToolUse — can approve, deny, or modify tool executions before they happen.

## 5. Hook Configuration Patterns

### 5.1 Claude Code (JSON in settings)
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash",
      "hooks": [{
        "type": "command",
        "command": "./scripts/validate-bash.sh"
      }]
    }]
  }
}
```

### 5.2 GitHub Copilot (JSON files)
```
.github/hooks/
├── security.json      # PreToolUse validation
└── notifications.json # SessionEnd alerts
```

### 5.3 OpenCode (Plugin files)
```
.opencode/plugin/
└── security-hooks.ts  # TypeScript event handlers
```

## 6. Hook Input/Output

Hooks receive JSON context about the event:

```json
{
  "event": "PreToolUse",
  "tool": "Bash",
  "input": {
    "command": "rm -rf /tmp/cache"
  },
  "session_id": "abc123"
}
```

Hook response controls behavior:
- **Exit 0:** Approve (continue)
- **Exit non-zero:** Deny (block action)
- **stdout JSON:** Modify the action

---

# Part III: Operations (How)

## 7. Common Hook Implementations

### 7.1 Security: Block Dangerous Commands
```bash
#!/bin/bash
# validate-bash.sh - PreToolUse hook
command="$1"

# Block dangerous patterns
if echo "$command" | grep -qE 'rm -rf|sudo|chmod 777'; then
  echo "Blocked: dangerous command pattern" >&2
  exit 1
fi
exit 0
```

### 7.2 Quality: Auto-format After Edits
```bash
#!/bin/bash
# format-on-edit.sh - PostToolUse hook for Edit tool
file="$1"

# Run formatter based on file type
case "$file" in
  *.py) ruff format "$file" ;;
  *.ts|*.js) prettier --write "$file" ;;
  *.go) gofmt -w "$file" ;;
esac
```

### 7.3 Observability: Log All Actions
```bash
#!/bin/bash
# log-action.sh - PostToolUse hook
echo "$(date -Iseconds) | $HOOK_EVENT | $HOOK_TOOL | $HOOK_SESSION" >> ~/.agent-audit.log
```

### 7.4 Notifications: Sound on Complete
```bash
#!/bin/bash
# notify-done.sh - SessionEnd or Stop hook
afplay /System/Library/Sounds/Glass.aiff  # macOS
# or: paplay /usr/share/sounds/... # Linux
```

## 8. Anti-Patterns

- **❌ Blocking hooks that timeout.** Agent hangs. Set timeouts, fail open if needed.
- **❌ Hooks that modify too much.** Confuses the agent about what actually happened.
- **❌ No error handling.** Hook crash = agent crash. Always handle errors gracefully.
- **❌ Secrets in hook scripts.** Use environment variables, not hardcoded values.
- **❌ Heavy computation in PreToolUse.** Slows every action. Keep hooks fast (<100ms).
- **❌ Hooks without logging.** When something breaks, you need the audit trail.
- **❌ Platform-specific assumptions.** Test hooks on all platforms you deploy to.

## 9. Testing Hooks

Treat hooks like code:

1. **Unit test:** Run hook script directly with sample JSON input
2. **Integration test:** Trigger hook via agent action, verify behavior
3. **Failure test:** Ensure hook failures don't crash the agent

```bash
# Test a PreToolUse hook
echo '{"tool":"Bash","input":{"command":"rm -rf /"}}' | ./validate-bash.sh
# Should exit non-zero
```

---

# Part IV: Reference

## 10. When to Use Hooks

| Situation | Hook? | Alternative |
|:---|:---|:---|
| Block dangerous commands | ✓ PreToolUse | — |
| Auto-format code | ✓ PostToolUse | Pre-commit hooks |
| Log for compliance | ✓ All events | External monitoring |
| Inject context | ✓ SessionStart | AGENTS.md instructions [9] |
| Enforce coding standards | Maybe | Linters (deterministic) |
| Complex workflows | No | Skills (more control) [8] |

**Rule:** Use hooks for cross-cutting concerns that apply to all agent actions. Use skills [8] for task-specific workflows.

## 11. References

[1]: https://code.claude.com/docs/en/hooks "Claude Code Hooks Documentation"
[2]: https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-hooks "GitHub Copilot: About Hooks"
[3]: https://www.infoq.com/news/2025/10/cursor-hooks/ "Cursor 1.7 Hooks Announcement"
[4]: https://opencode.ai/docs/plugins/ "OpenCode Plugins"
[5]: https://github.com/openai/codex/issues/2109 "OpenAI Codex Event Hooks Issue #2109"
[6]: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/ "Strands Agents Hooks"
[7]: https://medium.com/@abdulkabirlive1/customize-ai-agent-behavior-with-hooks-in-openai-agents-sdk-05270e590cbe "OpenAI Agents SDK Hooks"
[8]: Designing%20Skills.md "Designing Skills.md"
[9]: Designing%20AGENTS.md.md "Designing AGENTS.md.md"
