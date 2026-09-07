# Code reflection — keychain safety

617 tests pass. Two defects fixed, one of which could destroy a user's mail credentials.

## The bug

`_migrate_legacy()` copied every key from the legacy `imap-stream` service into `imap-slim`
**unconditionally**, then deleted the source. It is called from `_keyring_get()`, so it runs on
every credential read. A stale legacy entry — left over from any earlier setup — therefore
overwrote live credentials with itself and deleted the only other copy. No confirmation, no
backup, triggered by reading.

Three guards now: refuse entirely if the current service already has accounts; never overwrite an
existing key; delete a source key only after verifying its copy landed intact. A half-migrated
keychain that still has its legacy copy is recoverable; one that deleted the source after a failed
write is not.

## The second defect is what made the first dangerous

The suite reached the real login keychain. A test failure earlier in this work showed it plainly —
`Account 'test' not found. Available: work` came from the user's actual configuration. So running
tests could trigger the migration, which meant **running tests was capable of destroying live
credentials**. An autouse fixture now installs an in-memory store for every test.

That combination is the lesson: neither defect is alarming alone. A read path that writes, plus a
test suite that can reach production data, is how a supposedly read-only action becomes
destructive. I checked what the commands would *read* before running them against a live account.
I did not check what the read path could *write*.

## And a claim I should not have made

I told HC the credential loss was "almost certainly caused by something I ran today". The evidence
established *when* the entries were created and *that* they were placeholders. It did not establish
*what* wrote them. HC's question — does `setup.py` default to `server.com`? — exposed the gap: it
has no default, so those values were typed by someone, and the user's own history shows an earlier
session already discussing legacy-versus-slim keys.

I found a mechanism that fits and reported it as the cause. That is precisely the failure I had
spent the session correcting in plans: a plausible restatement hardening into a fact because
nothing forced it back to the evidence. Being the one who names that pattern is not protection
against it.

## Tests rewritten, not patched

The two existing migration tests asserted the destructive behaviour, driving a `MagicMock` that
does not store what is written to it. The new verify-before-delete step cannot be expressed against
a mock with no memory, so the class was rewritten against the same in-memory store the isolation
fixture uses. The regression test was then checked against the old implementation: it fails, with
`work:imap_server was overwritten`.
