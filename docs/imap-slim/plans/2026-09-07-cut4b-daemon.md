# SUPERSEDED — not built

**Dropped 2026-09-07 after measurement.** The daemon existed to share one IMAP connection
across processes. Measured on the day it was dropped: **11 imap-slim MCP processes running,
zero IMAP connections held** — `main()` is only `mcp.run()`, and nothing connects until an
action asks. The 2026-08-24 measurement this cut was built on showed four processes and *one*
connection; "four processes each holding a connection" was my restatement of it, repeated into
three later plans until it read as fact.

HC's usage is one session every few days. A stateless CLI holds **zero** connections between
commands, which is better for contention than a daemon holding one open for five minutes, and
needs none of the socket, lock, path-hardening, framing or lifecycle work below.

The daemon shape was copied from `chrome-control`, whose daemon exists because Chrome pops a
permission dialog on every new WebSocket connection. IMAP has no such dialog. The architecture
was inherited along with the file layout.

Kept for the analysis: the threat model for an unauthenticated socket carrying keychain-unlocked
mail, and the two review rounds that found the probe-cannot-tell-busy-from-dead flaw.

---

# Cut 4b: the daemon

Design record: `2026-09-07-cut4-daemon-and-cli.md` — the threat model, the framing rules and the
rejected designs live there and are not repeated. Cut 4a is merged.

Baseline: `cd tests && uv run pytest imap-slim/ -q` → **593 passed**.

Revision 2, after review. r1's liveness test was a socket probe with a bounded retry, which cannot
tell *dead* from *busy*: the daemon serves one request at a time, so during a 30 s action it cannot
answer, and a second starter would have unlinked its live socket and orphaned it. The lock, not the
probe, is now the liveness signal — see §3, which also removes r1's start-up deadlock and its
unconditional unlink.

## Intent

CLI callers must share one IMAP connection per account instead of each opening their own. That
needs a process that outlives a command, which means a socket, which — because this socket grants
full mailbox access with no further authentication — means the path is part of the threat model.

## Goal

`imapctl.py start` runs a daemon that owns the connections and serves `actions.run_action` over a
private unix socket. A thin client proves it end to end. Another local UID cannot connect, two
simultaneous starts produce one daemon, and no client can wedge it.

**Not in this cut:** the full CLI surface, exit-code mapping, `--format json`, `SKILL.md` — 4c. The
MCP still opens its own connection — cut 5.

## Design

### 1. Where it lives

```
$XDG_RUNTIME_DIR/imapctl/     only if XDG_RUNTIME_DIR itself passes validation
/tmp/imapctl-{uid}/           otherwise - and on macOS this is the normal path, not a fallback
        sock                  the socket
        lock                  the lifetime lock
```

**`XDG_RUNTIME_DIR` is untrusted input.** It comes from the environment, so validating only
`$XDG_RUNTIME_DIR/imapctl` leaves its parent under someone else's control: validate the child, and
the parent's owner can rename it and substitute another directory before `bind`. It is used only if
it is an absolute path and itself `lstat`s as a real directory, owned by the euid, mode `0700`, not
a symlink. Otherwise the `/tmp` path is used.

Validated with `lstat`, never `exists` or `stat`: a dangling symlink reports false from
`os.path.exists` while still defeating `bind`, and `stat` follows the link it is supposed to be
checking. Refuse — without touching it — anything at the directory path that is not a directory,
not owned by the euid, or not mode `0700`.

**Creation is one atomic attempt**, never check-then-create: `mkdir(path, 0o700)`, and on `EEXIST`
validate what is there. Never remove or "repair" an existing entry.

**A pathname validated is not a pathname bound.** Hold an open directory fd, open `lock` and bind
`sock` relative to it with `O_NOFOLLOW`, and re-check `(st_dev, st_ino)` against the fd before
binding. Validating a path and then operating on that path by name is a TOCTOU hole whenever a
parent component is not ours.

