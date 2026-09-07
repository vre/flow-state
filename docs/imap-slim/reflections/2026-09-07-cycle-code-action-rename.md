# Code reflection — naming the operations after what they are

590 tests pass. Breaking change: `draft` split into `create` and `replace`; `edit` removed.

## The name was licensing a wrong model

HC's observation: there is no edit here, only create, read and mark for deletion. Checking the
protocol level rather than the action names:

```
create_draft           APPEND                                    imap_client.py:1232
modify_draft           APPEND + STORE \Deleted + EXPUNGE         :1403-1404
                       and a fresh Message-ID every time         :1189
edit_draft             FETCH, substitute, then the same replace
flag ... +Deleted      STORE only - never expunged
```

So "edit" named an operation IMAP does not have. The cost is not aesthetic: the name promises
in-place mutation with a stable identity, and **neither holds**. I had just been bitten by exactly
that during the live test — my cleanup flagged message 1574 for deletion after an `edit` had already
replaced it with 1576. I diagnosed the stale id as an incidental annoyance and moved on. HC read
the same fact as evidence the concept was wrong.

That is the difference worth recording. I treated a surprising behaviour as a footnote; the right
response was to ask what the naming had to be false about for the surprise to happen.

## What changed

`create` and `replace` are now separate actions rather than one action branching on whether a
payload happens to carry an id. The destructive one is named, and the guards are explicit in both
directions: an `id` in a `create` is an error, a missing `id` in a `replace` is an error.

`edit` is gone rather than renamed. It was a replace with a substitution the caller can do itself,
already refused for HTML-bearing drafts, and its only justification was saving tokens on a large
body — thin ground for an action whose name misdescribed the protocol.

## Deletion policy, stated once

The expunge inside `replace` is the only deletion this client performs, and it is not exposed. HC
was explicit: `flag ... +Deleted` marks, and the mail client does the deleting. Worth writing down
because the asymmetry was invisible before — `replace` silently expunged while a user marking
messages deleted accumulated them with no way to finish, and `cleanup` sounds like it would help
but only removes local temp files.

## Migration cost, paid honestly

Two test classes deleted outright (`TestEditDraft`, `TestEditRefusalByMimeStructure`) because they
tested a concept that no longer exists. The schema literal was regenerated deliberately — that test
exists precisely so a change to the advertised surface is a conscious edit. The description budget
went from 2249 to 2279 characters, because two action names cost more than one; raised with the
reason in the constant.

A blanket regex rewriting `action="draft"` mis-assigned one case: a test patching `create_draft`
whose payload had no id became a `replace`. Third time this session a mechanical edit across tests
needed its exceptions enumerated first rather than discovered by the failure.
