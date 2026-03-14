# Sandbox Boundary Comparison: Claude Code CLI vs Codex CLI

**Date**: 2026-02-25
**Status**: Research complete
**Sources**: Official docs, source code (sandbox-runtime, codex-rs), GitHub issues, engineering blog posts, third-party analysis

---

## 1. Claude Code CLI Sandbox

### 1.1 How Repo Root Is Determined

Claude Code does **not** use "repo root" as the sandbox boundary. The sandbox boundary is the **current working directory (CWD)** at launch time [1].

- If CWD is inside a git repo, the sandbox writes to CWD and below -- not the entire repo root.
- If CWD is not a git repo, the same rule applies: CWD is the write boundary.
- Git root is used separately for memory/CLAUDE.md traversal (via `git rev-parse --show-toplevel`), but this is independent of the sandbox filesystem boundary [2].

The sandbox-runtime library (`@anthropic-ai/sandbox-runtime`) takes `allowWrite: ["."]` which resolves to `path.resolve(".")` at initialization time [3].

### 1.2 Writable vs Read-Only

**Write model: Allow-only (default deny)**

| Category | Access | Notes |
|---|---|---|
| CWD and subdirectories | Read + Write | Default writable root |
| `additionalDirectories` paths | Read + Write | Must be absolute paths, no tilde expansion |
| `/tmp`, `$TMPDIR` | Write | macOS auto-detects `/var/folders/XX/YYY/T/` pattern and allows both `/var/` and `/private/var/` paths |
| `~/.claude` | Write | Internal state directory |
| Everything else on disk | Read-only | Default read policy |
| Shell config files | Denied (read+write) | `.bashrc`, `.bash_profile`, `.zshrc` always blocked |
| `.git/hooks/**` | Denied (write) | Prevents hook injection regardless of other rules |
| SSH keys/auth files | Denied | Mandatory protection |

**Read model: Deny-only (default allow)**

All reads are permitted unless explicitly denied via `permissions.deny` rules (e.g., `Read(~/.aws/**)`, `Read(.envrc)`). Deny rules are translated into Seatbelt/bubblewrap restrictions.

### 1.3 How `additionalDirectories` / `--add-dir` Expands the Boundary

Configuration in `settings.json`:
```json
{
  "permissions": {
    "additionalDirectories": ["/Users/me/other-project", "/Users/me/shared-lib"]
  }
}
```

Or at runtime: `/add-dir /path/to/other/project`

Behavior:
- Grants **read + write** access to the specified paths within the sandbox.
- Requires **full absolute paths** -- `~/.local/bin` does not work, must use `/Users/me/.local/bin`.
- Does **not** bypass mandatory deny paths (`.git/hooks`, shell configs, SSH keys).
- Does **not** support glob patterns in the path specification itself (but the Seatbelt profile does support globs internally for deny rules).

### 1.4 Always-Writable Paths

Regardless of configuration:
- `/tmp` is always writable (included in default write paths).
- macOS `$TMPDIR` (typically `/var/folders/XX/YYY/T/`) is auto-detected by `getTmpdirParentIfMacOSPattern()` and both the `/var/` and `/private/var/` symlinked paths are allowed [3].
- `~/.claude` directory is writable (internal state).

**Known bug**: Background tasks hardcode `/tmp/claude/` ignoring `$TMPDIR`, causing `EACCES` on systems where `/tmp` is not user-writable [4]. The Bash tool has also been reported to set `$TMPDIR` to a root-owned path on macOS [5].

### 1.5 Network Proxy Architecture

The network proxy runs **outside** the sandbox and is the only way sandboxed processes can reach the network:

**macOS**: Seatbelt profile allows TCP connections only to specific `localhost:port` where the proxy listens. Environment variables `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` are set inside the sandbox pointing to these ports.

**Linux**: Network namespace is completely removed via bubblewrap. Traffic routes through Unix domain sockets to `socat` bridges running outside the namespace. The proxy intercepts at the application layer.

**Domain filtering** (`filterNetworkRequest()`):
1. Check `deniedDomains` first -- match blocks immediately.
2. Check `allowedDomains` -- match allows.
3. Invoke `sandboxAskCallback` if defined (user prompt).
4. Default deny if none match.

Wildcards: `*.github.com` matches subdomains only (not `github.com` itself). Base domain must be listed separately.

**Limitation**: This is an HTTP/HTTPS proxy. SSH (port 22), raw TCP, and other protocols **cannot traverse the proxy at all** [6]. The only workaround is `excludedCommands` or `allowUnsandboxedCommands`, which removes all sandbox protection for those commands.

### 1.6 `allowUnsandboxedCommands` Escape Hatch

**Default**: `true`

