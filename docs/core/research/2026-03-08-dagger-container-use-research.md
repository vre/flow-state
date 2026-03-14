# Dagger Container Use - Research

Date: 2026-03-08

## What It Is

Container Use is an open-source MCP server by Dagger that provides isolated, containerized development environments for AI coding agents. Each agent gets a fresh container backed by its own Git branch. Written in Go, powered by Dagger engine.

- Repo: https://github.com/dagger/container-use
- Docs: https://container-use.com
- Install: `brew install dagger/tap/container-use`
- Status: Early development, active iteration

## Architecture

Three components per environment:
1. **Git branch** in a fork bare repo at `~/.config/container-use/repos/`
2. **Dagger container** with code mounted at `/workdir`
3. **History tracking** via Git notes (`refs/notes/container-use`, `refs/notes/execution-log`, `refs/notes/environment-config`)

File sync uses Git worktrees mounted as Docker volumes. The user's repo stays untouched; container-use maintains a separate bare repository (fork pattern). Each environment gets a worktree pointing to a branch in the fork repo.

## MCP Server Tools (12 tools)

Started via `container-use stdio`. Exposed tools:

| Tool | Purpose |
|------|---------|
| `environment_create` | Spawn new isolated environment |
| `environment_open` | Connect to existing environment |
| `environment_run_cmd` | Execute commands (foreground/background) |
| `environment_file_read` | Read files |
| `environment_file_write` | Write files |
| `environment_file_edit` | Edit files |
| `environment_file_delete` | Delete files |
| `environment_file_list` | List files |
| `environment_add_service` | Add background services with port mapping |
| `environment_checkpoint` | Export container state |
| `environment_config` | Modify config (base image, env vars, commands) |
| `environment_update_metadata` | Change title/description |

Two modes:
- **Single-tenant**: reuses current environment ID from stored state (typical for one agent)
- **Multi-tenant**: caller specifies `environment_id` and `environment_source` explicitly

## File Sync Mechanism

Git worktrees mounted as Docker volumes (not copy):
1. Agent calls file operation (read/write/edit/delete)
2. Path validated (no submodule modifications)
3. Operation applied to worktree via Dagger (`container.WithNewFile`, `WithPatch`, `WithoutFile`)
4. Changes auto-committed to Git
5. Environment state updated

The agent does NOT operate on local files. All file operations go through the MCP tools, which operate inside the container's `/workdir`.

## Git Integration

Fork pattern:
- User repo remains untouched
- Fork bare repo at `~/.config/container-use/repos/` stores all environment branches
- Each environment = Git worktree pointing to a branch in the fork repo
- Full commit history preserved per environment
- Standard git commands work: `git log`, `git diff`, `git checkout <branch>`

Getting work out:
- `container-use diff <env>` -- view changes
- `container-use checkout <env>` -- bring to local workspace
- `container-use merge <env>` -- merge preserving commit history
- `container-use apply <env>` -- stage changes for custom commit

## Container Image Customization

Config stored in `.container-use/environment.json` (committable to VCS).

- **Base image**: any Docker image, default Ubuntu 24.04. Set via `container-use config base-image set python:3.11`. Use versioned tags.
- **Setup commands**: run after pulling base image, before code copy (e.g., `apt-get install openjdk-17-jdk gradle`)
- **Install commands**: run after code is copied (e.g., `npm install`, `pip install -r requirements.txt`)
- **Environment variables**: `container-use config env set KEY=VALUE`
- **Secrets**: 1Password (`op://`), env vars (`env://`), HashiCorp Vault (`vault://`), files (`file://`). Resolved at runtime inside container, never exposed to AI model. Output sanitization strips secret values from logs.

So yes, JVM + Gradle is straightforward: set base image to a JDK image or add setup commands.

## Network Access

- Containers have outbound network access by default (Dagger containers can reach the internet)
- Background services exposed via Dagger port mapping: `Host.Tunnel()` creates localhost tunnels
- `environment_add_service` tool handles port exposure
- Multiple services coexist on different ports
- Dagger supports host-to-container and container-to-host networking

No mention of network restriction/firewall controls for sandboxing. Containers appear to have full network access.

## Session Persistence

Persistence through Git, not container snapshots:
1. Every operation (file change, command) triggers auto-commit
2. Git notes store metadata
3. `EnvironmentInfo` serialized state (config, container ID, timestamps, submodule paths)
4. Environments loadable from disk via `Load()` -- reconstructs container context
5. Agents resume by referencing environment ID

Containers are ephemeral per command but state persists through Git commits. The container is rebuilt from the committed state when resuming.

## Podman Support

**Partially supported, not first-class.**

- Dagger engine supports Podman (and nerdctl, finch, Apple container) as OCI-compatible runtimes [1]
- container-use install script checks for Docker, shows error if not found
- The code does check for Podman presence [2]
- GitHub issue #102 (closed): maintainer says "follow Dagger docs for Podman" [3]
- Workaround: `ln -s $(which podman) <local_bin_dir>/docker`
- Podman must be configured for rootful execution on macOS
- macOS Podman Desktop may need: `podman machine ssh podman-machine-default` then `sudo modprobe iptable_nat`
- GitHub issue #310 (open): Apple `container` runtime not supported because container-use hardcodes `docker` CLI

**Verdict**: Works with Podman via symlink trick. Not officially tested or documented. Dagger itself handles Podman fine; the gap is in container-use's CLI detection logic.

[1]: https://docs.dagger.io/reference/container-runtimes/podman/
[2]: https://github.com/dagger/container-use/blob/main/cmd/container-use/version.go#L97-L115
[3]: https://github.com/dagger/container-use/issues/102

