# Cut 2: make connection failure cheap and legible

Frame: `2026-08-24-frame-imap-slim-cli-daemon.md`. **Promoted ahead of cut 1** on 2026-08-26.

Revision 5. r1 proposed skipping the probe and retrying inside `connection_ctx`; both were
wrong, see §Rejected. r2 downgraded the plan to instrumentation because the root cause looked
unresolved. **r3 restores the claim that this fixes the outage**: HC excluded connection quota on
2026-08-26, and the objection that killed r2 dissolves under HC's actual call pattern — see
§Root cause. r4 fixes five defects found in the r3 review, all confirmed against the source:
`IMAPError` is a plain `Exception` so the discard path never fired for wrapped read failures;
`get_folders`/`get_messages` do network work outside any lease; the preview path swallows
connection loss; `except IMAPError` precedes the generic handler so classification would be
bypassed; and `last_activity` is stamped from a timestamp captured before the slow work. r5 adds the
typed `ConnectionFailure` envelope, an errno allowlist, login-client cleanup, and — from the r5
review — the rule that **every** exception handler inside a lease must re-raise transport
failures, not just the read and preview paths.

## Intent

Reported symptom: after `/mcp-reconnect`, ten calls succeed, then every call times out until
reconnect. Every call currently pays up to a full 30 s socket timeout to discover a dead
connection, and whatever the cause turns out to be, the returned error names none of them.

## Goal

A call made after a long pause completes in about a second instead of timing out: no code path
spends a socket timeout on a connection it already believes is dead. One IMAP operation cannot
interleave with another on the same connection. Every connection failure reports which cause it
was and the stage it failed at.

## Situational Context

Measured 2026-08-26 against a fake IMAP server that completes `LOGIN` then goes permanently
silent — what an idle-reaped connection looks like from the client. Production socket timeout
is 30 s (`session.py:94`); the fixture uses 3 s and the column scales it:

| call | elapsed | × timeout | raises | at production |
|---|---|---|---|---|
| `noop()` on dead socket | 3.00 s | 1.0 | `TimeoutError` | 30 s |
| `logout()` **after** a timed-out `noop()` | 0.00 s | 0.0 | `OSError` | free |
| `logout()` on an **unprobed** silent socket | 3.00 s | 1.0 | `TimeoutError` | **30 s** |

The third row is the one that matters and it is the reason r1's design was worthless: skipping the
probe still routes into `_close_connection()` → `logout()` (`session.py:155`), which is itself an
IMAP command on the dead socket and pays the full timeout. `logout()` is only free *after*
imaplib has already marked the connection broken.

Current code:

- `CONNECTION_IDLE_TIMEOUT = 300` (`session.py:15`) — proactive close only after 5 minutes.
- `get_connection` (`session.py:128-149`) — probes with `noop()` (`:137`), closes on exception,
  reconnects. Runs **unlocked**; `self.lock` guards only the caches.
- `_close_connection` (`session.py:151-158`) — `logout()` in try/except.
- `connection_ctx` (`session.py:160-172`) — closes and re-raises. No retry.
- All causes collapse into `except Exception: return f"Error: {type(e).__name__}: {e}"`
  (`imap_stream_mcp.py:966`).

### Root cause: stale socket, and why "it should self-heal" was a red herring

Connection quota was excluded by HC on 2026-08-26. What remains is the server reaping idle
connections earlier than the 300 s the code waits before dropping one.

Review objected that this cannot be the cause, because after one 30 s failure `get_connection`
closes the connection and reconnects, so the session should self-heal and the *next* call should
be fast. It does self-heal. Every time. The objection assumes the next call comes soon:

```
call after a pause -> noop() on the reaped socket   30 s   <- the caller's deadline expires here
                   -> logout()                      free   (imaplib already marked it broken)
                   -> reconnect + login            ~1 s
                   -> the command then succeeds, with nobody left listening
```

HC's reported pattern is three calls in about ten minutes, sequential, each awaited — roughly
three minutes apart, well beyond any plausible reaping window. So **every** call starts cold and
pays the full timeout. Nothing is stuck; the failure recurs per call, which from the caller's side
is indistinguishable from stuck. The ten calls that succeed after `/mcp-reconnect` are made in
quick succession, inside the window, on a connection that never goes cold.

