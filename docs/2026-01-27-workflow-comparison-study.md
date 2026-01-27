# Workflow Comparison Study: Superpowers vs CLAUDE.md

**Date:** 2026-01-27
**Projects:** `imap-stream-mcp` (caching), `youtube-to-markdown` (update-mode-redesign)

## Executive Summary

A comparison of two different approaches to Claude Code development:
1. **Superpowers skills** (brainstorm → write-plan → execute-plan)
2. **CLAUDE.md Mission Command** (intent + constraints + context → delegation)

**Key finding:** Both produced working code, but differed significantly in user experience, test coverage, and architectural quality.

---

## 1. Study Background

### Projects Studied

| Project | Workflow | Date | Outcome |
|---------|----------|------|---------|
| imap-stream-mcp caching | Superpowers (brainstorm, write-plan, execute-plan) | 2026-01-27 | v0.4.0, session caching |
| youtube-to-markdown update-mode | CLAUDE.md Mission Command | 2026-01-26 | prepare_update.py, update_flow.md |

### Methodology

- Claude-historian-mcp session analysis (limited: some tools blocked for subagents)
- Plan document content analysis
- Git history examination
- Test coverage measurement

---

## 2. Planning Phase Comparison

### Document Structure

| Metric | Superpowers | Mission Command |
|--------|-------------|-----------------|
| Design doc | 245 lines | - |
| Implementation plan | 1216 lines | 418 lines (combined) |
| Total | 1461 lines | 418 lines |
| Tasks | 16 TDD tasks | 7 phases |

### Superpowers: Granular TDD Plan

```
Task 4: Folder Caching
├── Step 1: Write failing test [code provided]
├── Step 2: Run test to verify it fails [command provided]
├── Step 3: Write minimal implementation [code provided]
├── Step 4: Run test to verify it passes [command provided]
└── Step 5: Commit [command provided]
```

**Strength:** Mechanically executable, TDD enforced
**Weakness:** Over-specified - no room for implementer decisions

### Mission Command: Intent + Constraints

```
Intent: When user runs skill on already-extracted video, show current state
Constraints:
- prepare_update.py is read-only (no file writes)
- Don't modify module logic other than update_mode.md
- Reuse extract_data.py for API access
Implementation Order: [7 phases without detailed commands]
```

**Strength:** Trusts implementer competence, flexible
**Weakness:** Requires competent implementer

---

## 3. Implementation Phase Comparison

### User Experience

| Aspect | Superpowers | Mission Command |
|--------|-------------|-----------------|
| Trackability | "Couldn't be bothered, skipped tasks 4-14" | Skeptic review found 4 bugs |
| Subagents | Yes (execute-plan) | No |
| Worktree | `.worktrees/imap-caching` | Not mentioned |

**Critical observation:** The 16-task TDD plan was too heavy for manual user tracking. In practice, it served as a "recipe for subagents", not a step-by-step guide for humans.

### Commit Strategy

Both followed CLAUDE.md guidelines:
- Intermediate implementations committed
- Final squash to main branch
- One clear commit message

---

## 4. Test Coverage Comparison

### Quantitative Metrics

| Metric | Superpowers (caching) | Mission Command (update-mode) |
|--------|----------------------|------------------------------|
| Test lines | 308 | 335 |
| Test functions | 21 | 35 |
| Test classes | 7 | 7 |
| Lines/test | 14.7 | 9.6 |

### Analysis

**Surprising result:** Mission Command produced **67% more tests** (35 vs 21) and **more concise tests**.

**Explanation:**

1. **TDD plan pre-specified tests** → Superpowers followed literally, didn't add its own
2. **Mission Command gave freedom** → Implementer found edge cases (parse_count B-suffix, regex edge cases)
3. **Skeptic review** → Bug discovery led to additional tests

**Conclusion:** Over-specified plans can *limit* test coverage. Competent implementer + freedom = better coverage.

---

## 5. Architectural Quality

### Review Report Findings (2026-01-27)

| Project | Issue | Severity |
|---------|-------|----------|
| imap-stream-mcp | Circular dependency (imap_client ↔ session) | Critical |
| youtube-to-markdown | "Junk drawer" shared_types.py | Medium |
| youtube-to-markdown | DRY violation (extract_video_id duplicate) | Low |

### Superpowers and Circular Dependency