**What actually keeps other users out is directory traversal.** A genuinely private `0700`
directory means another UID cannot resolve `sock` at all. Mode `0600` on the socket is defence in
depth, not the mechanism: unix-socket permission enforcement on connect is not portable, and on
macOS an ACL can grant traversal that the mode bits do not show. The runtime directory is therefore
also checked for unexpected ACLs.

### 2. Binding without a permission window

`umask(0o077)` around `bind`, restored immediately after. `chmod` after `bind` leaves the socket at
the process umask for an instant, and a connection accepted in that instant cannot be revoked. The
mode is asserted afterwards, but as a check, not as the mechanism.

### 3. The lock is held for the daemon's lifetime, and it is the liveness signal

r1 asked a socket probe whether a daemon was alive. That cannot work here: serving is
single-threaded, so a daemon busy with a 30 s action answers nothing, and a bounded retry reads
*busy* as *dead*. The consequence is not a slow start — it is a second starter unlinking a live
socket and orphaning a daemon that still holds IMAP connections.

So: **`fcntl.flock(LOCK_EX | LOCK_NB)` is acquired by the daemon and held until it exits.** The
kernel releases it on death, including a crash, which makes it exactly the "is anyone alive"
question that a probe cannot answer. Advisory locking is sufficient because every implementation
here cooperates.

The protocol, with no step that waits on a step that waits on it:

1. `ensure_daemon_running` **never holds the lock**. It tries `send_command`; on success it is done.
2. Otherwise it spawns a contender and waits, bounded, for readiness.
3. The contender takes the lock non-blocking. **Failing to take it means a daemon is alive** —
   possibly busy — so the contender exits without touching anything, and the caller keeps waiting
   for readiness or reports "a daemon is running but did not answer in time". It never unlinks.
4. The winner, holding the lock, applies the staleness table, binds, calls `listen`, and only then
   publishes readiness. `bind` is not the boundary: a bound-but-not-yet-listening socket refuses
   connections and would look stale to anyone else.

Staleness, decided only by the process that *took* the lock:

| what is at the socket path | action |
|---|---|
| nothing | bind |
| a socket owned by the euid | unlink and bind — the lock was free, so no daemon owns it |
| a regular file, symlink, directory, or any other-UID entry | **refuse**, touch nothing |

No probe appears in this table, which is the point.

### 4. Serving

Single-threaded accept loop; the listening socket carries a timeout so the idle watchdog runs while
nothing is connected. Per connection:

- read incrementally to a newline against an **absolute deadline** taken from `time.monotonic()` at
  accept, each read given only the remaining budget. A per-read timeout would let a client sending
  one byte every nine seconds hold the only serving slot forever.
- cap the request at **1 MiB**, not 64 KiB: a `draft` payload carries a whole email body, and a
  100 KiB message is ordinary. The cap is a frame bound, not a product limit, and is stated in the
  error when exceeded.
- decode UTF-8, parse JSON, `MailAction.model_validate` for `cmd: "action"`
- malformed JSON, an oversized line, a missing field, a bad model or an unknown command all produce
  `{"ok": false, "error": ...}` — none of them kills the daemon
- write with a bounded deadline; `BrokenPipeError`, `ConnectionResetError` and timeouts mean "the
  client left", logged and skipped, never fatal

One request at a time, and the cost is named rather than hidden: a slow action delays `status` and
`quit` behind it. Requests for different accounts could run in parallel — the cut 2 lease is per
account — and that is left for later rather than claimed as unnecessary.

**The framing deadlines bound socket clients, not actions.** A well-formed request that triggers a
slow IMAP call blocks everything behind it for as long as that call takes, up to the 30 s socket
timeout per operation in `session.py`. "No client can wedge the daemon" is therefore a claim about
malformed, trickling and non-reading clients only, and AC5 is scoped to those.

**Idle** means time since the last request *completed*. An in-flight action does not count as idle,
so a long fetch cannot be interrupted by the watchdog.

### 5. Lifecycle

`quit`, idle expiry and `SIGTERM`/`SIGINT` all take the same path.

