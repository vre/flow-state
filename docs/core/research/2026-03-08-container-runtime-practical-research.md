# Container Runtime Practical Research: Codex & Claude Code on Podman/macOS

**Date**: 2026-03-08
**Status**: Research complete
**Scope**: Real-world experience running AI coding agents in containers on macOS Apple Silicon

---

## 1. Claude Code in Containers

### Official Support

Claude Code has first-class container support via three paths:

1. **DevContainer** (`.devcontainer/`): Official reference implementation [1]
   - Base image: `node:20-bookworm-slim`
   - Installs: git, curl, ripgrep, fd-find, jq, tree, bat, htop, zsh, fzf
   - Claude Code installed globally via `npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}`
   - Runs as `node` user (UID 1000), non-root with limited sudo
   - Firewall: `init-firewall.sh` sets default-deny egress via iptables/ipset, allowlists only npm registry, GitHub, Claude API
   - Requires `NET_ADMIN` + `NET_RAW` capabilities (restricted to firewall script via sudoers)
   - Volume mounts: bash history, `~/.claude` config (named volumes), workspace (bind mount, delegated consistency)
   - `NODE_OPTIONS="--max-old-space-size=4096"` (4GB heap)

2. **Docker Sandboxes** (`docker/sandbox-templates:claude-code`): Docker's official sandbox image [2]
   - Ubuntu base with Node.js, Python, Go, Git, Docker CLI pre-installed
   - Launches with `--dangerously-skip-permissions` by default
   - `docker sandbox run claude ~/my-project`
   - Runs in microVM with network isolation and allow/deny lists

3. **Community containers**: `tintinweb/claude-code-container` [3], `nezhar/claude-container` [4], `RchGrav/claudebox` [5]

### Non-Interactive Mode (`claude -p`)

Works well in containers. Key flags:

```bash
# Basic non-interactive
claude -p "prompt" --output-format json

# Full autonomous in container (safe because container is the boundary)
claude -p "prompt" --dangerously-skip-permissions --output-format stream-json

# Restrict tools for batch operations
claude -p "prompt" --allowedTools "Edit,Bash(git commit *)"
```

Output formats: `text` (default), `json`, `stream-json` (streaming JSONL).

The `--dangerously-skip-permissions` flag (alias for `--permission-mode bypassPermissions`) is the standard approach in containers. The container boundary replaces the permission prompts. Community consensus: never use this flag on bare metal, always use it in containers [6][7].

### Gotchas

- `ANTHROPIC_API_KEY` must be set as env var; Docker Sandboxes daemon does not inherit shell env vars [2]
- Never mount host Docker socket (`/var/run/docker.sock`) into the container -- enables sandbox escape [8]
- Devcontainer warns: malicious projects can exfiltrate anything accessible in the container, including Claude Code credentials [1]
- `--no-user-prompt` flag prevents blocking on user confirmation in CI pipelines

---

## 2. Podman macOS Performance: Bind Mounts & virtiofs

### The Core Problem: File Metadata Operations

Bind-mounted volumes on macOS are slow due to the host-to-VM file sharing layer. The bottleneck is **file stat operations** (not read/write throughput):

| Operation | Native `/tmp` | Bind-mounted `/app` | Slowdown |
|-----------|--------------|---------------------|----------|
| `jest --version` (Node.js) | ~1.1s | ~7.7s | **7x** |
| `ls` on 617 files | 0.014s | 7.3s | **520x** |
| Copy 45MB node_modules | fast | 1m 23s | extreme |

Source: Podman issue #16994 [9]. This was with Podman 4 using 9p/QEMU.

### Podman 5 Improvements: 9p -> virtiofs

Podman 5 (2024) rewrote `podman machine` and switched from 9p to virtiofs on macOS [10]:

- virtiofs uses Apple's native Hypervisor framework (not QEMU)
- Significant improvement over 9p, but still slower than native
- Current state: bind mounts are **~3x slower** than native (down from 5-6x two years ago) [11]

### Known virtiofs Issues on macOS

