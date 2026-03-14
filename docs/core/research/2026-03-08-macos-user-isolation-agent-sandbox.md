# macOS User Account Isolation for AI Agent Sandboxing

Research into using a dedicated non-admin macOS user account to isolate AI coding agents (Codex CLI, Claude Code). Conducted 2026-03-08.

## Context

The idea: create a non-admin user `agent`, share project worktrees via ACLs, run agents as that user via `sudo -u agent`. This provides OS-level isolation without VMs or containers, complementing existing Seatbelt/bubblewrap sandboxing.

## 1. macOS User-Level Isolation — How Strong?

### Default Home Directory Permissions

- Home directories: `drwxr-xr-x` (755) — world-readable by default [1]
- Subdirectories (Documents, Desktop, etc.): `drwx------` (700) + ACL `group:everyone deny delete` [2]
- Public and Sites folders: `drwxr-xr-x` (755) — intentionally world-readable
- Files created at home root: readable by all users by default [1]

**Implication**: A non-admin `agent` user cannot read files inside another user's Documents/Desktop/Downloads etc., but *can* see the home directory listing and any files placed directly in `~`.

### Non-admin vs Admin Capabilities

| Capability | Non-admin | Admin |
|---|---|---|
| Read other users' protected folders | No | Yes (via sudo) |
| Install system-wide software | No | No (needs sudo) |
| Modify /Applications | No | Yes (via sudo) |
| Access Keychain of other users | No | No [3] |
| Read /tmp, /var/tmp files | Yes (world-readable) | Yes |
| Write /tmp, /var/tmp | Yes (world-writable, sticky bit) | Yes |
| Use sudo | Only if in sudoers | Yes |

### /tmp and /var/tmp — Shared Attack Surface

- `/private/tmp` is world-writable with sticky bit (`drwxrwxrwt`) — any user can create files, but cannot delete others' files [4]
- `/var/folders/<hash>/` provides per-user temp directories (used by `NSTemporaryDirectory`) — more isolated [4]
- `/var/tmp` is also world-writable
- Risk: agent can read temp files created by other users in /tmp if permissions are lax

### SIP (System Integrity Protection) — Additional Layer

SIP restricts even root from modifying system files [5]:
- Protects `/System`, `/usr` (except `/usr/local`), `/bin`, `/sbin`, built-in apps
- Prevents code injection into system processes, unsigned kexts
- Uses mandatory access control (MAC) — not bypassable by any user including root
- Does NOT protect user home directories or `/usr/local`

**For agent isolation**: SIP prevents a compromised agent from modifying system binaries even if it somehow gains root. But it does not add user-to-user isolation beyond Unix permissions.

### Known Privilege Escalation Vectors (2025-2026)

Recent CVEs show the non-admin boundary is not absolute:

| CVE | Vector | Severity |
|---|---|---|
| CVE-2025-24118 | XNU kernel race condition → kernel access | Critical |
| CVE-2025-24085 | LaunchDaemon plist hijack → root | High |
| CVE-2025-32462/32463 | sudo chroot → root | Critical |
| CVE-2026-20614 | Path handling → privilege escalation | High |

Most require local access (which the agent has) but specific conditions. The sudo vulnerabilities are particularly relevant — keep macOS and sudo updated. [6][7]

## 2. Running CLI Tools as Another User

### `sudo -u agent command`

The primary mechanism. Works for CLI tools without GUI requirements.

```bash
# Basic usage
sudo -u agent /path/to/claude-code --args

# With environment variables (explicit, recommended)
sudo -u agent VAR1=value1 VAR2=value2 command

# Preserve caller's environment (risky — leaks all env vars)
sudo -E -u agent command

# With login shell (loads agent's .bashrc/.zshrc)
sudo -u agent -i command

# Via bash subshell (for complex env setup)
sudo -u agent bash -c 'export API_KEY="..."; export PATH="..."; command'
```

**Key behaviors** [8][9]:
- `sudo -u` does NOT load the target user's shell profile by default — add `-i` for that
- `sudo` clears most environment variables by default (security feature)
- The `-E` flag preserves environment but `env_reset` in sudoers can override it
- `HOME` is set to agent's home directory
- No GUI session — cannot run apps that need WindowServer

