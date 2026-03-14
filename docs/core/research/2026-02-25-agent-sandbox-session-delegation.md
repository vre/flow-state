# Agent Sandbox & Session Delegation Research

Research into sandboxing and session delegation for AI coding agents. Conducted 2026-02-25/26 while building `session-claude` and `session-codex` skills.

## Context

Multi-agent development workflow delegates tasks from an orchestrating Claude to worker agents. Workers need filesystem + git access in isolated worktrees, but must be prevented from causing damage outside the project. This research covers what sandboxing each CLI offers, how sessions work, and practical workarounds for limitations.

## 1. Sandbox mechanisms — kernel-level comparison

All major agents that offer sandboxing use the same deprecated macOS primitive (`sandbox-exec`). On Linux, approaches diverge.

| Platform | Claude Code | Codex CLI | Gemini CLI | OpenCode | Copilot CLI |
|---|---|---|---|---|---|
| macOS | Seatbelt | Seatbelt | Seatbelt (6 profiles) | Plugin: Seatbelt [a] | None |
| Linux | bubblewrap + seccomp | Landlock + seccomp (default), bubblewrap (opt-in) | Docker/Podman | Plugin: bubblewrap [a] | None |
| Windows | N/A | AppContainer + WSL | Docker/Podman | N/A | None |
| Sandbox default | **Off** | **On** (`workspace-write`) | **Off** | **Off** | **Off** |

