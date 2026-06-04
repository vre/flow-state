# Code Reflection: Browser-Control Hardening

**Plan**: `docs/plans/2026-06-03-browser-control-hardening.md`
**Date**: 2026-06-03

## What was done

Architecture review fixes across both browser-control tools (13 ACs, 4 implementation commits):

1. Firefox reconnect with error classification — transport errors trigger reconnect (5 attempts, asyncio.Lock), BiDiError returns error directly. Zombie session detection ("already started") shuts down cleanly.
2. Firefox liveness probes — session.status every ~30s when idle >10s, triggers reconnect on failure.
3. Firefox prefix-match context IDs — startswith match on top-level contexts, error on 0 or >1.
4. Chrome per-session retry — extracted `_dispatch_target_cmd`, evict stale session and re-attach once before escalating to full browser reconnect.
5. Both: console-tail handler cleanup via try/finally, connect timeout on all 8 `open_unix_connection` sites, sync comments on duplicated helper JS.
6. Bug fixes: Firefox cmd_list broken title, Chrome cmd_stop false-positive kills, Chrome `_daemon_request` string-based error detection.

## What changed from plan

- `serializationOptions` added to Firefox `cmd_eval` — not in any AC. Controls BiDi object serialization depth. Snuck into the reconnect commit.
- Plan step 8 (Chrome per-session retry) designed `_retry_target_cmd` with a callback pattern. Implemented as `_dispatch_target_with_retry` calling `_dispatch_target_cmd` directly — simpler, same behavior.
- AC12 sync comments initially missed `_WAIT_COMMANDS` (Firefox) and `_HELPER_COMMANDS` (Chrome). Caught in self-review, fixed by amending commit 4.

## Lessons learned

- Error classification (transport vs protocol) is the key design decision for reconnect. Getting this wrong means either reconnecting on bad user input (wasteful) or not reconnecting on network failures (broken).
- `send()` timeout removal requires auditing every path that calls the now-unbounded function. The `__aenter__` timeout on `session.new` was not obvious until the Codex review pointed it out.
- Self-review caught the incomplete AC12 that code-level implementation missed — reviewing diffs against acceptance criteria line-by-line works.
