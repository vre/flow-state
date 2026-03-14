# Sandvault Practical Testing — macOS Agent Sandbox

**Date**: 2026-03-11
**Status**: Research complete
**Prerequisite**: [macOS User Isolation Research](2026-03-08-macos-user-isolation-agent-sandbox.md)
**Tool**: [Sandvault](https://github.com/webcoyote/sandvault) v1.1.27

---

## 1. Installation

```bash
brew install sandvault
sv build
```

### Installation Bug

`sv build` fails with:
```
rsync(57229): error: /opt/homebrew/Cellar/sandvault/1.1.27/guest/home/user: stat: No such file or directory
```

**Fix**: Create the missing directory before `sv build`:
```bash
sudo mkdir -p /opt/homebrew/etc/sandvault/guest_home_user
```

### What `sv build` Creates

- User `sandvault-vre` (uid 502) in group `sandvault-vre` (gid 502)
- Shared workspace `/Users/Shared/sv-vre/`
- Sandbox profile `/var/sandvault/sandbox-sandvault-vre.sb`
- Passwordless sudo from host user to sandvault user
- Home directory `/Users/sandvault-vre/`

## 2. Architecture — Two Isolation Layers

Sandvault uses **two independent layers**. Both must allow an operation for it to succeed.

### Layer 1: macOS User Isolation

Standard Unix permissions + ACLs. The `sandvault-vre` user is non-admin, separate from the host user.

### Layer 2: sandbox-exec (Seatbelt)

Mandatory access control via Apple's sandbox-exec. The profile at `/var/sandvault/sandbox-sandvault-vre.sb` defines allowed operations at kernel level.

**Key insight**: sandbox-exec evaluates *before* ACLs. If the Seatbelt profile denies a write, the kernel never checks Unix permissions or ACLs.

## 3. Write Permission Testing

| Path | Read | Write | Why |
|---|---|---|---|
| `/Users/vre/work/MathTrainer/` | OK | Blocked | sandbox-exec denies — outside allowed write paths |
| `/Users/vre/work/MathTrainer/.worktrees/` | OK | Blocked | sandbox-exec denies — ACLs irrelevant |
| `/Users/Shared/sv-vre/` | OK | OK | In sandbox-exec allow-list + correct ownership |
| `/Users/sandvault-vre/` | OK | OK | In sandbox-exec allow-list + home directory |
| `/tmp/` | OK | OK | In sandbox-exec allow-list |

### sandbox-exec Allowed Write Paths

From the `.sb` profile:
```scheme
(allow file-write*
    (subpath "/Users/Shared/sv-vre")        ; shared workspace
    (subpath "/Users/sandvault-vre")         ; sandbox user's home
    (subpath "/tmp")
    (subpath "/var/folders")
    (subpath "/dev")
)
```

### ACL Configuration (Tested but Insufficient Alone)

```bash
# Read access to project — works
chmod -R +a "sandvault-vre allow read,execute" /Users/vre/work/MathTrainer

# Write access to .worktrees — ACL applied correctly but sandbox-exec blocks
chmod -R +a "sandvault-vre allow read,write,execute,delete,add_file,add_subdirectory,file_inherit,directory_inherit" /Users/vre/work/MathTrainer/.worktrees
```

`ls -ale` confirms ACLs are set. `touch` still returns `Operation not permitted` — sandbox-exec denies at kernel level before ACL evaluation.

## 4. Git Worktree Compatibility

### Problem: git worktree Requires `.git/` Write Access

`git worktree add` always writes to the **parent repo's** `.git/` directory — creating ref locks, worktree metadata, and branch refs. This happens regardless of where the worktree directory itself is located.

Tested from sandbox:
```bash
# safe.directory configured — git can read the repo
git config --global --add safe.directory /Users/vre/work/MathTrainer

# Worktree target is in writable shared workspace — but still fails
git worktree add /Users/Shared/sv-vre/.worktrees/test-wt -b test-worktree
# fatal: cannot lock ref 'refs/heads/test-worktree':
#   Unable to create '/Users/vre/work/MathTrainer/.git/refs/heads/test-worktree.lock':
#   Operation not permitted
```

**Conclusion**: git worktree cannot work in Sandvault sandbox without `.git/` write access, regardless of worktree target path. This is a fundamental git constraint, not a Sandvault limitation.

### Working Setup (Tested)

Profile patch + ACLs on both `.worktrees/` and `.git/` — three layers must align:

```bash
# 1. sandbox-exec profile — host user patches .sb to allow writes
sudo sed -i '' '/subpath "\/Users\/sandvault-vre"/a\
    (subpath "/Users/vre/work/MathTrainer/.worktrees")\
    (subpath "/Users/vre/work/MathTrainer/.git")
' /var/sandvault/sandbox-sandvault-vre.sb

# 2. ACLs — grant sandvault-vre write access
chmod -R +a "sandvault-vre allow read,write,execute,delete,add_file,add_subdirectory,file_inherit,directory_inherit" /Users/vre/work/MathTrainer/.worktrees
chmod -R +a "sandvault-vre allow read,write,execute,delete,add_file,add_subdirectory,file_inherit,directory_inherit" /Users/vre/work/MathTrainer/.git

# 3. git safe.directory — sandbox user must trust the repo
# (run as sandvault-vre or in sandbox session)
git config --global --add safe.directory /Users/vre/work/MathTrainer
```

Result:
| Path | Read | Write | Status |
|---|---|---|---|
| Repo root | OK | Blocked | Intentional — source protected |
| `.worktrees/` | OK | OK | sandbox-exec + ACL + safe.directory |
| `.git/` | OK | OK | sandbox-exec + ACL (needed for worktree metadata) |

Git worktree create and remove both verified working.

### Solution Options

| # | Approach | Security | Durability | Effort |
|---|---|---|---|---|
| 1 | Profile patch + ACLs (above) | Good — scoped to `.worktrees` + `.git` | Fragile — `sv build` overwrites `.sb` | Low |
| 2 | `sv claude --clone <repo>` — full git clone to sandbox | Good — Sandvault's design | Stable | High (re-setup env) |
| 3 | `sv -x` (no-sandbox) | Weak — user isolation only | Stable | None |

**Option 2 (`--clone`)** is Sandvault's intended model: `git clone` to `/Users/sandvault-vre/repositories/<repo>/`. Full git history, sandbox user owns everything, worktrees work. **Downside**: all tooling (dependencies, caches, SDK paths) must be installed/configured for `sandvault-vre` user from scratch.

**Option 1 (profile patch)** is the pragmatic choice when the project environment is complex:

```bash
# Host user (vre) patches the sandbox profile
sudo sed -i '' '/subpath "\/Users\/sandvault-vre"/a\
    (subpath "/Users/vre/work/MathTrainer/.worktrees")\
    (subpath "/Users/vre/work/MathTrainer/.git")
' /var/sandvault/sandbox-sandvault-vre.sb
```

Risk: `sv build` (on upgrade) regenerates the profile — patch must be reapplied. A post-rebuild hook can automate this:

```bash
#!/bin/bash
# ~/.sandvault-post-rebuild.sh — run after sv build
PROFILE="/var/sandvault/sandbox-sandvault-vre.sb"
if ! grep -q "MathTrainer" "$PROFILE"; then
    sudo sed -i '' '/subpath "\/Users\/sandvault-vre"/a\
    (subpath "/Users/vre/work/MathTrainer/.worktrees")\
    (subpath "/Users/vre/work/MathTrainer/.git")
' "$PROFILE"
    echo "Sandvault profile patched for MathTrainer"
fi
```

**Note on `.git` write access**: granting `.git/` write weakens isolation — the agent can modify hooks, config, and refs. This is the same tradeoff as running without sandbox. Codex CLI explicitly denies `.git` writes for this reason [3].

## 5. Sandvault vs Claude Code Native /sandbox

| Dimension | Sandvault | Claude Code /sandbox |
|---|---|---|
| Write boundary | `/Users/Shared/sv-vre/` + sandbox user home | CWD + `additionalDirectories` |
| Read boundary | Full disk (non-protected paths) | Full disk (deny-list exceptions) |
| Network | Full (no filtering) | HTTP/HTTPS proxy with domain allowlist |
| User isolation | Yes (separate macOS user) | No (same user) |
| Enforcement | sandbox-exec + Unix permissions | sandbox-exec (Seatbelt) |
| Setup | `brew install sandvault && sv build` | `/sandbox` command |
| Credential isolation | Separate keychain, separate SSH keys | Same user's credentials accessible |

**Sandvault advantage**: credential isolation. Separate macOS user means separate keychain, SSH keys, git config. Claude Code /sandbox runs as the same user — credentials are readable.

**Claude Code /sandbox advantage**: network filtering. Sandvault has no network restrictions. A compromised agent can exfiltrate data freely.

## 6. Android Development from Sandbox

### adb Works from Sandbox

The Android emulator runs under the host user, but `adb` from sandbox can connect to it. Tested:

```bash
$ whoami
sandvault-vre

$ adb devices
List of devices attached
emulator-5554    device
```

`adb` is installed at `/opt/homebrew/bin/adb` — readable by all users. The emulator's adb server listens on localhost TCP, which sandbox-exec allows.

### Full Development Loop Verified

| Step | Command | Status |
|---|---|---|
| Build | `./gradlew clean build` | OK |
| Unit tests | `./gradlew test` | OK |
| Install to device | `./gradlew installDebug` | OK |
| Launch app | `adb shell am start -n <package>/<activity>` | OK |
| Screenshot | `adb shell screencap -p /sdcard/screen.png && adb pull ...` | OK |
| Visual validation | Read screenshot as image | OK |
| Logs | `adb logcat` | OK |

The agent can autonomously code, build, deploy, screenshot, and visually validate — no host user intervention needed for the development loop.

### Git Identity

`sv build` copies host user's `.gitconfig` to sandbox user. Commits from sandbox use the same identity (user.name, user.email) as the host user.

## 7. Shared Bare Git Repo Between Host and Sandbox

An alternative to worktree patching: a shared bare git repo in `/Users/Shared/sv-vre/` as a bridge. Host user pushes sources to the bare repo, sandbox user clones/pulls from it.

### Problem: Copied Bare Repo Ownership

Copying an existing bare repo into the shared workspace preserves the original ownership (`vre:staff`). The shared directory has correct group (`sandvault-vre`) with `g+rwx`, but **directory group inheritance only applies to newly created files** — copied files retain their original owner and group.

Even with the setgid bit (`g+s`) on the parent directory, two issues remain:
1. **Group inheritance** — setgid makes new files inherit the directory's group, but copied/moved files keep their original group
2. **Permission inheritance** — new files get permission bits from the process umask (default `022` = no group write), not the parent directory. macOS ACLs can force inherited write permissions, but umask + setgid alone cannot.

### Fix: One-Time Permissions + Git Shared Repository

```bash
# 1. Fix existing files (run as vre, the owner)
chgrp -R sandvault-vre /Users/Shared/sv-vre/MathTrainer.git
chmod -R g+w /Users/Shared/sv-vre/MathTrainer.git

# 2. Tell git to handle future objects (the real fix)
git -C /Users/Shared/sv-vre/MathTrainer.git config core.sharedRepository group
```

`core.sharedRepository=group` makes git create new objects as group-writable regardless of umask. No ACL tricks needed for ongoing use — git handles it internally.

### Workflow

```
Host (vre)                    Bare repo                     Sandbox (sandvault-vre)
  git push shared main  →  /Users/Shared/sv-vre/Repo.git  ←  git clone / git pull
```

Both users can read/write the bare repo. The sandbox user works on a full clone in its own writable space — no `.git/` write-access patches needed on the host repo.

## 8. Observations

1. **sandbox-exec is not deprecated in practice** — Apple deprecated the API but hasn't removed it. Both Sandvault and Claude Code rely on it (macOS).
2. **Two-layer model is sound** — user isolation catches what sandbox-exec misses (e.g., credential separation). sandbox-exec catches what user isolation misses (e.g., world-writable paths).
3. **ACLs are a red herring with sandbox-exec** — setting up ACLs on paths outside the sandbox profile is wasted effort. The sandbox blocks before ACLs are evaluated.
4. **git worktree is fundamentally incompatible with read-only source repos** — `git worktree add` writes to the parent repo's `.git/` regardless of worktree location. No workaround exists without granting `.git/` write access.
5. **Sandvault's design assumes clone, not worktree** — `sv --clone` creates a full git clone in the sandbox user's space. This is the intended workflow but requires re-setting up the development environment.
6. **Profile patching is pragmatic but fragile** — adding project-specific paths to the `.sb` profile works but breaks on `sv build`. Requires a post-rebuild hook.
7. **No network isolation is a significant gap** — for "yolo" use cases where the agent has broad autonomy, network exfiltration is the primary risk that Sandvault does not address.
8. **Shared bare repo is the cleanest bridge** — avoids profile patching and `.git/` write access. `core.sharedRepository=group` is the key setting — without it, git objects created by one user are unwritable by the other regardless of directory permissions.
9. **File ownership doesn't inherit on copy** — macOS setgid + ACLs only affect newly created files. Copying or moving files into a shared directory preserves original ownership. Always fix permissions after copying.

## References

[1]: https://github.com/webcoyote/sandvault "SandVault — Run AI agents isolated in a sandboxed macOS user account"
[2]: docs/core/research/2026-03-08-macos-user-isolation-agent-sandbox.md "macOS User Account Isolation for AI Agent Sandboxing"
[3]: docs/core/research/2026-02-25-sandbox-boundary-comparison.md "Sandbox Boundary Comparison: Claude Code CLI vs Codex CLI"