### `su - agent -c "command"` vs `sudo -u`

- `su -` loads a full login shell (reads `.profile`, `.bash_profile`)
- Requires the agent user's password (or root)
- `sudo -u` is preferred — uses caller's password, more configurable via sudoers

### `launchctl asuser` — macOS-specific

```bash
uid=$(id -u agent)
launchctl asuser "$uid" sudo -u agent command
```

Runs command in the target user's bootstrap context. Recommended when you need the agent user's launchd domain (e.g., for `defaults`, `launchctl load`). For plain CLI tools, `sudo -u` suffices. [9]

### Does the Agent User Need a Login Shell / GUI Session?

- **CLI tools**: No login or GUI session needed. `sudo -u agent` works from any admin terminal.
- **GUI apps**: Cannot run without a GUI session (WindowServer access denied). macOS does not support multiple simultaneous GUI sessions natively. [10]
- **Simulators/emulators**: Require GUI session. Not feasible for a headless agent user. Would need VNC/screen sharing workaround with Fast User Switching (max 5 concurrent switched users on macOS 10.13+). [10]

### launchd for Background Agent Services

A LaunchDaemon can run as any user via the `UserName` key:

```xml
<key>UserName</key>
<string>agent</string>
```

Runs at boot, no login required. Suitable for long-running agent services. LaunchAgents (per-user) require the user to be logged in. [9]

## 3. Sharing Project Directories Between Users

### ACLs vs POSIX Groups

| Feature | POSIX Groups | macOS ACLs |
|---|---|---|
| Granularity | owner/group/other | Per-user/group with specific rights |
| Inheritance | setgid bit (group only) | `file_inherit`, `directory_inherit` flags |
| New file ownership | Creator's UID, directory's GID (with setgid) | Creator's UID; ACL inherited from parent |
| Evaluation order | Single pass | Ordered ACE list, first match wins |
| Complexity | Low | Medium-high |

**Recommendation**: Use ACLs for the shared worktree. POSIX groups alone cannot handle the "agent creates files that the main user needs to modify" case without setgid + umask coordination. ACLs with inheritance are more reliable. [11][12]

### Practical ACL Setup for Shared Worktree

```bash
# Create shared worktree location
mkdir -p /Users/Shared/worktrees

# Set ownership
chown -R vre:staff /Users/Shared/worktrees

# Grant agent user full access with inheritance
chmod -R +a "user:agent allow list,add_file,search,add_subdirectory,delete_child,readattr,writeattr,readextattr,writeextattr,readsecurity,file_inherit,directory_inherit" /Users/Shared/worktrees

# Grant main user full access with inheritance
chmod -R +a "user:vre allow list,add_file,search,add_subdirectory,delete_child,readattr,writeattr,readextattr,writeextattr,readsecurity,file_inherit,directory_inherit" /Users/Shared/worktrees

# Verify
ls -ale /Users/Shared/worktrees
```

**Gotchas**:
- ACL inheritance only applies to *newly created* files/dirs. Existing files need `chmod -R +a` reapplied. [11]
- `chmod -R +ai` adds inheritance to existing ACEs recursively
- ACLs are invisible in Finder's Get Info (shows "custom access") — use `ls -ale` or TinkerTool System [12]
- Recursive ACL application can choke on files/dirs that already have different ACLs [13]

### Git with Multiple Users — safe.directory

Git 2.35.2+ refuses to operate on repos owned by different users (CVE-2022-24765 fix). Solutions [14]:

```bash
# Option 1: Add to agent user's git config
sudo -u agent git config --global --add safe.directory /Users/Shared/worktrees/my-project

# Option 2: Wildcard (less secure)
sudo -u agent git config --global --add safe.directory '*'

# Option 3: Use core.sharedRepository
cd /path/to/repo
git config core.sharedRepository group
```