So the fix is to make the cold path cheap, which is exactly §1 and §2 below: discard costs no
network round trip, and a fresh login is ~1 s. The stage-and-cause reporting in §4 stays, because
a failure that still says only `Error: TimeoutError: timed out` is unfalsifiable next time.

## Constraints

- No private imapclient API. `IMAPClient.socket()` is documented as polling-only, so per-command
  socket timeouts are out. `IMAPClient.shutdown()` **is** public and documented as "close the
  connection without logging out" — that is the discard path.
- Wall clock (`time.time()`) kept, unchanged: a host that slept must count as long-idle, and the
  wall-clock jump is what delivers that.
- Existing suite green. `tests/imap-slim-mcp/test_session.py` pins the 300 s threshold and the
  probe-on-every-call behaviour; those assertions change and are enumerated in the diff.
- No change to caching, folder listing, or command semantics.

## Design

### 1. Discard, never `logout()`, a connection suspected dead

```python
def _discard_connection(self):      # replaces _close_connection on the failure path
    if self.connection:
        try:
            self.connection.shutdown()      # closes the socket, sends nothing
        except Exception:
            pass
        self.connection = None
```

`logout()` is kept only where the connection is believed healthy. Precisely: this removes the
blocking `logout()` from **both** paths, and removes the **full timeout** from the long-idle path.
A connection that dies inside the 60 s window still spends its timeout in `noop()` — §2 says so,
and this paragraph must not claim otherwise.

### 2. Do not probe a long-idle connection

```python
CONNECTION_MAX_IDLE = 60      # was CONNECTION_IDLE_TIMEOUT = 300
```

Idle beyond it → `_discard_connection()` and reconnect, no probe. Within it → `noop()` as today.

Not tuned to the server's reaping window, which is unknown and varies by server and network path.
It bounds the damage: the probe is only reachable for a connection used within the last minute.
**A connection that died within that minute still costs a full timeout** — that case is not solved
here, and the goal is worded to say so.

### 3. One lease per operation, covering every network use

A single internal `_lease()` context manager acquires `self.lock`, yields a connection, stamps
`last_activity` on success, and on failure decides whether to discard (see §4). `connection_ctx`
becomes its public wrapper.

**The cached fast paths stay outside the lease.** `get_folders` returns `folder_cache` before
touching the network (`session.py:180-184`), and `get_messages` validates its cache against
`select_folder` metadata. Only the network portions move inside; a cache hit must not start
requiring a connection, or a cached read would begin failing on network errors — which the
"no change to caching" constraint forbids.

**`get_folders` and `get_messages` otherwise must use it.** They currently call `get_connection()`
directly and then run `list_folders()`, `select_folder()`, `search()` and `fetch()` outside any
lease (`session.py:174-313`), so whole-operation locking applied only to `connection_ctx` would
leave the two most frequent paths unserialised — free to interleave commands on one IMAP stream,
and free to have their connection discarded underneath them by another caller's failure.

`_sessions_lock` is never held while acquiring a session lock or doing network I/O.

**`last_activity` is stamped after the work, not before.** Today `now` is captured at entry
(`session.py:130`) and applied at `:148`, so a connection is aged by however long the probe and
login took — after a failed probe plus reconnect, a brand-new connection is born ~31 s old. Stamp
on successful establishment and again at the end of each completed operation, using `time.time()`
for the idle clock and `time.monotonic()` for measuring elapsed durations.

### 4. One predicate for "the transport failed", used twice

```python
def is_transport_failure(exc, *, stage): ...   # walks __cause__ / __context__
```

Matched types, deliberately **not** bare `OSError`:

| stage | treated as transport failure |
|---|---|
| `connect` | any `OSError` raised by the **network** portion — see the split below |
| `probe`, `command` | `TimeoutError`, `ConnectionError` and subclasses, `IMAPClientAbortError`, and `OSError` whose `errno` is in the allowlist |

Type families alone are both under- and over-inclusive, so:

