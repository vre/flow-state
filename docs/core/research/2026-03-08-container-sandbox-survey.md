# Container-Based Sandbox Survey for AI Coding Agents

**Date**: 2026-03-08
**Status**: Research complete — recommended: context-dependent multi-mode approach
**Context**: Codex CLI `workspace-write` sandbox breaks build tools (Gradle, Maven, Cargo). Container-based isolation gives agents a full OS environment while preventing host filesystem damage.

---

## 1. Problem Statement

Codex CLI sandbox (`workspace-write`) uses Seatbelt/Landlock syscall filtering. Three hard blockers for build tools:

| Need | Blocked by |
|---|---|
| Write `~/.gradle`, `~/.m2`, `~/.cargo` | Writes restricted to CWD |
| Network for dependency resolution | seccomp blocks outbound sockets |
| Loopback socket (Gradle daemon) | seccomp blocks `bind`/`listen` |

`writable_roots` config is unreliable on macOS. `network_access = true` silently ignored by Seatbelt ([#10390][codex-net]). Only workaround: `danger-full-access` (no isolation at all).

### Threat Model

**Threat**: Agent writes/deletes files on the host outside the worktree.
**Not a threat**: Multiple parallel agents corrupting each other's worktrees (acceptable risk).
**Implication**: Container-level isolation is sufficient. No need for microVM, gVisor, or network filtering. The container boundary prevents host filesystem damage while giving the agent full freedom inside.

## 2. Solution Landscape

### 2.1 Local-First Solutions

#### Docker Sandboxes (Docker Desktop 4.58+)

**Isolation**: microVM (Apple Virtualization.framework on macOS, Hyper-V on Windows). Each sandbox gets its own VM + private Docker daemon. Not visible in host `docker ps`.

**File sync**: Bidirectional copy (not volume mount). Workspace appears at same absolute path inside sandbox. Slight lag.

**Network**: HTTP/HTTPS filtering proxy with MITM inspection. Allow/deny policies per domain. Auto-injects API credentials (OpenAI, Anthropic, Google, GitHub).

```bash
docker sandbox run codex ~/my-project
docker sandbox run claude ~/my-project
# Custom template for JVM:
docker sandbox run -t my-jvm:v1 codex ~/my-project
```

**Custom templates** for build tools:
```dockerfile
FROM docker/sandbox-templates:codex
USER root
RUN apt-get update && apt-get install -y openjdk-21-jdk gradle maven
USER agent
```

**Agents**: Claude Code (production-ready), Codex, Gemini, Copilot, Kiro, OpenCode (in development).

**Limitations**:
- 4GB RAM hardcap — LLVM compilation fails, JVM builds may hit limit [1]
- 17GB disk per sandbox, no deduplication between sandboxes [2]
- Experimental — "breaking changes may occur between Docker Desktop versions"
- macOS: full support. Windows: experimental. Linux: legacy container-based only (no microVM)
- First boot slow (template download + VM init)

**Verdict**: Most integrated local solution. Build tools work via custom templates. 4GB RAM cap is real constraint for large Gradle builds. Experimental status means API instability risk.

[1]: https://github.com/docker/desktop-feedback/issues/121
[2]: https://github.com/docker/desktop-feedback/issues/106

#### Dagger Container Use

**URL**: https://github.com/dagger/container-use

**What**: MCP server giving each coding agent its own Docker container + Git worktree. Parallel agent workflows.

**Isolation**: Docker containers (not microVM). Per-agent Git branches.

```bash
brew install dagger/tap/container-use
# Then configure as MCP server in agent
```

**Agents**: Any MCP-compatible: Claude Code, Cursor, Goose, VS Code.

**License**: Apache 2.0. **Maturity**: Experimental (v0.4.2).

**Verdict**: Lightweight, open source, MCP-native. Weaker isolation than microVM but simpler. Git worktree integration is natural fit for our workflow.

#### Microsandbox (zerocore-ai)

**URL**: https://github.com/zerocore-ai/microsandbox

**Isolation**: libkrun (KVM-based microVMs). <200ms boot. OCI-compatible.

**Agents**: MCP-compatible (demonstrated with Claude).

**License**: Open source. **Maturity**: Pre-1.0, experimental.

**Verdict**: Promising — real VM isolation, fast boot, self-hosted. Too early for production use.

#### ClodPod (webcoyote)

**URL**: https://github.com/webcoyote/clodpod

**What**: Runs AI agents inside macOS VMs via [Tart](https://tart.run/) (Apple Virtualization.framework). Same author as SandVault.

**Isolation**: macOS-on-macOS VM. Near-native performance. Base image: `ghcr.io/cirruslabs/macos-tahoe-xcode:latest` (~20GB, includes Xcode).

**Agents**: Claude Code (`clod claude`), Codex (`clod codex`), Gemini (`clod gemini`).

**File sync**: virtiofs shared folders (bidirectional). Multiple projects mountable.

**Resources**: CPU matches host; RAM defaults to 5/8 of host. Configurable via `tart set`.

**License**: Apache 2.0. **Maturity**: 84 stars, 108 commits, Shell-only.

**Verdict**: Best option for macOS-native development (Xcode, Simulator, Swift). Strong VM isolation with near-native performance. Requires Apple Silicon. ~20GB disk for base image. No documented network isolation.

#### Chamber (Cirrus Labs)

**URL**: https://github.com/cirruslabs/chamber

**What**: Ephemeral Tart VMs — created from seed, used once, destroyed. Minimal/PoC from the Tart vendor.

**Agents**: Claude Code, Codex (auto-adds yolo flags).

**License**: AGPLv3. **Maturity**: v0.2.0, 29 stars, 36 commits. PoC.

```bash
brew install --cask cirruslabs/cli/chamber
chamber init ghcr.io/cirruslabs/macos-sequoia-base:latest
```

**Verdict**: Simpler than ClodPod but less mature. AGPLv3 is restrictive. No network isolation ([issue #1](https://github.com/cirruslabs/chamber/issues/1)).

#### Cua (trycua)

**URL**: https://github.com/trycua/cua

**Isolation**: Apple Virtualization.framework (macOS on Apple Silicon), Docker (Linux). Full desktop sandboxes with screen control.

**Agents**: Claude Code, Codex, OpenCode + computer-use agents.

**License**: Open source. **Maturity**: Active development.

**Verdict**: Overkill for CLI agents. Interesting for computer-use (GUI automation) workflows.

#### Spritz (textcortex)

**URL**: https://github.com/textcortex/spritz

**What**: Kubernetes-native control plane for running AI agents in containers. Successor to archived [claude-code-sandbox](https://github.com/textcortex/claude-code-sandbox).

**Components**: Go operator, CRDs, Helm charts, gateway, CLI, UI, GitHub App integration.

**License**: Not specified. **Maturity**: 15 stars, 68 commits, no releases. Single contributor.

**Verdict**: Server-side/K8s only. Not usable locally. Early stage.

### 2.2 Cloud/Hybrid Solutions

#### E2B

**URL**: https://e2b.dev | https://github.com/e2b-dev/E2B

**Isolation**: Firecracker microVMs. <5 MiB memory overhead per VM. Sub-200ms cold starts with pre-warmed pools.

**Deployment**: Cloud-only SaaS. No self-hosted option.

**Verdict**: Best cloud sandbox. Not usable locally.

#### Daytona

**URL**: https://github.com/daytonaio/daytona

**Isolation**: Docker containers (OCI). Sub-90ms cold starts. Git + LSP built-in.

**Deployment**: Cloud and self-hosted. Apache 2.0.

**Verdict**: Self-hostable, fast, production-ready. Worth evaluating if we need server-side execution.

#### Alibaba OpenSandbox

**URL**: https://github.com/alibaba/OpenSandbox

**Isolation**: Docker, K8s, gVisor, Kata Containers, Firecracker. Multi-backend.

**Deployment**: Local (Docker) or Kubernetes. Apache 2.0. 6.9k stars.

**Verdict**: Most flexible backend selection. Overkill for local dev, valuable for team/CI infrastructure.

#### Kubernetes Agent Sandbox (kubernetes-sigs)

**URL**: https://github.com/kubernetes-sigs/agent-sandbox

**Isolation**: gVisor (default), Kata Containers. Pre-warmed pools.

**Deployment**: Kubernetes only. Apache 2.0. Google-backed.

**Verdict**: Server-side only. Good for CI/CD agent execution.

### 2.3 Adapter Layer (Not a Sandbox)

#### Rivet sandbox-agent

**URL**: https://github.com/rivet-dev/sandbox-agent

**What**: Universal HTTP/SSE adapter that normalizes different agent APIs (Claude Code JSONL, Codex JSON-RPC, OpenCode HTTP/SSE) into one API. Runs inside an existing sandbox.

**Does NOT provide isolation.** Delegates to E2B, Daytona, Docker, etc.

**Agents**: Claude Code, Codex, OpenCode, Amp, Cursor, Pi.

**License**: Apache 2.0. **Maturity**: v0.3.x.

**Verdict**: Useful as a control plane on top of a sandbox provider, not a sandbox itself.

## 3. Comparison Matrix

| Solution | Isolation | Local | OSS | Build tools | Xcode/Sim | Boot time | Maturity |
|---|---|---|---|---|---|---|---|
| **ClodPod** | macOS VM (Tart) | Yes | Apache 2.0 | All (native macOS) | **Yes** | ~10s | 84 stars |
| **Chamber** | macOS VM (Tart) | Yes | AGPLv3 | All (native macOS) | **Yes** | ~10s | PoC (v0.2) |
| **SandVault** | macOS user perms | Yes | OSS | All (native) | No (headless) | 0 | Active |
| **Docker Sandboxes** | microVM | Yes | No (DD) | Custom templates | No | Slow first | Experimental |
| **Podman container** | Linux namespace | Yes | OSS | Dockerfile | No | <1s warm | Stable |
| **Dagger Container Use** | Docker | Yes | Apache 2.0 | Any OCI image | No | 10-30s | Experimental |
| **Microsandbox** | KVM microVM | Yes | OSS | Any | No | <200ms | Pre-1.0 |
| **Daytona** | Docker (OCI) | Self-host | Apache 2.0 | Any | No | <90ms | Production |
| **OpenSandbox** | Multi-backend | Yes | Apache 2.0 | Any | No | Varies | Production |
| **E2B** | Firecracker | No | Partial | Any | No | <200ms | Production |
| **Spritz** | K8s containers | No | ? | Any | No | Varies | Pre-release |
| Codex `workspace-write` | Seatbelt/Landlock | Yes | OSS | **Broken** | N/A | 0 | Stable |
| Codex `danger-full-access` | None | Yes | OSS | Works | N/A | 0 | Stable |

## 4. Resource Requirements

| Solution | Disk (base) | Disk (per worktree) | RAM | CPU | Cold start |
|---|---|---|---|---|---|
| **ClodPod** (Xcode image) | ~25 GB | Delta (virtiofs share) | 5/8 host (~20 GB on 32 GB) | All cores | ~30s (VM boot) |
| **ClodPod** (base image) | ~15 GB | Delta (virtiofs share) | Configurable | All cores | ~30s |
| **Chamber** (Tart VM) | ~15 GB | Delta (virtiofs share) | Configurable | All cores | ~30s |
| **Podman** (Codex slim) | ~100 MB | Bind mount (0) | ~50 MB + agent | Shared | <1s (VM warm) |
| **Podman** (Codex JVM) | ~500 MB | Bind mount (0) | ~512 MB + agent | Shared | <1s (VM warm) |
| **Podman VM** (machine) | ~2 GB | — | 2 GB default | 2 cores default | 3-5s (cold) |
| **SandVault** (user) | ~0 (shared FS) | 0 (ACL share) | 0 (shared) | Shared | 0 |
| **Docker Sandboxes** | ~17 GB per sandbox | Copy (bidirectional) | 4 GB hardcap | Shared | Slow (first) |
| **Dagger Container Use** | ~2 GB (engine) | Git worktree clone | Varies | Shared | 10-30s |
| Codex host (baseline) | 0 | Worktree (~1 MB) | ~50 MB | Shared | 0 |

Notes:
- **ClodPod/Chamber**: Tart uses APFS cloning — VM clones are instant and share unchanged blocks. The ~25 GB is the seed image; clones add only delta.
- **Podman VM**: The Linux VM runs once, shared across all containers. 2 GB RAM / 2 cores default, configurable via `podman machine set`.
- **SandVault**: Zero overhead — same filesystem, same binaries. Only cost is Homebrew tools pre-installed under main user.
- **Docker Sandboxes**: Each sandbox gets its own microVM with 17 GB disk, no deduplication between sandboxes.

## 5. Evaluation for Our Workflow

### Requirements

1. Codex CLI must run inside with full-auto/never approval
2. Git must work (commit, push from inside)
3. Build tools (Gradle, Maven, uv/pip) must work
4. Network for dependency resolution
5. File changes sync back to host (volume mount)
6. Session persistence (resume across container restarts)
7. macOS support with Podman (no Docker Desktop)
8. Reasonable startup time (<10s)
9. No cloud dependency

### Assessment

**Podman + custom image** — Strongest isolation. Codex Rust binary (~35MB, zero deps) in a slim Debian image. Volume-mount worktree at `/workspace`. `--sandbox danger-full-access` inside container (container is the sandbox). Rootless Podman is default on macOS. No framework overhead. Downsides: virtiofs ~3x slower than native, UID mapping issues (macOS 503 → container 1000), open file descriptor limit 64 on mounted volumes (Node.js problem).

**macOS separate user (SandVault)** — Native performance, no VM overhead. [SandVault][sandvault] implements this: creates non-admin user, manages ACLs, optional Seatbelt layer. Supports Claude Code, Codex, Gemini. Unix permissions prevent agent from touching main user's files. Downsides: medium-strength isolation (kernel CVEs exist), shared `/tmp`, Homebrew friction (pre-install needed), GUI apps (emulator/simulator) don't work without login session.

**Dagger Container Use** — MCP server where agent runs on host, commands execute in container. Different architecture. 10-30s Dagger engine startup. Early stage — MCP timeouts, lock failures reported. Podman support via symlink workaround only.

**Docker Sandboxes** — Requires Docker Desktop (commercial). microVM isolation (overkill for our threat model). 4GB RAM hardcap. Not available with Podman or OrbStack.

[sandvault]: https://github.com/webcoyote/sandvault "SandVault — macOS sandbox for AI agents"

### Decision: Context-Dependent — No Single Solution

Neither approach works for all project types. Both containers and separate users fail at the same point: host GUI resources (emulators, simulators).

| Project type | Recommended approach | Why |
|---|---|---|
| Backend, libraries, CI | **Podman container** | Strongest isolation, build tools work |
| Python/Node (many small files) | **macOS separate user** (SandVault) | No virtiofs slowdown, no fd limit |
| Android build (no emulator) | **Podman container** (JVM image) | Full Gradle support |
| iOS / Android + Simulator/Emulator | **ClodPod** (macOS VM) | Xcode, Simulator, Emulator — all work in VM |
| Mobile + USB device | **Host mode** + `danger-full-access` + worktree | USB passthrough to VM not practical |
| Web testing (headless) | **Podman container** (browser image) | Playwright/Chromium inside container |

Rationale for multi-mode approach:
- Container: strongest isolation, but virtiofs overhead and macOS UID/fd quirks
- Separate user: native performance, but weaker isolation and Homebrew friction
- Host mode: zero overhead, but no isolation beyond git worktree boundary

## 6. Podman + Codex Implementation Details

### Codex CLI in Containers — Confirmed Working

- Codex Rust binary: `codex-aarch64-unknown-linux-gnu.tar.gz` (~35MB) from [GitHub Releases][codex-releases]
- Zero dependencies — no Node.js needed
- Built-in sandbox (bubblewrap/Landlock) may conflict with container isolation → use `--sandbox danger-full-access`
- Flag ordering matters: `codex exec "prompt" --sandbox="danger-full-access"` (sandbox flag AFTER prompt)
- DNS must resolve `api.openai.com` — verify with `curl -I https://api.openai.com` inside container

[codex-releases]: https://github.com/openai/codex/releases "Codex CLI releases"

### Dockerfile

```dockerfile
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates jq && rm -rf /var/lib/apt/lists/*
# Add Codex CLI (Rust binary)
ADD https://github.com/openai/codex/releases/latest/download/codex-aarch64-unknown-linux-gnu.tar.gz /tmp/codex.tar.gz
RUN tar -xzf /tmp/codex.tar.gz -C /usr/local/bin/ && rm /tmp/codex.tar.gz && chmod +x /usr/local/bin/codex
# Non-root user
RUN useradd -m -s /bin/bash coder && mkdir -p /workspace && chown coder:coder /workspace
USER coder
WORKDIR /workspace
RUN git config --global --add safe.directory /workspace
ENV HOME=/home/coder
```

Variant with JVM:
```dockerfile
FROM eclipse-temurin:21-jdk-jammy
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates jq && rm -rf /var/lib/apt/lists/*
ADD https://github.com/openai/codex/releases/latest/download/codex-aarch64-unknown-linux-gnu.tar.gz /tmp/codex.tar.gz
RUN tar -xzf /tmp/codex.tar.gz -C /usr/local/bin/ && rm /tmp/codex.tar.gz && chmod +x /usr/local/bin/codex
RUN useradd -m -s /bin/bash coder && mkdir -p /workspace && chown coder:coder /workspace
USER coder
WORKDIR /workspace
RUN git config --global --add safe.directory /workspace
ENV HOME=/home/coder GRADLE_USER_HOME=/home/coder/.gradle
```

### Run Commands

```bash
# Basic delegation
podman run --rm \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -v .worktrees/feature:/workspace:Z \
  codex-sandbox:latest \
  codex exec --json --full-auto --sandbox danger-full-access "prompt"

# With session persistence
podman run --rm \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -v .worktrees/feature:/workspace:Z \
  -v codex-sessions:/home/coder/.codex \
  codex-sandbox:latest \
  codex exec --json --full-auto --sandbox danger-full-access "prompt"

# Resume session
podman run --rm \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -v .worktrees/feature:/workspace:Z \
  -v codex-sessions:/home/coder/.codex \
  codex-sandbox:latest \
  codex exec resume --json ${THREAD_ID} "follow-up prompt"
```

### macOS Podman Considerations

- Podman on macOS runs a Linux VM (Apple Virtualization.framework on Apple Silicon)
- Bind mounts use virtiofs — ~3x slower than native for many small files (node_modules)
- Mitigation: mount only the worktree, not entire repo
- `:Z` suffix handles SELinux relabeling inside VM
- Rootless Podman is default and sufficient
- Outbound network works by default (pasta/slirp4netns)

### Git Workaround No Longer Needed

Inside a container, Codex's `.git` denylist is irrelevant because we use `--sandbox danger-full-access`. The container itself is the security boundary. No need for the `.git-codex-sandbox-workaround` rename.

### Integration with session-codex Skill

The skill needs two modes:
1. **Host mode** (current): `codex exec -s workspace-write -C .worktrees/${NAME}` with `.git` rename workaround
2. **Container mode** (new): `podman run ... codex exec --sandbox danger-full-access` with volume mount

Container mode is preferred when:
- Project uses JVM build tools (Gradle, Maven)
- Project needs network access for dependency resolution
- Codex's built-in sandbox blocks required operations

## 7. macOS Separate User (SandVault) Details

### How It Works

SandVault ([github.com/webcoyote/sandvault][sandvault]) creates a non-admin macOS user, manages ACLs on shared workspace directories, and optionally layers Seatbelt sandbox on top.

```bash
# Manual approach (or use SandVault):
sudo sysadminctl -addUser agent -password <pwd> -home /Users/agent
# Share worktree with ACL inheritance
chmod -R +a "agent allow read,write,execute,delete,add_file,add_subdirectory,file_inherit,directory_inherit" .worktrees/feature
# Run agent as that user
sudo -u agent env OPENAI_API_KEY="$OPENAI_API_KEY" codex exec --json --full-auto "prompt"
```

### What Works

- CLI tools: `codex exec`, `claude -p`, `gradle build`, `git` — all work via `sudo -u`
- Native filesystem performance — no VM, no virtiofs
- Network access — unrestricted
- Build tools — full access to agent's own `~/.gradle`, `~/.m2`, etc.

### What Doesn't Work

- **GUI apps**: Simulator, Android Emulator, visual browsers — require WindowServer access (login session)
- **Homebrew**: designed for single user. Pre-install tools under main user, agent uses read-only
- **macOS Keychain**: cross-user access requires explicit sharing
- **`sudo -u` clears environment**: must pass env vars explicitly or use `env` wrapper

### Security Properties

- Non-admin cannot `sudo`, cannot write to `/usr/local`, `/Applications`, `/Library`
- Home directory isolation: `/Users/vre/` is 700 (owner-only)
- Shared `/tmp` — agent and main user can both read/write
- SIP protects system files but not user-to-user boundaries
- Kernel privilege escalation CVEs exist (2025-2026) — medium-strength isolation
- SandVault adds Seatbelt layer for defense-in-depth

### Podman Container Practical Issues (macOS)

Discovered during deep research:
- **virtiofs**: ~3x slower than native (improved from 9p's 7-520x)
- **UID mapping**: macOS UID 503 maps to container UID 1000. `--userns=keep-id` unreliable on macOS. Use `applehv` provider.
- **Open file limit**: 64 fd limit on mounted volumes — breaks Node.js workloads with many concurrent file watches
- **Container startup**: <1s with cached image (VM already running). Cold VM start adds 3-5s.
- **Claude Code easier to containerize** than Codex: official devcontainer image, Docker Sandbox template. Codex has no official image but richer JSONL streaming.

See: `docs/core/research/2026-03-08-macos-user-isolation-agent-sandbox.md`
See: `docs/core/research/2026-03-08-container-runtime-practical-research.md`

## 8. Alternatives for Future Reference

### Dagger Container Use

Worth revisiting if we need:
- MCP-native container tools (12 tools for file/command operations)
- Automatic git audit trail per operation
- Multi-agent parallel environments with branch isolation
- Secret injection from 1Password/Vault

Current blockers: Dagger engine 10-30s startup, early-stage stability, Podman via symlink only.

See: `docs/core/research/2026-03-08-dagger-container-use-research.md`

### Docker Sandboxes

Worth revisiting if:
- Docker Desktop becomes available (OrbStack adds `docker sandbox` support — [#2295][orbstack-sandbox])
- microVM isolation becomes a requirement (untrusted code execution)

Current blockers: requires Docker Desktop, 4GB RAM hardcap, experimental.

[orbstack-sandbox]: https://github.com/orbstack/orbstack/issues/2295 "OrbStack docker sandbox support request"

## 9. Next Steps

1. **Evaluate ClodPod**: install Tart, test `clod codex` on a worktree with Gradle project — strongest candidate for mobile dev
2. **Evaluate SandVault**: test with Codex CLI, measure setup friction — best for Python/Node projects
3. **Build Podman Codex image**: slim variant, test `codex exec --json` inside container — best for backend/CI
4. **Compare**: ClodPod vs SandVault vs Podman on real project (Gradle build, Python tests, startup time)
5. **Update `session-codex` skill**: four modes — host (current), container (Podman), user (SandVault), vm (ClodPod)
6. **Test session resume**: across VM restarts, container restarts, and `sudo -u` invocations

## References

[codex-net]: https://github.com/openai/codex/issues/10390 "macOS: network_access = true silently ignored by seatbelt"
[codex-gradle]: https://github.com/openai/codex/issues/5228 "Allow gradle to run in sandbox"
[codex-cache]: https://github.com/openai/codex/issues/2444 "Need ability to whitelist ~/.cache in safe sandbox mode"
[docker-sandboxes]: https://docs.docker.com/ai/sandboxes/ "Docker Sandboxes docs"
[docker-arch]: https://docs.docker.com/ai/sandboxes/architecture/ "Docker Sandboxes architecture"
[docker-templates]: https://docs.docker.com/ai/sandboxes/templates/ "Docker Sandboxes custom templates"
[docker-codex]: https://docs.docker.com/ai/sandboxes/agents/codex/ "Docker Sandboxes Codex integration"
[docker-network]: https://docs.docker.com/ai/sandboxes/network-policies/ "Docker Sandboxes network policies"
[docker-ram]: https://github.com/docker/desktop-feedback/issues/121 "4GB RAM cap issue"
[docker-disk]: https://github.com/docker/desktop-feedback/issues/106 "17GB disk per sandbox"
[docker-blog]: https://www.docker.com/blog/docker-sandboxes-a-new-approach-for-coding-agent-safety/ "Docker blog: sandboxes"
[dagger-cu]: https://github.com/dagger/container-use "Dagger Container Use"
[microsandbox]: https://github.com/zerocore-ai/microsandbox "Microsandbox"
[daytona]: https://github.com/daytonaio/daytona "Daytona"
[opensandbox]: https://github.com/alibaba/OpenSandbox "Alibaba OpenSandbox"
[k8s-sandbox]: https://github.com/kubernetes-sigs/agent-sandbox "Kubernetes Agent Sandbox"
[e2b]: https://e2b.dev "E2B"
[rivet]: https://github.com/rivet-dev/sandbox-agent "Rivet sandbox-agent"
[cua]: https://github.com/trycua/cua "Cua"
[rivet-reverse]: https://rivet.dev/blog/2026-02-04-we-reverse-engineered-docker-sandbox-undocumented-microvm-api/ "Rivet reverse-engineered Docker Sandbox API"
[clodpod]: https://github.com/webcoyote/clodpod "ClodPod — AI agents in macOS VMs"
[chamber]: https://github.com/cirruslabs/chamber "Chamber — ephemeral Tart VMs for AI agents"
[spritz]: https://github.com/textcortex/spritz "Spritz — K8s control plane for AI agents"
[tart]: https://tart.run/ "Tart — macOS VM management on Apple Silicon"