**File ownership issue**: When agent commits, new files are owned by `agent:staff`. The main user can still read/modify via ACLs, but `git status` may show permission-related warnings. Using `core.sharedRepository = group` with both users in `staff` group helps. [15]

## 4. Prior Art — AI Agents as Separate macOS Users

### SandVault (most directly relevant)

GitHub: [webcoyote/sandvault](https://github.com/webcoyote/sandvault) — Apache 2.0, 2026.

Exactly this approach. Creates `sandvault-$USER` non-admin account, runs commands via `sudo -u` or SSH. [16]

**Architecture**:
- Shared workspace: `/Users/Shared/sv-$USER` (ACL-controlled)
- Readable: `/usr`, `/bin`, `/etc`, `/opt`
- Blocked: other home dirs, `/Volumes/*`
- Optional: nested `sandbox-exec` (Seatbelt) for additional restriction
- Supports Claude Code, Codex CLI, Gemini CLI

**Limitations**:
- GUI apps cannot run (WindowServer restriction)
- Apps already using sandbox-exec fail (no nested sandboxes on macOS)
- Without sandbox-exec layer: no protection against world-writable files or `/Volumes` access

### Other Sandbox Tools

| Tool | Mechanism | macOS Support | Notes |
|---|---|---|---|
| [Alcoholless](https://github.com/AkihiroSuda/alcless) | Custom sandbox profiles | Yes | Lightweight CLI wrapper around sandbox-exec |
| [ai-jail](https://github.com/akitaonrails/ai-jail) | sandbox-exec (macOS), bwrap (Linux) | Yes | Supports Claude Code, Codex, OpenCode |
| [agent-seatbelt-sandbox](https://github.com/michaelneale/agent-seatbelt-sandbox) | Seatbelt profiles | Yes | Focused on preventing data egress |
| [macbox](https://github.com/srdjan/macbox) | macOS sandbox | Yes | With Ralph loop integrated |
| [Clawboxed](https://clawboxed.ai/) | Separate macOS VM (Apple Silicon) | Yes | Full macOS isolation, $19/mo, uses virtualization not user accounts |
| Claude Code native | Seatbelt (macOS), bwrap (Linux) | Yes | Built-in `/sandbox` command, network proxy [17] |
| Docker Sandboxes | MicroVM | Linux only | [docker.com/ai/sandboxes](https://docs.docker.com/ai/sandboxes/) |

### Blog Posts / Discussions

- [INNOQ: "I sandboxed my coding agents"](https://www.innoq.com/en/blog/2025/12/dev-sandbox/) — Used Lima VM (Linux on macOS), shared directory mounting, explicit credential isolation. Half-day setup. Notes: user accounts share kernel/network/packages — not sufficient alone. [18]
- [Pierce Freeman: "A deep dive on agent sandboxes"](https://pierce.dev/notes/a-deep-dive-on-agent-sandboxes) — Compares OS-native (Seatbelt/Landlock), containers, command whitelists. OS-native = good isolation, low overhead. Full virtualization = best isolation, worst usability. [19]
- [Optimum Partners: "Enterprise AI Security: OS-Level Sandboxing"](https://optimumpartners.com/insight/the-sandbox-blueprint-securing-ai-agents-at-the-kernel-level/) — Recommends layered approach: compute boundary (kernel), MCP gateway (tool gating), deterministic lanes. "Application-level filters are security theater." [20]
- [Codex issue #215](https://github.com/openai/codex/issues/215) — sandbox-exec deprecated, but still functional. Apple has not removed it. [21]

## 5. Practical Issues

### Homebrew

Homebrew is designed for single-user use. Multi-user is explicitly unsupported. [22]

**Options**:
1. **Dedicated brew user**: Install Homebrew with a dedicated user, others use `sudo -Hu brew_user brew install ...` [22]
2. **Shared /usr/local**: Both users in `admin` group, fix permissions with `chgrp -R admin /usr/local/* && chmod -R g+w /usr/local/*` — breaks over time as new installs reset permissions [22]
3. **Agent uses main user's Homebrew via sudo**: `sudo -u vre brew ...` — ownership mismatch issues
4. **Agent gets own Homebrew in home dir**: Compiles from source (no bottles), slow [22]

**Recommendation**: Agent should use system tools from `/usr/bin`, `/usr/local/bin` (readable by all). Avoid having agent install packages. Pre-install everything needed as the main user.

### Xcode CLI Tools

- Installed system-wide at `/Library/Developer/CommandLineTools` — accessible by all users [23]
- Full Xcode at `/Applications/Xcode.app` — readable by all users
- No per-user installation needed

### Android SDK

- Default location: `~/Library/Android/sdk` (per-user)
- Can be installed at `/usr/local/share/android-sdk` for sharing [23]
- Needs ACL setup for multi-user write access
- `ANDROID_HOME` env var must be set for agent user

### SSH Keys & Git Credentials

All per-user — each user has independent:
- `~/.ssh/` — keys, config, known_hosts
- `~/.gitconfig` — user.name, user.email, credential helper
- macOS Keychain — per-user, not shared across accounts [3]

**For agent user**:
- Generate dedicated SSH key for agent
- Configure git with agent-specific identity
- Store API keys in agent's environment or a file in agent's home (not in shared keychain)
- Consider: keep git credentials out of agent entirely, use shared worktree only for code [18]

### API Keys — macOS Keychain

- Keychain items are per-user. One user cannot access another's keychain without explicit sharing. [3]
- The System Keychain (`/Library/Keychains/System.keychain`) is shared but typically stores system certificates, not API keys
- **Recommendation**: Pass API keys to agent via environment variables in `sudo -u agent bash -c 'export ANTHROPIC_API_KEY="..."; claude ...'` or store in agent's `~/.config/` files

## 6. macOS Fast User Switching / Multiple Sessions

### CLI Processes Without Login

- `sudo -u agent command` works without agent being logged in — no GUI session needed [8][9]
- LaunchDaemons with `UserName` key run at boot without login [9]
- Agent user does not even need a password if only accessed via `sudo -u` from admin account

### GUI Sessions

- macOS supports only one active GUI session (the physical display)
- Fast User Switching: up to 5 concurrent switched users (10.13+), but only one has the display [10]
- Other sessions are "backgrounded" — apps may be suspended or throttled
- Screen Sharing can provide VNC access to background sessions [10]

### Simulators / Emulators

- iOS Simulator requires Xcode and a GUI session — not feasible for headless agent user
- Android Emulator requires display or virtual display — same constraint
- Workaround: run simulators under main user, agent interacts via CLI tools (`xcrun simctl`, `adb`)

## 7. Assessment — User Account Isolation for AI Agents

### Strengths

1. **Zero overhead**: No VM or container startup. `sudo -u` adds ~2ms.
2. **Native toolchain access**: Agent uses same compilers, SDKs, runtimes as main user.
3. **Established mechanism**: Unix user isolation is decades-old, well-understood.
4. **Complementary**: Stacks with Seatbelt sandboxing (SandVault does this).
5. **SandVault exists**: Production-ready tool implementing exactly this pattern.

### Weaknesses

1. **Shared kernel**: Agent can exhaust CPU, memory, disk. No resource limits (without additional cgroups/launchd limits).
2. **Shared network**: Agent has full network access (no egress filtering without additional proxy/firewall).
3. **Shared /tmp**: World-readable temp files are accessible across users.
4. **No rollback**: Unlike VMs/containers, cannot snapshot and restore.
5. **Privilege escalation risk**: Non-zero — kernel CVEs exist. Not air-gapped.
6. **File ownership friction**: Agent-created files need ACL management. Git safe.directory config needed.
7. **No GUI**: Simulators/emulators cannot run under agent user without workarounds.

### Comparison with Alternatives

| Approach | Isolation | Overhead | Native tools | Network control | Rollback |
|---|---|---|---|---|---|
| User account (this) | Medium | None | Full | None (add-on) | No |
| User + Seatbelt (SandVault) | Medium-High | ~15ms | Full | Partial | No |
| Claude Code /sandbox | Medium-High | ~15ms | Full | Yes (proxy) | No |
| Lima VM | High | ~5s boot | Partial (Linux) | Configurable | Snapshot |
| Docker sandbox | High | ~2s | Linux only | Full | Yes |
| Clawboxed (macOS VM) | Very High | ~2s | Full macOS | Configurable | Yes |

### Recommendation

**Use SandVault** rather than building this from scratch. It implements the user-account approach with proper ACL management, and optionally layers Seatbelt on top. For the worktree-based workflow in this project:

1. `sv` creates the sandbox user and shared workspace
2. Create git worktrees in the shared workspace
3. Run agents via `sv exec claude ...` or `sv exec codex ...`
4. Agent operates in worktree with file isolation from main user's home
5. Main user reviews/merges from the same worktree location

For stronger isolation (network control, rollback), Claude Code's native `/sandbox` mode with Seatbelt + network proxy is already built-in and requires no additional user management.

## References

[1]: https://discussions.apple.com/thread/8132633 "Default folder/file permissions for users — Apple Community"
[2]: https://discussions.apple.com/thread/254305733 "macOS folder permissions and ACLs — Apple Community"
[3]: https://docs.github.com/en/get-started/git-basics/updating-credentials-from-the-macos-keychain "Updating credentials from the macOS Keychain — GitHub Docs"
[4]: https://wadetregaskis.com/creating-temporary-files-safely-in-mac-apps/ "Creating files safely in Mac apps — Wade Tregaskis"
[5]: https://support.apple.com/guide/security/system-integrity-protection-secb7ea06b49/web "System Integrity Protection — Apple Support"
[6]: https://gbhackers.com/apples-macos-vulnerability/ "CVE-2025-24118 macOS Kernel Vulnerability — GBHackers"
[7]: https://addigy.com/blog/macos-26-1-critical-security-update/ "macOS 26.1 Fixes Critical Sudo Vulnerabilities — Addigy"
[8]: https://scriptingosx.com/2020/08/running-a-command-as-another-user/ "Running a Command as another User — Scripting OS X"
[9]: https://www.launchd.info/ "A launchd Tutorial"
[10]: https://help.realvnc.com/hc/en-us/articles/360006973632 "Can each user have their own separate session on macOS? — RealVNC"
[11]: https://gist.github.com/nelstrom/4988643 "Setting ACL on OS X — GitHub Gist"
[12]: https://eclecticlight.co/2022/02/16/permissions-and-acls/ "Permissions and ACLs — The Eclectic Light Company"
[13]: https://www.codejam.info/2021/11/homebrew-multi-user.html "Using Homebrew on a multi-user system (don't) — CodeJam"
[14]: https://www.hrekov.com/blog/git-detected-dubious-ownership "Git Detected Dubious Ownership — Hrekov"
[15]: https://fabianlee.org/2018/12/02/git-sharing-a-single-git-controlled-folder-among-a-group-under-linux/ "Git: Sharing a single git controlled folder — Fabian Lee"
[16]: https://github.com/webcoyote/sandvault "SandVault — Run AI agents isolated in a sandboxed macOS user account"
[17]: https://code.claude.com/docs/en/sandboxing "Sandboxing — Claude Code Docs"
[18]: https://www.innoq.com/en/blog/2025/12/dev-sandbox/ "I sandboxed my coding agents — INNOQ"
[19]: https://pierce.dev/notes/a-deep-dive-on-agent-sandboxes "A deep dive on agent sandboxes — Pierce Freeman"
[20]: https://optimumpartners.com/insight/the-sandbox-blueprint-securing-ai-agents-at-the-kernel-level/ "Enterprise AI Security: OS-Level Sandboxing — Optimum Partners"
[21]: https://github.com/openai/codex/issues/215 "sandbox-exec deprecated on macOS — Codex GitHub"
[22]: https://github.com/orgs/Homebrew/discussions/4149 "Does brew support using a non-admin account? — Homebrew Discussion"
[23]: https://andrewli.blog/environment/mac-share-xcode-between-accounts/ "Sharing Xcode Projects Between User Accounts — Andrew's Blog"