[a] OpenCode uses `@anthropic-ai/sandbox-runtime` (Anthropic's library) via optional plugin. Fail-open design — if sandbox init fails, commands run unrestricted.

### How the kernel mechanisms work

**Apple Seatbelt** (macOS): Built on TrustedBSD MACF (~300 policy hooks, ~90 filter predicates). SBPL profiles (Scheme dialect) are compiled to bytecode by `libsandbox`'s TinyScheme interpreter, then loaded into the kernel via `__mac_syscall`. Evaluated per-syscall at the MACF hook layer. Child processes inherit the policy via MAC label on `proc` struct. [1][2]

**Landlock** (Linux): LSM with unprivileged declarative rules. Three syscalls: `landlock_create_ruleset`, `landlock_add_rule`, `landlock_restrict_self`. FD-based path rules, allow-only (no negative rules). Kernel >= 5.13 required. Known limitation: cannot restrict `stat()`, `chdir()`, `chmod()`. Read restrictions not fully enforced in Codex (TODO in source). [3]

**Bubblewrap** (Linux): User namespaces + bind mounts. Creates empty mount namespace on tmpfs, selectively bind-mounts paths. Stronger than Landlock because the sandboxed process cannot even *see* restricted paths. Claude Code uses socat bridges for network proxy (Unix sockets bind-mounted into sandbox). [4]

**Seccomp-BPF** (Linux): Syscall-level filter. Used alongside Landlock/bubblewrap. Codex blocks `ptrace`, `io_uring_*`, and network syscalls (`connect`, `bind`, `listen`, `sendto`). `AF_UNIX` allowed for local IPC. [2]

### Performance

- Seatbelt: per-syscall bytecode evaluation; <15ms startup [5]
- Landlock: minimal — rule check at VFS/LSM layer, no namespace creation
- Bubblewrap: ~15ms startup (mount namespace setup), zero per-operation overhead

## 2. Sandbox boundaries — what is actually restricted

### Claude Code

Sandbox boundary = **CWD at launch** (not git repo root as previously assumed — git root is only used for CLAUDE.md traversal). In our tests CWD happened to be inside the repo, creating the appearance of a repo-root boundary.

| What | Access |
|---|---|
| CWD + subdirs | Read + write |
| Rest of filesystem | Read-only |
| `.git/hooks/**` | Denied (even inside CWD) |
| Shell configs (`.bashrc`, `.zshrc`) | Denied |
| `~/.ssh/**`, `~/.aws/**` | Denied |
| `/tmp`, macOS `$TMPDIR`, `~/.claude` | Always writable |
| `additionalDirectories` | Read + write (via `--add-dir` or settings) |

Network: HTTP/HTTPS proxy outside sandbox. Domain allowlisting. SSH/raw TCP cannot traverse proxy. `allowUnsandboxedCommands` (default true) allows fallback to unsandboxed exec with permission prompt.

### Codex CLI

Three modes, hardcoded `.git`/`.codex`/`.agents` read-only denylist:

| Mode | Writable | Denied (hardcoded) | Network |
|---|---|---|---|
| `read-only` | Nothing | All writes | Off |
| `workspace-write` | CWD + `writable_roots` + `/tmp` | `.git`, `.codex`, `.agents` (recursive, even in CWD) | Off |
| `danger-full-access` | Everything | Nothing | Unrestricted |

`--add-dir` adds writable roots but **cannot override** the `.git` denylist. When `.git` is a worktree pointer file, the resolved gitdir target is also protected. `sandbox_permissions` config is partially implemented plumbing — does not enforce restrictions in practice. [6][7]

After CVE-2025-59532: CWD is canonicalized from user's actual starting location.

### Gemini CLI

Six Seatbelt profiles with increasing restriction:

| Profile | Writes | Reads | Network |
|---|---|---|---|
| `permissive-open` (default) | Project dir + caches | Unrestricted | Full |
| `permissive-closed` | Project dir + caches | Unrestricted | None |
| `permissive-proxied` | Project dir + caches | Unrestricted | Via proxy |
| `restrictive-open` | Project dir | Project dir | Full |
| `restrictive-closed` | Project dir | Project dir | None |
| `strict-proxied` | Project dir | Project dir | Via proxy |

Custom profiles via `.gemini/sandbox-macos-<name>.sb`. Container sandbox (Docker/Podman) also available with mount-based isolation. `--include-directories` adds up to 5 extra writable paths.

Past vulnerability (CVE, fixed v0.1.14): prompt injection via README.md exploiting cursory command whitelist string matching. [8]

### OpenCode

Built-in: **soft boundary only**. `external_directory` permission prompts for paths outside project root, but Bash can bypass (acknowledged by maintainer [9]).

With `opencode-sandbox` plugin: OS-enforced via Anthropic's sandbox-runtime. Configurable deny/allow lists for read, write, and network domains. **Fail-open** — if sandbox init fails, commands run unrestricted.

### Copilot CLI

**No kernel sandbox.** Application-level path checking only — restricts tool calls to CWD + subdirs, but once a shell command runs it has full user permissions. Issue [#892][10] requests sandbox mode (priority: medium, effort: large, unimplemented).

Cloud-based Copilot Coding Agent (GitHub Actions) uses ephemeral environments with a network firewall, but the firewall only applies to Bash tool processes and explicitly states "sophisticated attacks may bypass" it.

## 3. Git in worktrees

| Agent | Git in sandbox? | Mechanism |
|---|---|---|
| Claude Code | **Works** | `.git/worktrees/` inside CWD boundary |
| Codex CLI | **Blocked** (but workaround found) | `.git` hardcoded read-only; rename bypasses denylist |
| Gemini CLI | **Works** | `.gitconfig` explicitly allowed in Seatbelt profile; `.git` not denied |
| OpenCode | N/A (no built-in sandbox) | — |
| Copilot CLI | N/A (no sandbox) | — |

### Codex `.git` bypass — tested and confirmed

Codex's denylist matches literal path `.git`. Renaming the git data directory bypasses it:

```bash
# In worktree:
mv .git .git-codex-sandbox-workaround
printf 'gitdir: .git-codex-sandbox-workaround\n' > .git
```

Git reads the `.git` pointer file and operates normally. Codex's Seatbelt `(require-not (subpath ".git"))` does not match `.git-codex-sandbox-workaround`. Landlock equivalent uses the same path-based denylist.

**Tested under `workspace-write` sandbox**: `git status`, `git add`, `git commit` all succeed. This allows using kernel-enforced sandbox (CWD-restricted writes, no network) while retaining git access — eliminating the need for `danger-full-access`.

Feature request [#7071][6] for configurable protected directories remains unimplemented, but this rename workaround achieves the same result.

## 4. Network isolation

| Agent | Mechanism | Granularity |
|---|---|---|
| Claude Code | Proxy (Unix socket / localhost) | Per-domain allowlist/denylist |
| Codex CLI | Seccomp syscall filter | Binary on/off |
| Gemini CLI | Seatbelt profile / proxy / container | Per-profile (open/closed/proxied) |
| OpenCode | Plugin: domain allowlist | Per-domain (default: package registries + AI APIs) |
| Copilot CLI | None (app-level URL patterns) | Tool-level only, bypassable via shell |

## 5. Session management

| | Claude Code | Codex CLI | Gemini CLI | OpenCode | Copilot CLI |
|---|---|---|---|---|---|
| Non-interactive | `claude -p` | `codex exec --json` | `gemini -p` | `opencode run` | `copilot -p` |
| Resume specific | `-r ${ID}` | `resume ${ID}` | `--resume ${ID}` | `--session ${ID}` | `--resume` |
| Resume latest | `-c` | N/A | `--resume` / `-r` | `--continue` / `-c` | `--continue` |
| Output JSON | `--output-format json` | `--json` (JSONL) | `-o json` / `-o stream-json` | `--format json` | N/A |
| Working dir | `cd path &&` | `-C path` (exec only) | `cd path &&` | `cd path &&` | `cd path &&` |
| Nesting guard | `CLAUDECODE` env var | None | None | None | None |
| Session fork | N/A | N/A | N/A | `--fork` | N/A |
| Session export | N/A | N/A | N/A | `opencode export` | `/share` (markdown) |
| HTTP API | N/A | N/A | N/A | `opencode serve` | N/A |

**Codex `resume` quirks** discovered during testing:
- Does not support `-s` (sandbox), `-C` (working dir), or `-a` (nonexistent flag)
- `-c` config overrides work on resume
- Session does NOT reliably inherit sandbox settings — must re-pass via `-c`

## 6. `allowedTools` / command allowlisting is security theater

Allowing `Bash(npm run test*)`, `Bash(pytest *)`, `ShellTool(git *)` etc. provides no real security. The agent can edit `package.json`, `conftest.py`, `Makefile`, or `.gitconfig` to execute arbitrary code through whitelisted runners. [11]

This applies to all agents: Claude Code, Codex CLI, Gemini CLI, OpenCode, and Copilot CLI. The kernel sandbox is the real security boundary. Application-level tool allowlists are defense-in-depth at best.

## 7. macOS sandbox landscape

`sandbox-exec` deprecated since macOS Sierra (~2016). Apple recommends App Sandbox (entitlements) — requires `.app` bundles and code signing, unsuitable for CLI tools. No supported CLI-level replacement exists.

| Alternative | CLI-usable? | Notes |
|---|---|---|
| `sandbox-exec` (Seatbelt) | Yes | Deprecated, works on macOS 15+. De facto standard. |
| App Sandbox (entitlements) | No | Requires .app bundle + code signing |
| Apple Containers | No | macOS 26+, Linux containers only |
| Docker/Podman | No (native) | Linux VM, not native macOS |
| Alcoholless [12] | Partial | User-level isolation, no kernel enforcement |

Claude Code, Codex CLI, Gemini CLI, Cursor, Chrome, Firefox all use `sandbox-exec`. Seatbelt was "never actually deprecated — marking it as such seems to be just a way to warn developers off trying to use it directly." [13]

## 8. Tested sandbox profiles (session-claude skill)

Three profiles validated on macOS, differing only in network access:

**code** — git, edit, pure function tests. No network.
```json
{"sandbox":{"enabled":true,"autoAllowBashIfSandboxed":true,"allowUnsandboxedCommands":false}}
```

**test** — code + localhost (dev servers, Playwright, browser tests).
```json
{"sandbox":{"enabled":true,"autoAllowBashIfSandboxed":true,"allowUnsandboxedCommands":false,"network":{"allowLocalBinding":true}}}
```

**e2e** — test + external domains (APIs, package registries).
```json
{"sandbox":{"enabled":true,"autoAllowBashIfSandboxed":true,"allowUnsandboxedCommands":false,"network":{"allowLocalBinding":true,"allowedDomains":["github.com","*.pypi.org","*.npmjs.org"]}}}
```

Test results (macOS Seatbelt, worktree inside repo):

| Test | Result |
|---|---|
| Write file in worktree | OK |
| `git add` + `git commit` | OK |
| Write elsewhere in repo | OK (CWD = worktree, boundary = repo root in practice) |
| Write outside repo (`/tmp/`) | Blocked — `operation not permitted` |
| Localhost server (port bind) | OK with `allowLocalBinding: true` |
| HTTP request to localhost | OK |

## Conclusions

1. **For sandboxed delegation, prefer session-claude.** Kernel sandbox allows git + restricts filesystem. Codex forces a choice. Gemini has equivalent capability but requires explicit activation.

2. **Codex `danger-full-access` is acceptable with worktree branch isolation**, but the agent has full machine access. The worktree is logical, not a security boundary.

3. **Gemini CLI has the most flexible sandbox profiles** (6 presets + custom `.sb` files + container option). Worth evaluating as a session-gemini skill candidate.

4. **OpenCode has the best programmatic API** (HTTP server + TypeScript SDK + session fork/export), but its sandbox is an optional fail-open plugin. Not suitable for security-critical delegation without containerization.

5. **Copilot CLI has no sandbox.** Application-level permissions only. Requires external Docker wrapper for any real isolation. The cloud-based Coding Agent has better isolation (ephemeral environments + firewall).

6. **`sandbox-exec` deprecation is a non-issue.** The entire industry depends on it. Apple cannot remove it without breaking their own system services.

7. **Command allowlisting is security theater.** Rely on kernel sandbox, not tool whitelists. [11]

8. **Codex's `.git` hardcoding is the key blocker** for sandbox parity with Claude Code and Gemini CLI. Monitor [#7071][6].

## References

[1]: https://papers.put.as/papers/macosx/2011/The-Apple-Sandbox-BHDC2011-Paper.pdf "Blazakis: The Apple Sandbox (BlackHat DC 2011)"
[2]: https://github.com/openai/codex "OpenAI Codex CLI source (codex-rs/)"
[3]: https://docs.kernel.org/userspace-api/landlock.html "Landlock kernel documentation"
[4]: https://github.com/containers/bubblewrap "Bubblewrap GitHub"
[5]: https://www.anthropic.com/engineering/claude-code-sandboxing "Anthropic: Claude Code Sandboxing"
[6]: https://github.com/openai/codex/issues/7071 "Codex: CLI sandbox cannot commit because .git is read-only"
[7]: https://github.com/openai/codex/issues/5034 "Codex: Unable to use git even with workspace-write"
[8]: https://tracebit.com/blog/code-exec-deception-gemini-ai-cli-hijack "Tracebit: Gemini CLI prompt injection CVE"
[9]: https://github.com/sst/opencode/issues/2242 "OpenCode: Sandbox the agent"
[10]: https://github.com/github/copilot-cli/issues/892 "Copilot CLI: Add sandbox mode"
[11]: https://formal.ai/blog/allowlisting-some-bash-commands-is-often-the-same-as-allowlisting-all-with-claude-code "Formal: Allowlisting Bash is often the same as allowlisting all"
[12]: https://github.com/AkihiroSuda/alcless "Alcoholless: macOS user-level isolation"
[13]: https://bdash.net.nz/posts/sandboxing-on-macos/ "Mark Rowe: Sandboxing on macOS"
[14]: https://cursor.com/blog/agent-sandboxing "Cursor: Agent Sandboxing"
[15]: https://google-gemini.github.io/gemini-cli/docs/cli/sandbox.html "Gemini CLI: Sandboxing docs"
[16]: https://opencode.ai/docs/permissions/ "OpenCode: Permissions docs"
[17]: https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli "GitHub Copilot CLI docs"
