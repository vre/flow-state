# Planning reflection — cut 2, connection recovery

## Six revisions, and what each was killed by

| rev | design | killed by | the fact that killed it |
|---|---|---|---|
| r1 | skip the probe on long-idle connections | measurement | `logout()` on an *unprobed* dead socket costs a full timeout too — the saving was zero |
| r1 | retry inside `connection_ctx` | review | `contextlib.contextmanager` yields once; the caller's `with` body cannot be re-run |
| r2 | downgrade to instrumentation, cause unknown | HC | quota excluded; and "it should self-heal" assumed the next call arrives soon, which HC's 3-minute spacing refutes |
| r3 | lock `get_connection`, classify at the boundary | source | `IMAPError` is a plain `Exception`, so the discard path never fired for wrapped read failures |
| r4 | transport predicate by exception family | review | `OSError(ENOTCONN)` is a real transport death and is neither `ConnectionError` nor `TimeoutError` |
| r5 | fix the three known swallowing sites | review | `modify_flags` was a fourth; a list of sites is not a rule |
| r6 | errno allowlist inside the lease | review | a disk `TimeoutError` is indistinguishable from an IMAP one by type or errno |

## The one that matters

Twice I proposed a fix whose saving I had not measured. r1's "skip the probe" was *obviously*
right and worth nothing, because I measured `logout()` only on the path where it happens to be
free — after a timed-out `noop()` — and generalised from that one sample. The second measurement
took ninety seconds and deleted the design.

**Measure the path you are changing, not an adjacent one.** The first measurement was real and I
still drew a false conclusion from it, which is more dangerous than having no measurement at all:
it came with a number attached.

## Diagnosis quality

I told HC the stale-socket story matched the report "line for line", then had to withdraw it when
review pointed out it does not explain persistence, then restored it once HC excluded quota and
the call spacing resolved the contradiction. The final explanation — it self-heals every time, but
the heal costs more than the caller waits — was available from the start. I skipped it because the
first story fit the symptom, and a story that fits is not the same as a story that is checked
against the other constraints.

The reviewer was right to reject it and wrong about the conclusion. Both. Its objection was sound
and its inference — that the cause must therefore be quota — was not. Taking either the objection
or the inference wholesale would have been wrong.

## What worked

- **Verifying every finding before acting.** Across six passes the reviewer produced wrong
  arithmetic twice and one wrong inference, and I flagged one of its "regressions" as my own
  malformed test string. Every accepted finding was reproduced first: `IMAPError.__mro__`, the
  `except IMAPError`/`except Exception` ordering, `get_folders` running outside the lease, the
  swallowing `except Exception` line numbers.
- **Preferring structural fixes to detection.** The last finding could have been answered with a
  cleverer predicate. Moving file I/O out of the lease means there is nothing left to detect. Every
  time the choice appeared, the structural answer was shorter and had fewer acceptance criteria.
- **Letting scope shrink.** Retry, `atexit` and `SIGTERM` all left this cut. The plan is smaller
  than r1 and does more, because the removed parts were unimplementable, unnecessary, or harmful.

## Input to implementation

- Task 9's audit is the risky one: "no handler inside a lease may swallow a transport failure" is a
  rule, and rules need an enumeration to check against. Grep every `except Exception` reachable
  from a lease before declaring it done, rather than trusting the three sites named in the plan.
- The `430 passed` baseline predates cut 1 and this cut both. Re-measure; do not quote it.