When a sandboxed command fails (e.g., network timeout, incompatible tool), Claude is prompted to analyze the failure. If the failure is sandbox-related, Claude can retry with `dangerouslyDisableSandbox: true` on the Bash tool call. This retried command then goes through the **normal permission flow** (user must approve).

Setting `allowUnsandboxedCommands: false` completely disables this. The `dangerouslyDisableSandbox` parameter is ignored. All commands must either:
- Run inside the sandbox, or
- Be listed in `excludedCommands` (which bypass sandbox but still require normal permission approval).

`excludedCommands` is an array of command prefixes (e.g., `["docker", "git"]`) that always run outside the sandbox. These commands use the standard permission flow instead.

---

## 2. Codex CLI Sandbox

### 2.1 What `workspace-write` Allows

In `workspace-write` mode, the writable scope is:

1. **CWD** (where the user started the session) -- this is always a writable root.
2. **`/tmp`** and **`$TMPDIR`** -- writable by default (can be excluded via `exclude_slash_tmp` and `exclude_tmpdir_env_var`).
3. **`writable_roots`** from config -- additional paths specified in `[sandbox_workspace_write]`.
4. **`--add-dir`** paths from CLI -- appended as additional writable roots.

After CVE-2025-59532, CWD is canonicalized and validated as the user's actual starting location, not model-generated paths [7].

**Read access**: Full disk read by default. The `disk-full-read-access` permission in `sandbox_permissions` is documented but the **Landlock restriction branch is a TODO** -- read restrictions are not enforced regardless of config [8].

### 2.2 Full List of Hardcoded Denied Paths

Within every writable root, these paths are **always read-only** (recursive):

| Path | Condition |
|---|---|
| `<writable_root>/.git` | Always (directory or file) |
| `<writable_root>/.git` resolved gitdir target | When `.git` is a pointer file (`gitdir: ...`), the resolved path is also protected |
| `<writable_root>/.codex` | When it exists as a directory |
| `<writable_root>/.agents` | When it exists as a directory |

That is the complete documented denylist. No shell configs, no SSH keys, no hooks -- only these three path patterns.

**Windows bug**: The Windows sandbox (`codex-rs/windows-sandbox-rs/src/allow.rs`) only denied `.git` when `.is_dir()` was true, leaving `.git` files (worktrees/submodules) unprotected. This was reported as issue #9313 [9].

### 2.3 How `--add-dir` Works in Codex

```bash
codex --cd apps/frontend --add-dir ../backend --add-dir ../shared
```

- Each `--add-dir` path is added as an additional writable root alongside CWD.
- Can be repeated for multiple paths.
- The same denylist (`.git`, `.codex`, `.agents`) applies to each added directory.
- `--add-dir` **cannot override the denylist** -- `.git` remains read-only in all writable roots.
- Equivalent to adding paths to `writable_roots` in config, but per-session.

### 2.4 `sandbox_permissions` -- Current State

The `sandbox_permissions` array accepts values like `"disk-full-read-access"` and `"disk-write-access"`. However:

- **`disk-full-read-access`**: The Landlock policy **always grants full read access** regardless of whether this permission is present. The restriction branch is a `TODO` in the codebase. `has_full_disk_read_access()` exists as a function but is effectively a no-op [8].
- **`disk-write-access`**: Not documented as functional. The actual write boundary is controlled by `sandbox_mode` + `writable_roots`.

**Verdict**: `sandbox_permissions` is partially implemented plumbing. It exists in the config schema and `--help` output, but the enforcement logic is incomplete. Do not rely on it for security boundaries.

### 2.5 `writable_roots` Config -- Does It Work?

Yes, but with caveats:

```toml
[sandbox_workspace_write]
writable_roots = ["/Users/me/.pyenv/shims", "/home/me/.cache"]
```

- **CLI**: Works correctly. CWD is appended (not overridden) to the configured roots.
- **VSCode extension**: Had a bug where it **overwrote** `writable_roots` with the current project directory instead of appending. Reported in issue #8029, closed with a workaround via "custom mode" [10].
- **Desktop app**: Similar overwrite behavior reported in issue #10439 [11].

The behavior should be: CWD + configured `writable_roots` + `--add-dir` paths = total writable scope. The denylist applies to all of them.

---

## 3. Edge Cases

### 3.1 Git Worktrees