TDD plan Task 2 (Connection Management) identified the issue:

> "Circular import avoidance: `session.py` needs `get_credentials()` from `imap_client.py`. Solved with lazy import inside function."

**Analysis:** The plan solved the problem with "fragile local imports" rather than refactoring the architecture. TDD focus (tests passing) didn't prevent architectural issues.

### Mission Command and Refactoring

The update-mode plan's skeptic review found:
- Intermediate file duplication → `intermediate_files.py` created
- SKILL.md context bloat → Logic moved to `update_flow.md`

**Analysis:** Freedom to make architectural decisions led to better modularity.

---

## 6. Post-Commit Code Review Findings

### co-review.md (2026-01-27)

A separate code review found **three serious bugs** in the imap-stream-mcp caching implementation - all in code that passed TDD tests:

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| 1 | **Race Condition** in flag modification | High | imap_client.py:825-832 |
| 2 | **TOCTOU Bug** in cache validation | Medium | session.py:187-195 |
| 3 | **Incomplete Connection Cleanup** | Medium | session.py:125-132 |

### Why Didn't TDD Prevent These?

1. **Race condition:** TDD tests didn't test concurrency - mocked tests run single-threaded
2. **TOCTOU:** TDD plan specified `folder_status()` + `select_folder()` separately (Task 5) - the plan itself contained the bug
3. **Connection cleanup:** TDD test mocked `_create_connection()` to succeed, didn't test failure path

### Comparison Between Workflows

| Metric | Superpowers TDD | Mission Command |
|--------|-----------------|-----------------|
| Bugs found *before* commit | 0 | 4 (skeptic review) |
| Bugs found *after* commit | 3 | 0 |
| Highest severity bug | High (race condition) | - |

### Conclusion

**TDD tests passed but the code was buggy.**

A mechanical TDD process only tests what the plan specifies. If the plan contains an architectural error (like the TOCTOU `folder_status()` → `select_folder()` sequence), TDD faithfully reproduces the error.

Mission Command + skeptic review forces critical thinking *before* commit, not just mechanical test execution.

---

## 7. Conclusions

### When to Use Superpowers Skills?

✓ Repetitive, similar projects (MCP development, plugin development)
✓ When delegation to subagents is needed
✓ When TDD discipline must be enforced
✗ Not suitable for manual user tracking (too granular)

### When to Use Mission Command?

✓ One-off or unique projects
✓ When staying "hands-on" and observing each phase
✓ When skeptic review is more valuable than automated process
✓ When implementer agent is competent (no over-specification needed)

### Hybrid Model (Recommendation)

| Element | Source |
|---------|--------|
| Plan structure | CLAUDE.md (Intent, Constraints, Acceptance Criteria) |
| Worktree isolation | Superpowers |
| Task list | 5-7 high-level tasks (not 16 micro-tasks) |
| TDD | Mentioned as constraint, don't pre-specify tests |
| Subagent delegation | Opt-in only for large blocks |

### The Philosophical Choice

> **Do you trust the implementer or the process?**

- **Superpowers:** Trusts the process (TDD cycle enforces quality)
- **Mission Command:** Trusts the implementer (competent agent makes good decisions)

This study shows that **trust in a competent implementer + skeptic review** produced better test coverage and fewer architectural issues than a mechanical TDD process.

---

## 8. Appendices

### Files Studied

- `docs/imap-stream-mcp/plans/2026-01-27-caching.md` (design doc)
- `docs/imap-stream-mcp/plans/2026-01-27-caching-implementation.md` (TDD plan)
- `docs/youtube-to-markdown/plans/2026-01-26-update-mode-redesign.md` (Mission Command plan)
- `review_report.md` (architectural review)
- `co-review.md` (post-commit code review)

### Test Coverage Details

**imap-stream-mcp (7 test classes, 21 tests):**
- TestDataStructures
- TestConnectionManagement
- TestConnectionContextManager
- TestFolderCaching
- TestMessageListCaching
- TestSessionManagement
- TestCacheUpdateOnFlags

**youtube-to-markdown (7 test classes, 35 tests):**
- TestParseCount
- TestCompareCounts
- TestCompareStrings
- TestDetectIssues
- TestGenerateRecommendation
- TestReplaceMetadataSection
- TestUpdateExtractionDate