**Signal handlers only set a flag.** The loop owns every teardown step. A handler that logged out,
closed sockets or unlinked could run in the middle of a `sendall` or an IMAP operation and leave
both inconsistent. The cost is that a signal arriving during an action is acted on after that
action finishes: graceful shutdown means "after the in-flight request", and the accept timeout
bounds the idle case. The stronger claim — prompt exit under all conditions — is not available in a
single-threaded design and is not made.

**`LOGOUT` is bounded by lowering the transport timeout first.** `session.py` builds clients with a
30 s socket timeout, so N accounts logging out sequentially is N × 30 s of shutdown. Before
`logout()`, the remaining shutdown budget is set on the underlying transport; on expiry the
connection is `shutdown()` and the loop continues. Total shutdown budget: **5 s**.

A connection the cut 2 predicate already classified as dead is discarded with `shutdown()`, never
sent `LOGOUT` — that rule does not stop applying because the process is exiting.

**The socket is unlinked only by the process that bound it.** `owns_socket` is set after a
successful `bind`, together with the socket's `(st_dev, st_ino)`; cleanup unlinks only if that flag
is set and a final `lstat` still matches that identity. A contender that refused to start must
never reach an unconditional `finally: unlink` — it would delete the live daemon's socket, which is
the failure this whole section exists to prevent.

### 6. Client lifecycle helper

`imapctl_daemon.py`, shaped like `chromectl_daemon.py`: `send_command`, `ensure_daemon_running`
(idempotent, takes the lock), `daemon_context`. The spawned daemon's stdio goes to `DEVNULL` or a
log file, never to an unread `PIPE` — a daemon that logs enough would block on a full pipe with
nothing draining it.

## Acceptance Criteria

- [ ] **AC1 — the runtime directory is private and verified**

```gherkin
Given no runtime directory, when the daemon starts, it is created with mode 0700
Given a directory owned by another uid at that path, the daemon refuses and does not modify it
Given a regular file at that path, the daemon refuses
Given a symlink at that path, the daemon refuses, and lstat is what detects it
```

- [ ] **AC2 — the invariants that make another UID unable to connect**

The goal is that another local UID cannot connect. Mode bits alone do not prove that, so what is
asserted is every enforceable invariant, and what is assumed is stated as an assumption rather than
dressed up as a test:

```gherkin
Given the runtime directory, its mode is 0700, it is owned by the euid, and it carries no ACL
      granting any other user traversal
Given a freshly bound socket, its mode is 0600
And the umask was restrictive across the bind, not applied afterwards
Given the directory fd used for the bind, its (st_dev, st_ino) still match the validated directory
```

**Assumed, not tested here:** that the OS denies path resolution through a `0700` directory to
other UIDs. A cross-UID connect test needs a second account and is out of reach of this suite;
it is recorded as the security assumption the design rests on.

The same-UID boundary is documented: any process running as the user can connect, which is the
boundary the keychain already has.

- [ ] **AC3 — one daemon, even under a race**

Observable, not inferred: the probe response carries a random instance id and the daemon's pid.

```gherkin
Given two ensure_daemon_running calls released by a barrier from separate processes
Then both reach the same instance id
And exactly one long-lived daemon process remains
And the socket's inode is unchanged from the one the winner bound

Given a same-uid socket whose lock is free
Then it is unlinked by the lock holder and replaced

Given a live daemon busy with a long action
Then a second contender fails to take the lock, exits, unlinks nothing,
     and the socket inode is unchanged

Given a responsive daemon
Then ensure_daemon_running reuses it and spawns nothing
```

- [ ] **AC4 — CLI callers share one connection**

```gherkin
Given a daemon with a counting connection factory and three sequential requests for one account
Then the factory was invoked exactly once

Given requests for two different accounts
Then one connection per account, not one per request
```

- [ ] **AC5 — no client can wedge the daemon**

```gherkin
Given a client that connects and sends "{" with no newline
Then the absolute deadline expires, that connection is dropped, and the next request still succeeds

Given a client that sends one byte every nine seconds under a ten second deadline
Then it is still dropped at the absolute deadline, not kept alive by each read resetting it

Given a request one byte over the 1 MiB cap
Then the daemon answers with an error naming the cap and stays up
Given a request exactly at the cap
Then it is accepted

Given malformed JSON, a missing cmd, an unknown cmd, and params that fail model validation
Then each returns ok:false with a message naming the problem, and the daemon stays up

Given a client that disconnects before reading a large response
Then the daemon logs it, stays up, and serves the next request
```