- **errno allowlist** for command-stage `OSError`: `ENOTCONN`, `EHOSTUNREACH`, `ENETDOWN`,
  `ENETUNREACH`, `ENETRESET`, `ECONNABORTED`, `ECONNRESET`, `EPIPE`, `ETIMEDOUT`. Without it,
  `OSError(ENOTCONN)` and `OSError(EHOSTUNREACH)` are genuine transport deaths that would leave
  the corpse cached, because neither is a `ConnectionError` or `TimeoutError`.
- **`IMAPClientAbortError` only, never the generic `IMAPClientError`.** An illegal-state or
  rejected-command protocol error does not mean the transport died, and discarding on it would
  throw away a healthy connection.
- **The lease contains no local file I/O.** `download_attachment` currently writes the attachment
  to disk inside the lease, and a disk `TimeoutError` or `ETIMEDOUT` — from a slow or
  network-mounted filesystem — is *indistinguishable by type or errno* from an IMAP timeout. No
  allowlist can separate them, so the fix is provenance by construction: fetch inside the lease,
  write outside it. `PermissionError` and `ENOSPC` then cannot reach the predicate either.
- **The connect stage is split.** `_create_connection` (`session.py:89-96`) calls
  `get_credentials()` before touching the network, so a keyring `PermissionError` would otherwise
  be reported as a lost server connection. Credentials are fetched in a `config` stage, and only
  the `IMAPClient(...)` + `login()` portion is the `connect` stage.
- **A rejected login must not leak its client.** `_create_connection` assigns `client` to a local
  and then calls `login()`; if that raises, the client is never returned, never stored, and so
  `_discard_connection()` can never close it — on a connection-limited server that leaks a slot
  until garbage collection. Wrap it: on any failure after construction, `client.shutdown()`, then
  re-raise. If `shutdown()` itself raises, that failure is suppressed and the original login
  exception is what propagates — cleanup must never mask the reason.

The predicate walks the cause chain because the read paths wrap failures into `IMAPError`
(`imap_client.py:610-615` and the equivalents in `download_attachment` and `search_messages`), and
**`IMAPError` is a plain `Exception`** — not `OSError`, not `IMAPClientError` — so today
`connection_ctx`'s `except (OSError, IMAPClientError, ConnectionError)` never fires for them and
the dead connection survives in the cache. That is a second, independent route to the reported
symptom.

It is used in exactly two places:

1. **the lease** — decides whether to `_discard_connection()`
2. **the boundary** — decides what to tell the caller

**Stage and elapsed propagate in a typed exception, not by re-raising the original.** The lease
cannot re-raise unchanged and still let the boundary know which stage failed: the two handlers in
`imap_stream_mcp.py` receive only an exception. So a surfaced failure is re-raised as
`raise ConnectionFailure(stage, elapsed) from original` — standard chaining, with `stage` and
`elapsed` as fields and the original reachable as `__cause__`, which is what AC12 asserts against.
The boundary matches on the type rather than re-deriving anything, and the cause chain is walked
only inside the predicate.

**The envelope is wider than the discard predicate.** `LoginError` is not a transport failure — it
must not trigger a discard, since nothing is connected to discard — but it *is* a connect-stage
failure, and the Goal promises every connection failure carries its stage. So the lease wraps a
surfaced `LoginError` in `ConnectionFailure(stage="connect", ...)` too, and the boundary reads its
`__cause__` to choose between quota and general login rejection. Two separate questions: *should
this be discarded* (transport only) and *should this be enveloped* (any surfaced connect-stage
failure).

Better still at the source: **no handler inside a lease may swallow a transport failure.** This is
a rule to audit against, not a list of three known sites, because every such handler silently
defeats the discard, lets `last_activity` be stamped as if the operation succeeded, and prevents
any `ConnectionFailure` from reaching the boundary. The known sites:

- the read-path wrappers, which do `except Exception as e: raise IMAPError(...) from e` — a
  transport failure is re-raised unchanged instead
- the preview path in `get_messages` (`session.py:264, 273, 295`), which turns a lost connection
  into empty snippets and a successful-looking result
- **`modify_flags` (`imap_client.py:1500-1520`)**, whose per-message `except Exception` blocks
  convert a `TimeoutError` from `add_flags`/`remove_flags` into an entry in `result["failed"]`,
  and the same for its `search()` and final `fetch()`

In each, non-transport command errors keep their current per-message or per-field handling; only
transport failures are re-raised. Nothing is retried or replayed, so no mutation repeats.

