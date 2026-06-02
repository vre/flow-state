# Cut 4: Documentation + test updates

Framing: `docs/plans/2026-06-01-frame-browser-control-parity.md`

## Intent

READMEs and SKILL.mds must reflect the new commands and flags. Integration tests must cover new functionality.

## Goal

All documentation and SKILL files updated. Firefox integration test covers open, status, targets, console-tail.

## Tasks

- [x] 1. Firefox README: add open, status, targets, console-tail to Commands tables; add --json flag; remove direct-connection language; update Socket Protocol examples
- [x] 2. Chrome README: add --json flag documentation
- [x] 3. Firefox SKILL.md: add new commands, --json note
- [x] 4. Chrome SKILL.md: add --json note
- [x] 5. Firefox integration test: add open, status, targets, console-tail test sections
- [x] 6. Commit

## Files Changed

- `firefox-control/README.md`
- `chrome-control/README.md`
- `firefox-control/SKILL.md`
- `chrome-control/SKILL.md`
- `tests/firefox-control/test_integration.sh`