## Codex CLI Compatibility

**container-use lists "OpenAI Codex" in its 20+ supported agents.** [4]

The agent integration docs show MCP configuration for Codex via `~/.codex/config.toml`. container-use works with any MCP-compatible agent, and Codex CLI supports MCP servers.

[4]: https://container-use.com/agent-integrations

## macOS Installation

```bash
brew install dagger/tap/container-use
container-use version
```

Prerequisites: Docker (or Podman with symlink). Git required.

Add to Claude Code:
```bash
claude mcp add container-use -- container-use stdio
```

Add to Codex (`~/.codex/config.toml`):
```toml
[mcp.container-use]
command = "container-use"
args = ["stdio"]
```

## Key Question: Architecture for Claude Code -> Codex CLI Delegation

**Can container-use be an MCP server that Claude Code calls, where Codex CLI runs inside the Dagger container?**

The answer is nuanced:

### What container-use IS designed for
The agent (Claude Code, Codex, etc.) runs on the host and calls container-use MCP tools. The container is a workspace -- file operations and command execution happen inside it via MCP tools. The agent itself stays outside.

### What this means for delegation
Two viable patterns:

**Pattern A: Claude Code uses container-use directly**
- Claude Code has container-use as MCP server
- Claude Code creates environment, runs commands, edits files -- all via MCP tools
- No Codex CLI involved; Claude Code does the work through container-use tools
- This is the intended use case

**Pattern B: Claude Code delegates to Codex CLI which uses container-use**
- Claude Code delegates task to Codex CLI (via codex-as-mcp or session-codex)
- Codex CLI has container-use configured as its MCP server
- Codex CLI creates environment and works inside it
- This works because Codex CLI supports MCP servers

**Pattern C: Codex CLI running INSIDE the container (what you asked)**
- Theoretically possible: use `environment_run_cmd` to install and run Codex CLI inside the container
- But container-use's MCP tools replace what Codex would do (file ops, command execution)
- Running Codex inside the container would mean Codex operates on `/workdir` directly, bypassing container-use's file tracking/commit system
- Network access needed for Codex to reach OpenAI API -- available by default
- Would need Node.js/npm installed in container image
- Loses the audit trail that container-use provides

**Recommendation**: Pattern B is most aligned with our workflow. Codex CLI runs on the host with container-use as its MCP server. Claude Code delegates to Codex CLI. Codex CLI gets full sandbox isolation via container-use.

### Comparison with current git worktree approach

| Aspect | Git worktrees (current) | container-use |
|--------|------------------------|---------------|
| Isolation | Filesystem only | Full container (deps, env, services) |
| Setup overhead | Low (git worktree add) | Medium (Dagger engine + container pull) |
| Dependency isolation | None (shared system) | Full (per-container) |
| Network isolation | None | Partial (outbound open) |
| File sync | Native filesystem | Git worktree as Docker volume |
| Audit trail | Manual commits | Auto-commits per operation |
| Resume | Immediate | Rebuild container from git state |
| Tool overhead | None | 12 MCP tools replace direct file access |
| Startup time | ~1s | ~10-30s (container build + Dagger engine) |

## Known Issues and Limitations

- Early development stage -- stability issues reported
- GitHub #25: MCP timeouts frequent
- GitHub #248: Fails with shallow Git repos
- GitHub #334: Terminal source mounting issues
- GitHub #148: Engine version conflicts between `cu` and `dagger` CLI
- GitHub #300: Lock acquisition failures
- No rootless container support (Dagger requirement)
- Containers are ephemeral per command -- rebuilt from git state each time
- All file operations must go through MCP tools (no direct filesystem access by agent)
- No network restriction controls for true sandboxing

## Real-World Usage Reports

- **Zed editor**: Native integration for background agents. Recommends two profiles (foreground for local, container-use for sandboxed). Reports "significant cognitive overhead" in understanding the multi-technology stack. [5]
- **Goose (Block)**: Uses container-use for parallel isolated environments (REST + GraphQL agents simultaneously). [6]
- **InfoQ coverage**: Notes tool is "still in early development" with known issues. [7]

[5]: https://zed.dev/blog/container-use-background-agents
[6]: https://block.github.io/goose/blog/2025/06/19/isolated-development-environments/
[7]: https://www.infoq.com/news/2025/08/container-use/

## Related Projects

- **codex-as-mcp** (https://github.com/kky42/codex-as-mcp): MCP server that lets Claude Code delegate to Codex CLI. Runs `codex exec` with prompts.
- **codex-subagents-mcp** (https://github.com/leonardsellem/codex-subagents-mcp): Sub-agents for Codex via MCP. Each call spins up clean context in temp workdir.
- **podman-mcp-server** (https://github.com/manusa/podman-mcp-server): Alternative MCP server for Podman/Docker container runtimes directly.
- **gnosis-container** (https://github.com/DeepBlueDynamics/gnosis-container): Codex CLI in Docker with cron, webhooks, tools.

## Summary Assessment

**Strengths**: Full container isolation, automatic git audit trail, multi-agent parallel support, secrets management, service tunneling, 20+ agent integrations, active development.

**Weaknesses**: Early stage stability, Dagger engine overhead, no network restriction for sandboxing, Podman support is workaround-level, all file ops mediated through MCP (no direct access), container rebuild latency on resume.

**For our use case** (Claude Code delegating to Codex CLI in sandbox): Pattern B works -- Codex CLI on host with container-use as MCP server. The main question is whether the added complexity and Dagger overhead justify the isolation compared to our current git worktree approach with Codex's built-in sandbox (`workspace-write` mode).