### 5. Report the cause, at one boundary with stated precedence

| condition | reported as |
|---|---|
| `LoginError` matching `too many connections`, `maximum number of connections`, or `connection limit` (case-insensitive) | connection limit reached — other sessions or your mail client hold the quota |
| `LoginError` otherwise | login rejected by the server, sanitized server text preserved; credentials named as one possible cause, not asserted |
| transport failure per §4 | connection to the server was lost |

The quota pattern requires connection context: `Maximum login attempts exceeded` matches
`maximum` and `exceeded` but is not a quota message, and is a negative test.

`imap_stream_mcp.py` catches `except IMAPError` at `:934` **before** `except Exception` at `:966`,
so classification placed only ahead of the generic handler would be bypassed for exactly the
wrapped errors it exists to catch. Classification runs as a helper invoked from both handlers,
with `IMAPError` checked first, and the precedence is stated in the code.

**Surfaced vs recovered.** A probe failure that is transparently replaced never reaches the caller
and must not manufacture an error message. Only failures that reach the boundary carry `stage` and
elapsed. Recovered ones produce nothing — no counter, no log line. Diagnostics for them would be a
separate decision with its own destination and test, not an unspecified promise here.

### Rejected

- **Retry inside `connection_ctx`** (r1 Design §2). `contextlib.contextmanager` yields once; an
  exception thrown back at the `yield` can be suppressed or transformed, but the caller's `with`
  body cannot be re-run. The design was unimplementable as written. Retry needs an operation
  runner — `run_with_connection(fn, retry=...)` — owning a two-attempt loop. **Deferred to a
  later cut**, because it must be designed against the confirmed cause and because retry is unsafe
  for `client.append` (`imap_client.py:1135`, `:1302`) and the `delete_messages`+`expunge` pair
  (`:1304-1305`), which would duplicate drafts.
- **Skip the probe to save the timeout** (r1 Design §1). Measured worthless without §1 above.
- **`atexit` + `SIGTERM` logout.** Installing a SIGTERM handler replaces whatever is there,
  and a handler that logs out and returns suppresses termination; a blocking `LOGOUT` can add a
  timeout per session to shutdown. Process exit closes the sockets anyway. Deferred until there is
  evidence the server does not free the slot on TCP close.
- **Tuning `CONNECTION_MAX_IDLE` to the live server's window.** Needs a long-running probe against
  HC's server, holding a contended connection slot, for a number that is not portable.

## Acceptance Criteria

- [ ] **AC1 — a suspected-dead connection is discarded, not logged out**

```gherkin
Given a cached connection and a reason to believe it is dead
When the session discards it
Then shutdown() is called and logout() is not
And self.connection is None afterwards
```

- [ ] **AC2 — a long-idle connection is replaced without probing**

```gherkin
Given a cached connection whose last activity was 61 seconds ago
When a connection is acquired
Then noop() is never called, shutdown() is, and a new connection is created

Given last activity was exactly 60 seconds ago
Then the recent path is taken: noop() is called exactly once and the connection is reused
```

- [ ] **AC3 — a recently used connection is probed, and a failed probe is recovered silently**

```gherkin
Given a cached connection whose last activity was 5 seconds ago
When a connection is acquired
Then noop() is called once and the same connection is returned

Given that noop() raises TimeoutError
Then the connection is discarded via shutdown(), a new one is created,
     and the caller receives the new connection with no error surfaced

Given that noop() raises a non-abort IMAPClientError
Then the connection is NOT discarded, matching the transport predicate
```

- [ ] **AC4 — the dead-socket path is bounded, measured against the server's own log**

```gherkin
Given the fake IMAP server that completes LOGIN then goes silent
And a cached connection to it, last active 61 seconds ago
When a connection is acquired
Then the server's received-command log contains neither NOOP nor LOGOUT
And the call completes in under 1.0 s against the fixture's 3 s socket timeout
```

The command log is the primary evidence; elapsed time is the secondary check, so the test cannot
pass for the wrong reason nor flake on a loaded machine.

- [ ] **AC5a — two healthy concurrent callers are serialised on one connection**

```gherkin
Given two threads released by a barrier placed BEFORE they enter the lease
When both run an operation on the same session
Then their operation bodies never overlap in time
And the connection factory is invoked exactly once
```

