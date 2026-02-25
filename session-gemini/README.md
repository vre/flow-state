# Session Gemini Skill

Delegates tasks to Google Gemini CLI with session persistence. Two modes: direct (review/analysis) and worktree (implementation with sandboxed git).

## Why Gemini

Gemini CLI has the most flexible sandbox of the three agents:

- **Git works natively** in sandbox — `.git` is not denied (unlike Codex)
- **6 Seatbelt profiles** from permissive to restrictive, with 3 network modes (open/closed/proxied)
- **Custom `.sb` profiles** for project-specific needs
- **Container sandbox** (Docker/Podman) as alternative to Seatbelt
- **`--include-directories`** for additional writable paths (up to 5)

## Sandbox profiles

Six built-in profiles, selected via `SEATBELT_PROFILE` env var:

| Profile | Writes | Reads | Network | Use case |
|---|---|---|---|---|
| `permissive-open` | Project + caches | All | Full | E2e tests, API integration |
| `permissive-closed` | Project + caches | All | None | Code, git, unit tests |
| `permissive-proxied` | Project + caches | All | Via proxy | Controlled external access |
| `restrictive-open` | Project only | Project only | Full | Minimal write + network |
| `restrictive-closed` | Project only | Project only | None | Maximum restriction |
| `strict-proxied` | Project only | Project only | Via proxy | Audited network access |

The default `permissive-open` profile allows writes to: project dir, `~/.gemini`, `~/.npm`, `~/.cache`, `~/.gitconfig`, tmp dirs, `/dev/stdout`, `/dev/stderr`, `/dev/null`, PTY devices, and up to 5 `--include-directories`.

Custom profiles at `.gemini/sandbox-macos-<name>.sb` in the project directory.

### Container sandbox

Set `GEMINI_SANDBOX=docker` or `GEMINI_SANDBOX=podman`. Project dir mounts read-write. Custom Dockerfile at `.gemini/sandbox.Dockerfile`, shell init at `.gemini/sandbox.bashrc`. MCP servers must be available inside the container.

## Comparison with session-codex and session-claude

| | session-codex | session-claude | session-gemini |
|---|---|---|---|
| Sandbox mechanism | Seatbelt/Landlock | Seatbelt/bubblewrap | Seatbelt + Docker/Podman |
| Git in sandbox | Workaround (`.git` rename) | Native | Native |
| Network control | Binary on/off | Per-domain proxy | Per-profile (open/closed/proxied) |
| Filesystem profiles | 3 modes | Configurable via settings | 6 Seatbelt profiles + custom |
| Custom sandbox profiles | No | No | Yes (`.sb` files) |
| Container option | No | No | Yes (Docker/Podman) |
| Session resume | `codex exec resume ${ID}` | `claude -p -r ${ID}` | `gemini -p -r ${ID}` |
| Output JSON | `--json` (JSONL) | `--output-format json` | `-o json` |

## Known issues

- **Sandbox is off by default** — must pass `-s` flag or set `GEMINI_SANDBOX=true` [2]
- **Past CVE (fixed v0.1.14)**: prompt injection via README.md exploiting cursory command whitelist matching [1]
- **`GOOGLE_API_KEY` required** — must be in `.env` or environment for headless mode
- **YOLO warning**: `-y` prints "YOLO mode is enabled" to stderr — filter if parsing output

## References

[1]: https://tracebit.com/blog/code-exec-deception-gemini-ai-cli-hijack "Tracebit: Gemini CLI prompt injection CVE"
[2]: https://google-gemini.github.io/gemini-cli/docs/cli/sandbox.html "Gemini CLI: Sandboxing docs"
