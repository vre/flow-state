# Session Claude Skill

Delegates tasks to a nested Claude Code CLI with session persistence. Two modes: direct (review/analysis) and worktree (implementation with sandbox).

## The problem

Claude Code blocks nested sessions (`CLAUDECODE` env var). Non-interactive mode (`-p`) needs explicit permission and sandbox config since there's no human to approve prompts.

## The solution: two modes

### Direct (`--permission-mode acceptEdits`)

For review, analysis, quick edits. Auto-approves file edits, blocks Bash silently. Safe for read-heavy tasks.

### Worktree (sandbox + `dontAsk` + profiles)

For writing code, running tests, committing. Uses kernel-level sandbox (Seatbelt on macOS, bubblewrap on Linux) restricting writes to git repo root. `autoAllowBashIfSandboxed` allows all Bash within sandbox — no need for fine-grained `allowedTools` on Bash commands.

## Why not fine-grained Bash allowlisting?

Allowing `Bash(npm run test*)` or `Bash(pytest *)` is security theater. Claude can edit `package.json` / `conftest.py` to run arbitrary code through those tools. The sandbox is the real security boundary. Source: [Formal security analysis][1].

## Settings profiles

Three profiles, differing only in network access:

| Profile | Network | Use case |
|---------|---------|----------|
| **code** | None | Git, edit, pure function tests |
| **test** | localhost binding | Dev servers, browser tests, playwright |
| **e2e** | localhost + external domains | API integration, package registries |

All profiles share: `sandbox.enabled`, `autoAllowBashIfSandboxed`, `allowUnsandboxedCommands: false`.

## Sandbox details (tested)

| Action | Result |
|---|---|
| Write file in worktree | Allowed |
| `git add` + `git commit` | Allowed |
| Write elsewhere in repo | Allowed (boundary = repo root) |
| Write outside repo (`/tmp/`) | **Blocked** — `operation not permitted` |
| Start localhost server (port bind) | Allowed (with `allowLocalBinding: true`) |
| HTTP request to localhost | Allowed |

## Nesting guard

Claude Code refuses nested sessions. Workaround: `unset CLAUDECODE` before launch. Prompts piped via stdin to avoid shell quoting issues.

## Comparison with session-codex

| | session-codex | session-claude |
|---|---|---|
| CLI | `codex exec` | `claude -p` |
| Resume | `codex exec resume ${ID}` | `-r ${ID}` or `-c` (most recent) |
| Sandbox (worktree) | None (`danger-full-access`) | Kernel-level (repo root) |
| Network control | Binary (on/off) | Per-profile (none/localhost/domains) |
| Output format | `--json` (JSONL) | `--output-format json` or `stream-json` |
| Session ID | `thread_id` from JSONL | `session_id` from JSON |
| Working dir | `-C path` | `cd path &&` (no flag) |

[1]: https://formal.ai/blog/allowlisting-some-bash-commands-is-often-the-same-as-allowlisting-all-with-claude-code "Formal: Allowlisting some Bash commands is often the same as allowlisting all"