The barrier must be outside the lease: inside the bodies it would deadlock, since the first holds
the lock while waiting for the second to enter.

- [ ] **AC5b — a failing caller cannot discard a healthy caller's connection**

```gherkin
Given the first caller's operation raises a transport failure
Then it discards its own connection before releasing the lock
And the second caller creates a replacement, so the factory is invoked twice
And the second caller never receives the discarded connection object
```

- [ ] **AC6 — every network path holds the lease**

```gherkin
Given get_folders and get_messages, including the preview=True snippet fetch
Then all of their IMAP calls run inside the lease
And two concurrent get_messages calls do not overlap
```

- [ ] **AC7 — a wrapped transport failure is both discarded and classified**

```gherkin
Given select_folder raises TimeoutError inside read_message
Then read_message re-raises it unchanged rather than wrapping it
And the lease discards the connection and session.connection is None

Given an IMAPError raised from a TimeoutError cause reaches the boundary
Then it is classified as a lost connection via the cause chain
And it reaches the classifier despite except IMAPError preceding except Exception

Given an OSError with errno ENOTCONN raised during a command
Then it is treated as a transport failure and the connection is discarded

Given an IMAPClientError that is not an abort, such as a rejected command
Then the connection is NOT discarded
And it is NOT classified as a lost connection at the boundary

Given modify_flags whose add_flags raises TimeoutError
Then it is re-raised rather than recorded in result["failed"]
And the connection is discarded

Given get_messages with preview=True whose snippet fetch raises TimeoutError
Then the failure is not swallowed into empty snippets
And the connection is discarded

Given download_attachment
Then the file write happens outside the lease, so a PermissionError, an ENOSPC
     or a local TimeoutError from the filesystem never reaches the predicate
And none of them is classified as a lost connection or discards the connection

Given a ValueError
Then it is not classified as any connection cause
```

- [ ] **AC8 — causes are named, without overstating**

```gherkin
Given a LoginError containing "Maximum number of connections exceeded"
Then the message states the connection limit is reached and names other sessions or the mail client

Given a LoginError containing "Maximum login attempts exceeded"
Then it is NOT reported as a connection-limit failure

Given a LoginError containing "Invalid credentials"
Then the message states the server rejected the login, preserves the server text,
     and does not assert that the credentials are wrong
```

- [ ] **AC9 — surfaced failures carry stage and elapsed; recovered ones do not**

```gherkin
Given a failure surfaced from the connect stage and from the command stage
Then each message names its stage and its elapsed duration, measured with time.monotonic()

Given a probe failure that was transparently recovered
Then no error message is produced for it
```

- [ ] **AC10 — a new connection is not born stale**

```gherkin
Given a probe that consumes 30 seconds and a login that consumes 1 second, with mocked time
When the connection is established
Then its last_activity reflects the moment establishment completed, not the moment the call began
And a subsequent acquisition 5 seconds later takes the recent path
```

- [ ] **AC11 — a rejected login does not leak its client**

```gherkin
Given IMAPClient construction succeeds and login() raises
Then shutdown() is called on that client before the error propagates
And the session holds no connection afterwards

Given login() raises LoginError and the subsequent shutdown() also raises
Then the LoginError is what propagates, not the shutdown failure
```

- [ ] **AC12 — the boundary receives the stage, it is not supplied by the test**

```gherkin
Given a transport failure at the connect stage and one at the command stage
When each reaches the reporting boundary
Then the boundary reads stage and elapsed off the raised ConnectionFailure
And reports the stage that actually failed

Given a LoginError raised by login()
Then it too arrives as ConnectionFailure with stage "connect" and an elapsed duration
And the boundary reads its __cause__ to choose quota versus general login rejection
And the connection is NOT discarded, since none was established
```

- [ ] **AC13 — no regression**

```gherkin
Given the suite green before this change, run as: cd tests && uv run pytest imap-slim-mcp/ -q
Then every pre-existing test passes except those pinning the 300-second threshold or the
     probe-on-every-call behaviour, which are listed by name in the commit message
```

## Testing Strategy

