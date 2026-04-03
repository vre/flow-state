# TODO

## Hooks integration

- `references/Designing Hooks.md` exists but is not referenced from SKILL.md or generator
- Scaffold creates empty `.claude/settings.json` (`{}`) — could include hook stubs for common patterns:
  - PostToolUse: run formatter after file edits
  - SessionStart: load project environment
  - PreToolUse: guardrails for destructive operations
- SKILL.md Step 3 (fill template files) should ask: "Which hook patterns?" and populate `.claude/settings.json`
- See `references/Designing Hooks.md` for patterns and rationale