- [ ] **AC6 — a response larger than the socket buffer arrives whole**

```gherkin
Given an action whose rendered text exceeds the socket buffer
Then the client receives all of it
```

- [ ] **AC7 — every exit path is bounded and clean**

```gherkin
Given quit, idle expiry, SIGTERM and SIGINT
Then in each case the process exits within the 5 s shutdown budget,
     LOGOUT is attempted on live connections within that budget,
     and the socket file is removed

Given a connection whose logout blocks on socket I/O
Then the transport timeout is lowered to the remaining budget and shutdown still completes in time

Given a contender that refused to start because a daemon holds the lock
Then it unlinks nothing, and the live daemon's socket inode is unchanged

Given LOGOUT raises or times out
Then the daemon still exits and still removes its socket

Given a connection the transport predicate calls dead
Then it is discarded with shutdown(), not sent LOGOUT
```

- [ ] **AC8 — idle is measured from request completion**

```gherkin
Given an action that runs longer than the idle timeout
Then the daemon does not exit underneath it, and exits after it completes
```

- [ ] **AC9 — end to end**

```gherkin
Given a stubbed action layer and no daemon running
When the thin client sends one request
Then a daemon auto-starts, the response comes back, and the socket exists afterwards
```

- [ ] **AC10 — the suite passes**

```gherkin
When `cd tests && uv run pytest imap-slim/ -q` is run, there are zero failures
```

## Testing Strategy

- **No credentials, no network, no real mailbox.** The daemon is started through a **test-only
  bootstrap** that imports the daemon and injects a stub runner directly. Shipping an environment
  variable that names an arbitrary module to import would be a code-execution hook in production
  code — not a new privilege against an attacker already running as this user, but dangerous the
  moment the daemon is launched from a context with a different environment, and an accidental
  production substitution waiting to happen.
- **AC3 uses two real processes and a barrier**, not two sequential calls in one process — the race
  is between processes and cannot be exercised any other way.
- **AC1's refusal cases are built with real filesystem entries** in a temp directory, including a
  dangling symlink, so `lstat` versus `exists` is actually distinguished.
- **AC7's SIGTERM case runs in a subprocess** and asserts on exit status and the socket's absence.
- **AC8 uses a short idle timeout and a stub action that sleeps past it**, asserting the daemon
  survives the action and exits after.
- Every socket test carries a bounded timeout so a failure is a failure rather than a hung suite.

## Out of Scope

- The full CLI surface, exit codes, `--format json`, `SKILL.md` — 4c.
- Routing the MCP through the daemon — cut 5.
- Parallelism across accounts — named in §4, deliberately not built.
- Windows.

## Tasks

- [ ] 1. `imapctl_daemon.py`: runtime directory resolution and lstat validation; socket and lock paths.
- [ ] 2. Startup lock; the staleness table; `ensure_daemon_running`; `send_command`.
- [ ] 3. `imapctl.py start`: umask-bound socket, accept loop, framing with caps and deadlines.
- [ ] 4. Request handling: validate, dispatch to `actions.run_action`, bounded write.
- [ ] 5. Idle watchdog measured from completion; signal handlers; bounded LOGOUT; `finally` unlink.
- [ ] 6. Thin client path in `imapctl.py` sufficient for AC9.
- [ ] 7. Tests AC1–AC9, with the stub-module hook.
- [ ] 8. Verify: zero failures.

## Files Changed

| file | change |
|---|---|
| `imap-slim/imapctl_daemon.py` | new — paths, lock, lifecycle helpers |
| `imap-slim/imapctl.py` | new — `start` role and a thin client |
| `tests/imap-slim/test_daemon.py` | new — AC1–AC9 |

## Reflection

<!-- Written post-implementation -->