- **Unit, mocked**: AC1–AC3 and AC10–AC12 in `test_session.py`; AC7–AC9 and AC12's boundary half
  in a new `test_error_classify.py`; the `modify_flags` scenario of AC7 in `test_imap_client.py`.
  Existing `Mock(spec=IMAPClient)` + `patch` pattern throughout. AC10 patches the clock.
- **Integration, fake server**: AC4 only. The fixture records every command line received, exposes
  a readiness event, bounds its thread join on teardown, and runs plaintext `ssl=False` — stated
  explicitly as not exercising the production `ssl=True` path.
- **Concurrency**: AC5a, AC5b and AC6 with `threading.Barrier` placed before the lease, and
  recorded enter/exit intervals per thread so overlap is detected rather than assumed.
- **Manual**: none. The live symptom needs a server-side reap; the fake server is the instrument.
- Outside-in per AC: failing test first, then implementation.

## Out of Scope

- **Retry.** See §Rejected. Later cut, built as an operation runner, scoped against
  `download_attachment`'s filesystem side effect and the append/expunge non-idempotency.
- **Signal handling and graceful shutdown.** See §Rejected.
- **Reducing the number of connections** — the daemon, cut 4. Still worth doing, no longer
  load-bearing for this outage now that quota is excluded.
- **A connection that dies within the 60 s window** still costs one socket timeout to discover.
- Everything in cuts 1, 3, 4, 5.

## Tasks

- [ ] 1. Fake-server fixture with received-command log in `conftest.py`; failing AC4 test.
- [ ] 2. Failing tests AC1–AC3 for discard, threshold and the 60 s boundary.
- [ ] 3. Failing tests AC5a, AC5b, AC6 for the lease, with barriers.
- [ ] 4. Failing tests AC7–AC9 for the transport predicate, discard-on-wrapped-cause, and classification.
- [ ] 5. Failing test AC10 for the `last_activity` stamp.
- [ ] 6. `_discard_connection` via `shutdown()`; `logout()` only for healthy closes.
- [ ] 7. `CONNECTION_MAX_IDLE = 60`; skip-probe branch routed through discard.
- [ ] 8. `_lease()` holding the lock for the whole operation; `connection_ctx` as its wrapper;
      `get_folders` and `get_messages` moved onto it, preview fetch included.
- [ ] 9. `is_transport_failure` walking the cause chain, stage-aware, with the errno allowlist and
      abort-only rule; `raise ConnectionFailure(stage, elapsed) from original` in the lease; stop the
      read paths and the preview path from swallowing transport failures; audit every handler
      inside a lease, `modify_flags` included.
- [ ] 9b. Split `_create_connection` into config and connect stages; `client.shutdown()` on a
      failure after construction, suppressing a raising shutdown.
- [ ] 9c. Move `download_attachment`'s file write outside the lease — fetch inside, write outside.
- [ ] 10. Stamp `last_activity` after establishment and after each completed operation.
- [ ] 11. Classifier invoked from both `except IMAPError` and `except Exception`, precedence stated.
- [ ] 12. `CHANGELOG.md`; update and name the changed `test_session.py` assertions.
- [ ] 13. Verify: full suite green.

## Files Changed

| file | change |
|---|---|
| `imap-slim-mcp/session.py` | `:15` constant; `get_connection:128-149`; `_close_connection:151-158` → discard + healthy close; `connection_ctx:160-172` → `_lease()`; `get_folders:174-189` and `get_messages:190-313` onto the lease; preview `except Exception` at `:264, 273, 295`; `last_activity` stamping at `:130, 148, 169` |
| `imap-slim-mcp/imap_client.py` | `is_transport_failure`; `ConnectionFailure`; read-path, preview and `modify_flags:1500-1520` handlers stop swallowing transport failures; `download_attachment:714-780` writes its file outside the lease |
| `imap-slim-mcp/imap_stream_mcp.py` | classifier called from `except IMAPError:934` and `except Exception:966` |
| `tests/imap-slim-mcp/conftest.py` | fake silent-IMAP-server fixture with command log |
| `tests/imap-slim-mcp/test_session.py`, `test_error_classify.py`, `test_imap_client.py` | AC1–AC12 |
| `imap-slim-mcp/CHANGELOG.md` | Unreleased entry |

## Reflection

<!-- Written post-implementation by IMP -->
