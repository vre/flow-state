# Cycle Reflection: CLI Docs Update

Date: 2026-03-22
Role: ORC (planning + implementation + review + merge in single session)

## What happened

Updated `Designing CLI Tools.md` and created `writing-cli-tools.md` based on findings from a browser automation research session. Renamed `mcp-design-principles.md` → `writing-mcp-servers.md` for naming consistency.

## Plan → Implementation

No formal plan — docs update was small enough to do directly. Changes originated from a separate exploratory session (CDP daemon, SPA data extraction, calendar sync) where several general CLI design patterns emerged:
- Daemon pattern for persistent connections
- CLI over MCP for data pipelines
- Idempotent sync with dual-hash (sync-ID + content hash)

## Review Iterations

Three rounds of review caught scope creep:

1. **First review** — found broken section numbers, dead link to nonexistent research doc, missing header in `writing-mcp-servers.md`.

2. **Second review (HC-triggered)** — HC challenged: "why are Chrome M144 flag details in a general CLI design doc?" Removed entire §10 Browser Automation and §10.3 Chrome restrictions. Correct call — these were implementation specifics of one tool, not design principles. Also removed app-specific example code.

3. **Third review (HC-triggered)** — HC challenged: "is the data extraction hierarchy relevant to CLI tool design?" Removed that too. Also cleaned remaining Chrome CDP example from daemon section.

Final diff: 131 additions, 16 deletions. Only general-purpose content survived.

## Root cause of scope creep

I was still in "research documentation" mode from the CDP session when I started writing the CLI docs update. The boundary between "what we learned" and "what belongs in a general design guide" was not clear in my head. Each specific finding felt valuable, but value-to-this-user ≠ value-in-a-general-doc.

## Lessons

- **Exploratory findings ≠ design principles.** Research sessions produce specific knowledge. Design docs teach general patterns. The translation step (specific → general) requires active filtering, not copy-paste with names changed.
- **HC review caught what self-review missed.** I reviewed my own work twice and didn't see the scope creep. HC's "why is this here?" questions were the actual quality gate. Self-review checked correctness within the chosen approach — HC challenged whether the approach was right.
- **Amend over new commit for cleanup.** When review strips content that shouldn't have been committed, amend keeps history clean. Applied here.
- **Single-session small changes don't need full process.** No worktree, no IMP delegation, no plan file. Cherry-pick from feature branch worked cleanly. But the review discipline (skeptic role) was still essential.