**Claude Code**:
- The sandbox does not have special handling for `.git` files vs `.git` directories at the filesystem boundary level.
- `.git/hooks/**` is in the mandatory deny list regardless.
- The memory/CLAUDE.md traversal has a known issue: it traverses up through worktree boundaries, loading configs from the parent repo (#16600) [2]. A proposal exists to detect `.git` files (worktree indicator) and stop traversal.
- The sandbox itself treats the worktree directory as CWD and restricts writes accordingly -- the parent repo's `.git` directory is outside CWD and therefore read-only by default.

**Codex CLI**:
- Documented behavior: `.git` is protected as read-only "whether it appears as a directory or file" [12]. When `.git` is a pointer file, the **resolved gitdir target** is also protected.
- **Windows bug**: The `.is_dir()` check missed `.git` files, leaving worktree/submodule metadata writable [9]. This was identified and reported.
- macOS (Seatbelt) and Linux (Landlock) implementations handle `.git` files correctly per the security documentation.

### 3.2 Symlinks

**Claude Code**:
- Paths are resolved through `fs.realpathSync()` **before** generating sandbox rules [3].
- macOS `/var` -> `/private/var` symlink is explicitly handled: when a `$TMPDIR` matching `/var/folders/XX/YYY/T/` is detected, both `/var/` and `/private/var/` paths are allowed.
- Symlinks to targets outside the sandbox boundary are resolved to their real path and subject to normal rules. A symlink from CWD to `/etc/passwd` would resolve to `/etc/passwd` which is outside the writable root -> write denied.
- **Known limitation**: Creating symlinks targeting paths like `~/.local/bin` fails even when the directory is in `additionalDirectories` [13].

**Codex CLI**:
- Path canonicalization was the subject of CVE-2025-59532: the sandbox now canonicalizes paths to prevent bypass [7].
- The `.git` pointer file resolution (`gitdir: ...`) explicitly follows the pointer and protects the resolved target [12].
- No documented symlink-specific bypass vectors after the CVE fix.

### 3.3 Temp Files

**Claude Code**:
- `/tmp` is in default write paths.
- macOS `$TMPDIR` (`/var/folders/...`) auto-detected and allowed via `getTmpdirParentIfMacOSPattern()`.
- `~/.claude` is writable for internal state.
- **Bug**: Background tasks hardcode `/tmp/claude/` ignoring `$TMPDIR` [4].
- **Bug**: Bash tool may set `$TMPDIR` to root-owned directory on macOS [5].
- **Gotcha**: Shell heredocs (`<< EOF`) create temp files. If the temp directory is not writable or `$TMPDIR` is misconfigured, heredocs fail inside the sandbox [13].

**Codex CLI**:
- `/tmp` and `$TMPDIR` are writable by default in `workspace-write`.
- Can be excluded via `exclude_slash_tmp = true` and `exclude_tmpdir_env_var = true` in config.
- Linux: Entire environment is cleared and rebuilt with only necessary variables, including `$TMPDIR`.

### 3.4 Package Managers (`pip install`, `npm install`)

**Claude Code**:
- `pip install --user` writes to `~/.local/lib/` -- **outside** the sandbox write boundary. Will fail silently or with permission errors.
- `pip install` into a virtualenv inside CWD works (virtualenv dir is within CWD).
- `npm install` (local, within CWD) works. `npm install -g` writes to global node_modules -- fails.
- Workaround: Add package manager paths to `additionalDirectories` or use `excludedCommands` for the package manager command.
- Network access is required: package registries must be in `allowedDomains` (e.g., `*.npmjs.org`, `pypi.org`, `*.pythonhosted.org`).

**Codex CLI**:
- Same fundamental constraint: global installs write outside writable roots.
- `writable_roots` can be configured to include paths like `/Users/me/.pyenv/shims` [14].
- Network access is **off by default** in `workspace-write`. Must explicitly set `network_access = true`.
- `npm install` (local) works if network is enabled and CWD is writable.
- `pip install` into a local venv works. Global installs require `writable_roots` expansion.

---

## 4. Comparison Summary

| Dimension | Claude Code | Codex CLI |
|---|---|---|
| **Write boundary default** | CWD + subdirs | CWD + `/tmp` + `$TMPDIR` |
| **Write model** | Allow-only (explicit) | Allow-only (explicit) |
| **Read model** | Default allow, deny-only exceptions | Default allow (TODO: deny not enforced) |
| **Mandatory deny (write)** | Shell configs, `.git/hooks`, SSH keys | `.git`, `.codex`, `.agents` per writable root |
| **Additional write dirs** | `additionalDirectories` in settings, `/add-dir` command | `writable_roots` in config, `--add-dir` CLI flag |
| **Network default** | Proxy with domain allowlist + user prompts | **Off** (must opt-in `network_access = true`) |
| **Network mechanism** | HTTP/HTTPS proxy (no SSH/raw TCP) | seccomp blocks outbound sockets (except AF_UNIX) |
| **Escape hatch** | `allowUnsandboxedCommands` + `excludedCommands` | `danger-full-access` mode, `--yolo` flag |
| **OS enforcement (macOS)** | Seatbelt via `sandbox-exec` | Seatbelt via `sandbox-exec` |
| **OS enforcement (Linux)** | bubblewrap + seccomp + socat | Landlock + seccomp (optional bubblewrap for proxy) |
| **Symlink handling** | `realpathSync()` before rule generation | Canonicalization (post CVE-2025-59532 fix) |
| **`.git` protection** | Hooks always denied; `.git` dir itself not specially protected | `.git` (dir or file) + resolved gitdir always read-only |
| **Glob support in paths** | macOS: full glob; Linux: literal only | Not documented in path config |
| **`sandbox_permissions`** | N/A | Exists but Landlock read restriction is TODO -- non-functional |

---

## 5. Why the Boundaries Are Drawn Where They Are

### Claude Code rationale

The Anthropic engineering blog [15] explains:
- **Dual isolation is mandatory**: Filesystem without network allows exfiltration of SSH keys. Network without filesystem allows backdooring system resources to gain network access. Both must be enforced simultaneously.
- **CWD as boundary (not repo root)**: Minimizes blast radius. A monorepo with sensitive dirs is not fully writable just because you're in one subdirectory.
- **Default-allow reads**: Development tools need broad read access (compiler includes, system libraries, dependency caches). Restricting reads breaks too many workflows.
- **Default-deny writes**: Prevents modification of system files, shell configs, and other projects. The 84% reduction in permission prompts comes from defining trusted zones upfront.
- **Mandatory shell config deny**: Even if CWD contains `.bashrc` (unlikely but possible via path manipulation), writing to it enables privilege escalation when other users or cron jobs source it.
- **HTTP-only proxy**: SSH and raw TCP would require a full MITM proxy with certificate management. HTTP/HTTPS covers 95%+ of development tool network needs (package managers, APIs, git over HTTPS).

### Codex CLI rationale

The Codex security docs [12] explain:
- **`.git` always read-only**: Prevents the model from modifying git history, hooks, or config. A corrupted `.git/config` could redirect `git push` to an attacker's remote. Hooks could execute arbitrary code on the next `git commit`.
- **`.codex` and `.agents` read-only**: Prevents the model from modifying its own instruction files, which would be a self-modification attack vector.
- **Network off by default**: Unlike Claude Code's domain-filtered proxy, Codex takes a stricter stance. Development frequently requires zero network access (refactoring, code review). Enabling network is an explicit opt-in.
- **No shell config protection**: Codex relies on the writable root boundary being CWD. Shell configs live in `$HOME` which is outside CWD, so they are not writable by default. Claude Code adds explicit deny rules as defense-in-depth.
- **`sandbox_permissions` as plumbing**: The infrastructure exists for future granular control (e.g., MCP server isolation where an inner agent should not read outer agent workspaces). The TODO indicates this is planned but not yet critical for the primary use case.

---

## References

[1]: https://code.claude.com/docs/en/sandboxing "Claude Code Sandboxing Docs"
[2]: https://github.com/anthropics/claude-code/issues/16600 "Claude Code memory traversal should respect git worktree boundaries"
[3]: https://deepwiki.com/anthropic-experimental/sandbox-runtime/6.2-macos-sandboxing "sandbox-runtime macOS implementation (DeepWiki)"
[4]: https://github.com/anthropics/claude-code/issues/15700 "Background tasks ignore $TMPDIR and hardcode /tmp/claude/"
[5]: https://github.com/anthropics/claude-code/issues/23160 "Bash tool uses root-owned TMPDIR instead of user temp directory on macOS"
[6]: https://github.com/anthropics/claude-code/issues/24091 "Feature request: per-host SSH/TCP allowlist in sandbox network config"
[7]: https://advisories.gitlab.com/pkg/npm/@openai/codex/CVE-2025-59532/ "CVE-2025-59532: Codex sandbox bypass via model-generated cwd"
[8]: https://github.com/openai/codex/issues/11316 "sandbox_permissions: Landlock read restrictions not enforced (TODO)"
[9]: https://github.com/openai/codex/issues/9313 "Windows sandbox: .git file entries under writable roots are not denied"
[10]: https://github.com/openai/codex/issues/8029 "VSCode Codex doesn't respect writable_roots in config.toml"
[11]: https://github.com/openai/codex/issues/10439 "Codex Desktop appears to ignore writable_roots"
[12]: https://developers.openai.com/codex/security/ "Codex Security Documentation"
[13]: https://antisimplistic.com/posts/2026-02-02-claude-code-permissions/ "Claude Code Permissions and Sandboxing analysis"
[14]: https://developers.openai.com/codex/config-advanced/ "Codex Advanced Configuration"
[15]: https://www.anthropic.com/engineering/claude-code-sandboxing "Making Claude Code more secure and autonomous"