- **Concurrency bug**: File operations can fail with "No such file or directory" due to cache invalidation issues (Podman #23061) [12]
- **Open file limit**: Mounted volumes have a limit of 64 open files, which is extremely low for Node.js workloads (Podman #16106) [13]
- **File size mismatch**: VirtioFS may report incorrect file sizes in bind-mounted volumes [14]

### Benchmark Comparison: npm install (React app) [11]

| Runtime | Bind mount | Bind + volume hybrid |
|---------|-----------|---------------------|
| Lima | 8.99s | 3.96s |
| Docker-VZ (standard) | 9.53s | -- |
| Docker-VZ + file sync | 3.88s | -- |
| Docker-VMM | 8.47s | 3.42s |
| OrbStack | 4.22s | 3.19s |
| Linux native | 5.29s | -- |

Key insight: **Docker with synchronized file shares and OrbStack approach or beat native Linux** for package install workloads. Plain bind mounts remain ~2x slower.

### Recommendations for Git Repos (Many Small Files)

1. Use virtiofs (Podman 5 default on macOS), not 9p
2. For dependency-heavy dirs (node_modules, .git): use named volumes, not bind mounts
3. Consider hybrid: bind mount source code, named volume for deps
4. OrbStack is consistently fastest for macOS bind mount performance

---

## 3. Container Startup Time

### Podman on Linux (bare metal reference)

- Optimized: **5.6ms +/- 3ms** (Podman direct, small image) [15]
- Podman spawns OCI runtime directly (no daemon relay), slightly faster than Docker in some tests

### macOS Container Startup (VM overhead included)

| Runtime | Cold start | Warm start | Notes |
|---------|-----------|------------|-------|
| Apple Container v0.5 | 1.2s | 0.8s | No host VM delay [16] |
| Colima | ~15s | ~2s | QEMU VM boot on cold |
| Docker Desktop | ~3-5s | ~0.5-1s | VM always running |
| Podman machine | ~3-5s | ~0.5-1s | VM must be started first |

On macOS, the VM is the bottleneck, not the container. Once `podman machine` is running, `podman run` for a cached image adds <1s. The `--rm` flag cleanup overhead is negligible.

### Image Caching

- First pull: network-bound (seconds to minutes depending on image size)
- Subsequent runs: image layers cached in VM, near-instant
- `podman machine stop/start` preserves image cache (stored in VM disk)
- `podman machine rm` destroys cache

---

## 4. Podman Rootless on macOS Gotchas

### UID/GID Mapping

The fundamental issue: macOS host UID (typically 501/503) does not match container UID (typically 1000).

- All rootless containers run in a user namespace [17]
- Bind-mounted files appear as different owner inside container
- Example: host UID 503 -> container sees files owned by root or unmapped UID
- Writing back to mount can fail with permission denied

**Workarounds**:
- `--userns=keep-id`: maps host UID to container UID (partial fix, sometimes broken on macOS) [18]
- `podman unshare chown`: change ownership within Podman's user namespace
- Run container as root (defeats rootless purpose)
- Use named volumes instead of bind mounts for writable data

### Known macOS-Specific Issues

- **DevContainer workspace read-only**: Volume mounted with wrong UID/GID, container user cannot write (Podman #27893) [18]
- **Permission denied on volumes**: `--userns=keep-id` does not always work on macOS (Podman #17560) [19]
- **libkrun vs applehv**: libkrun (default since Podman 5) has bind mount permission issues that applehv does not (Podman discussion #27679) [20]

### Network Limitations

- Rootless containers cannot bind to ports <1024 without `slirp4netns` or `pasta`
- On macOS, networking goes through the VM, adding a layer of complexity
- Port forwarding works but is slower than native Docker Desktop port forwarding

---

## 5. Codex CLI in Containers

### Official Sandbox

Codex CLI has built-in Docker sandbox support [21]:
- Entry point: `codex-cli/scripts/run_in_container.sh`
- Creates per-project Codex home inside workdir (`.codex/.environment`)
- Configures internal iptables firewall (allowlists only OpenAI API)
- Starts codex inside container in project directory

### No Pre-Built Image

Unlike Claude Code, **Codex does not ship a pre-built Docker image** [22]. Users must build their own:
- Requires Node.js 22-slim base
- Build: `pnpm install && pnpm build` locally, produces tarball
- Common approach: start from Python or CUDA image, add npm, install codex

### Non-Interactive Mode (`codex exec`)

```bash
# Basic
codex exec "summarize repository structure"

# Full auto (skip approvals)
codex exec --full-auto "task"

# JSONL output for parsing
codex exec --json "task"

# Resume session
codex exec resume --last "follow-up"
codex exec resume <SESSION_ID> "continuation"
```

JSONL event types: `thread.started`, `turn.started`, `turn.completed`, `turn.failed`, `item.started`, `item.completed`, `error`.

Auth: `CODEX_API_KEY` env var (recommended for CI) or `~/.codex/auth.json`.

**Requirement**: Codex must run inside a git repository. Override with `--skip-git-repo-check`.

### Sandbox Limitations in Containers

Codex uses Landlock/seccomp for sandboxing on Linux. **These kernel APIs may not work inside Docker containers** if the host/container config does not support them. Recommended approach: configure Docker container to provide isolation guarantees, then run `codex --sandbox danger-full-access` inside it [23].

---

## 6. Claude Code vs Codex: Which is Easier to Containerize?

| Aspect | Claude Code | Codex CLI |
|--------|------------|-----------|
| **Pre-built image** | Yes (`docker/sandbox-templates:claude-code`) | No (build your own) |
| **Base runtime** | Node.js 20 | Node.js 22 |
| **Non-interactive flag** | `claude -p "prompt"` | `codex exec "prompt"` |
| **Skip permissions** | `--dangerously-skip-permissions` | `--full-auto` / `--sandbox danger-full-access` |
| **Output formats** | text, json, stream-json | text, json (JSONL events) |
| **Session resume** | `claude --continue` / `--resume` | `codex exec resume --last` / `resume <ID>` |
| **Git requirement** | No | Yes (overridable) |
| **Built-in firewall** | Yes (devcontainer init-firewall.sh) | Yes (iptables in sandbox script) |
| **Container maturity** | High (official image, Docker Sandboxes, community images) | Lower (DIY, community images) |
| **Structured output** | `--output-format json` | `--json` (JSONL event stream, richer) |

**Verdict**: Claude Code is significantly easier to containerize due to official pre-built images and broader community support. Codex has a richer JSONL event stream for programmatic parsing but requires more setup effort.

### Size Estimates

- Claude Code devcontainer: ~500MB-1GB (node:20-bookworm-slim + tools)
- `docker/sandbox-templates:claude-code`: larger (includes Python, Go, Docker CLI)
- Codex minimal: ~300-500MB (node:22-slim + codex package)

---

## 7. Apple Container Runtime (Emerging Alternative)

Apple announced a native container runtime at WWDC 2025 [24]:
- Swift-based, uses Apple Virtualization framework directly
- Each container runs in its own lightweight VM (stronger isolation than namespace containers)
- Cold start: 1.2s, warm start: 0.8s (sub-second goal) [16]
- CPU performance: within 1% of Docker
- Memory: 2.76GB available vs Docker's 2.2GB
- I/O: mixed results (31x more iomix ops, but Fio random reads favor Docker)

**Current limitations (v0.5)**: No Dockerfile/image build, no volumes/bind mounts, no Compose, no Kubernetes. Not usable for our use case yet, but worth watching.

---

## Summary: Practical Recommendations

1. **For containerized Claude Code on macOS**: Use Docker Desktop or OrbStack with the official devcontainer or sandbox template. Both have superior bind mount performance vs Podman.

2. **For Podman on macOS**: Use Podman 5+ with applehv provider (not libkrun) to avoid bind mount permission issues. Expect ~3x slower file operations on bind mounts vs native. Use named volumes for dependency directories.

3. **For CI/automation**: Claude Code's `claude -p` with `--dangerously-skip-permissions` in a container is the most battle-tested path. Codex `codex exec --json` has richer structured output.

4. **For minimal startup overhead**: Keep `podman machine` running. Container start is <1s for cached images. Cold VM start adds 3-5s.

5. **Avoid on Podman macOS**: Large git repos with many small files as bind mounts. UID 503 (macOS) -> UID 1000 (container) mapping breaks with `--userns=keep-id` on some configurations.

---

## References

[1]: https://code.claude.com/docs/en/devcontainer "Claude Code DevContainer docs"
[2]: https://docs.docker.com/ai/sandboxes/agents/claude-code/ "Docker Sandboxes: Claude Code"
[3]: https://github.com/tintinweb/claude-code-container "claude-code-container"
[4]: https://github.com/nezhar/claude-container "claude-container"
[5]: https://github.com/RchGrav/claudebox "claudebox"
[6]: https://www.ksred.com/claude-code-dangerously-skip-permissions-when-to-use-it-and-when-you-absolutely-shouldnt/ "Safe usage guide for --dangerously-skip-permissions"
[7]: https://blog.promptlayer.com/claude-dangerously-skip-permissions/ "claude --dangerously-skip-permissions"
[8]: https://www.datacamp.com/tutorial/claude-code-docker "Claude Code Docker tutorial"
[9]: https://github.com/containers/podman/issues/16994 "Bind mount slowness on macOS"
[10]: https://www.infoq.com/news/2024/05/podman-5-released/ "Podman 5 released"
[11]: https://www.paolomainardi.com/posts/docker-performance-macos-2025/ "Docker on macOS performance 2025"
[12]: https://github.com/containers/podman/issues/23061 "virtiofs concurrency issue"
[13]: https://github.com/containers/podman/issues/16106 "Open file limit 64 on mounted volumes"
[14]: https://github.com/docker/for-mac/issues/7501 "VirtioFS file size mismatch"
[15]: https://www.redhat.com/sysadmin/speed-containers-podman-raspberry-pi "Podman startup speed improvements"
[16]: https://shipit.peterhollmer.com/posts/containers/ "Apple Container v0.5.0 benchmarks"
[17]: https://www.tutorialworks.com/podman-rootless-volumes/ "Podman rootless volumes explained"
[18]: https://github.com/containers/podman/issues/27893 "DevContainer workspace mounted read-only"
[19]: https://github.com/containers/podman/issues/17560 "Permission denied on volumes macOS"
[20]: https://github.com/containers/podman/discussions/27679 "libkrun vs applehv bind mount permissions"
[21]: https://blog.promptlayer.com/how-openai-codex-works-behind-the-scenes-and-how-it-compares-to-claude-code/ "How Codex works"
[22]: https://github.com/openai/codex/discussions/915 "Docker image for Codex discussion"
[23]: https://developers.openai.com/codex/cli/reference/ "Codex CLI reference"
[24]: https://www.infoq.com/news/2025/06/apple-container-linux/ "Apple Containerization announcement"
