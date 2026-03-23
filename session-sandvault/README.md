# Session Sandvault Skill

Delegates tasks to agents (Codex/Claude) running inside a Sandvault macOS sandbox (separate non-admin user + Seatbelt kernel enforcement).

## Why not session-codex?

Codex `workspace-write` sandbox blocks build tools:
- Writes to `~/.gradle`, `~/.m2`, `~/.cargo` restricted to CWD
- Network blocked (seccomp denies outbound sockets)
- Loopback sockets blocked (Gradle daemon `bind`/`listen`)

Sandvault gives the agent a full OS environment while preventing host filesystem damage via user isolation + Seatbelt.

## How `sv` wraps agents

Sandvault installs wrapper scripts in the sandbox user's `~/bin/`:

- `codex` → `exec "$codex" --dangerously-bypass-approvals-and-sandbox "$@"`
- `claude` → `exec "$claude" --dangerously-skip-permissions "$@"`

The skill does not need to specify permission or sandbox flags — `sv codex` and `sv claude` add them automatically. Source: `/opt/homebrew/Cellar/sandvault/*/guest/home/bin/{codex,claude}`.

## When this skill is NOT needed

If the repo exists only inside sandvault (e.g., cloned directly with `sv -c <url>`), use `sv codex` / `sv claude` interactively. No sync needed, no skill needed.

This skill exists for the case where the host user has work that needs to be synced to the sandbox user and back.

## Architecture

```
Host user (vre)                    Sandvault user (sandvault-vre)
  /Users/vre/work/project/           Read-only (sandbox-exec deny)
    .git/                            Write OK (if profile-patched)
    .worktrees/feature/              Write OK (if profile-patched)
  /Users/Shared/sv-vre/              Write OK (shared workspace)
  localhost:5037 (adb)               TCP connect OK
  localhost:9222 (Chrome CDP)        TCP connect OK
```

Two isolation layers — both must allow an operation:
1. **macOS user isolation**: Unix permissions + ACLs
2. **Seatbelt (sandbox-exec)**: Kernel-level MAC, evaluated before ACLs

## Prerequisites

1. Install: `brew install sandvault && sv build`
2. Log into agents inside sandbox (one-time per agent):
   - `sv shell` → `codex` → complete login
   - `sv shell` → `claude` → `/login`
3. After brew upgrade of Claude/Codex: **run once on host first** to accept update prompts. Inside sandvault the upgrade acceptance dialog crashes.

Interactive use: `sv codex` and `sv claude` launch agents directly in sandbox. For non-interactive/scripted use (e.g., `codex exec --json`), use `sv shell PATH -- codex exec ...` instead — `sv codex` does not support subcommands like `exec`.

## Git worktree setup

Two options per project.

### Option A: Profile patch + ACLs (fast, fragile)

Grants sandbox write access to `.worktrees/` and `.git/`. Fragile: `sv build` overwrites the `.sb` profile — rerun after upgrade. Security tradeoff: `.git/` write access means the agent can modify hooks, config, refs.

See [Sandvault practical testing](docs/core/research/2026-03-11-sandvault-practical-testing.md) section 4 for exact commands.

### Option B: Shared bare repo (durable, more setup)

Creates shared bare repo at `/Users/Shared/sv-${USER}/<name>.git` as bridge between host and sandbox user. No profile patching needed. `core.sharedRepository=group` handles permissions.

Sync flow: host `git push shared <branch>` → sandbox `git fetch && git rebase`.

See [Sandvault practical testing](docs/core/research/2026-03-11-sandvault-practical-testing.md) section 7 for exact commands.

## Localhost service access

Sandvault's Seatbelt profile allows localhost TCP. Agent controls host-side GUI apps without display access:

- **Android emulator**: `adb` over `localhost:5037`. Full loop: build → install → `adb shell screencap` → visual validation (agent reads image).
- **Chrome DevTools**: CDP over `localhost:9222`. `Page.captureScreenshot` for visual feedback. Host starts Chrome with `--remote-debugging-port=9222`.
- **Dev servers, databases**: standard ports, no configuration needed.

## Limitations

- **No GUI**: sandbox user has no WindowServer access. For macOS GUI apps or iOS Simulator, use ClodPod (macOS VM with its own display).
- **No network isolation**: unrestricted outbound. Compromised agent can exfiltrate.
- **Shared `/tmp`**: both host and sandbox user read/write.

## Security comparison

- **vs Codex `danger-full-access`**: Sandvault is strictly stronger (has actual user + Seatbelt isolation)
- **vs Codex `workspace-write`**: Sandvault stronger on compatibility (build tools, network), weaker on write scope (broader than CWD-only)
- **vs Podman container**: Sandvault stronger on localhost access (native), weaker on network isolation (none)
- **vs ClodPod (macOS VM)**: Sandvault weaker on GUI support (none) and isolation strength, stronger on performance (zero overhead)

## Keychain and auth

Sandbox user has separate keychain. If keychain locks after sleep:
```bash
sv shell -- zsh -c "security delete-keychain ~/Library/Keychains/login.keychain-db; security create-keychain -p '' login.keychain-db; security default-keychain -s ~/Library/Keychains/login.keychain-db; security set-keychain-settings ~/Library/Keychains/login.keychain-db"
```
Then re-login: `sv shell` → `claude` → `/login`.

## Known issues

- `sv build` overwrites `.sb` profile — rerun `setup-profile-patch.sh` after brew upgrade
- `sv shell -c` means `--clone`, not shell `-c`. Commands go after `--`: `sv shell -- zsh -c "..."`
- Brew upgrade bumps version — `buildhome` script retains old Cellar paths. Fix: `sv -r shell`
- After brew upgrade of claude/codex: must run once on HOST first to accept update. Inside sandvault the first-run acceptance crashes.

## References

- [Sandvault](https://github.com/webcoyote/sandvault)
- [Container sandbox survey](docs/core/research/2026-03-08-container-sandbox-survey.md)
- [Sandvault practical testing](docs/core/research/2026-03-11-sandvault-practical-testing.md)
- [Sandbox boundary comparison](docs/core/research/2026-02-25-sandbox-boundary-comparison.md)
