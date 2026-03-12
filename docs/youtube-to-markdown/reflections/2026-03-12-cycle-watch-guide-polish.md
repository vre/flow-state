# Cycle Reflection: Watch Guide into Polish Pipeline (v2.13.0)

## Plan-to-Implementation Translation

Plan was largely accurate for feature work: heatmap extraction, chunk analysis with `para_range`, synthesis prompt with watch guide, assembler simplification. Significant prompt engineering work during implementation: variants A–H tested on diverse video types (talking heads, demos, tutorials) to get synthesis quality right. Prompt quality had a larger impact on watch guide usefulness than gate logic in the assembler.

Key design change: verdict line parsing and cross-link logic removed from assembler entirely (option A from review). Simpler contract — assembler saves any non-empty watch guide content without parsing.

What changed from plan:
- Verdict line (WATCH/SKIM/READ-ONLY) dropped from assembler — synthesis prompt produces structured markdown directly
- Cross-link generation removed — added complexity without demonstrated value
- `_watch_guide_requested.flag` marker file added to signal watch guide intent between pipeline steps
- `ChunkRecord` TypedDict with `para_start`/`para_end` added to split script (not in original plan)
- Heatmap extraction from yt-dlp added as concrete replay-intensity signal for the synthesis prompt

Final commit `aef4d70`: 15 files changed, 754 insertions, 169 deletions. `watch_guide.md` subskill deleted.

## Review Iterations and Root Causes

ORC review found prompt/assembler contract mismatch: synthesis prompt no longer produces verdict lines but assembler still parsed them. Root cause: plan evolved during prompt iteration (A–H variants) but assembler spec wasn't updated to match.

Split script test failures (4): tests expected `list[Path]` but implementation returned `list[ChunkRecord]`. Root cause: test fixtures not updated when split script output format changed.

Acceptance testing: synthetic test (4 scenarios) instead of full pipeline run. All passed.

## Delegation Effectiveness

Codex for implementation: effective for code changes. Git commits blocked by sandbox — `.git-codex-sandbox-workaround` pattern means Codex commits to its own copy, not the real worktree. Manual commits needed after each Codex run. Same issue as v2.12.0 and v0.7.1 — now a known pattern.

Codex for documentation (Merge Phase): changelog, version bumps, plan reflection all delegated successfully in single session.

## Merge

Merge was the most problematic phase. Three distinct issues compounded:

1. **RTK masking git output.** `rtk-rewrite.sh` was silently rewriting `git log/status/diff` through rtk, which truncated/filtered output. `git log --oneline` showed 10 commits when there were 115+. This made it impossible to understand repo state. Fix: removed git commands from rtk hook entirely.

2. **Two-root git problem.** Local main (root `ecad5f0`) and remote main (root `29575b5`) had identical content but different SHA graphs from a historical force push/repo recreation. `git pull --rebase` produced massive conflicts because every commit appeared as new. Same class of issue as v2.12.0 — diverged roots make rebase impossible.

3. **`git clean -fd` deleted untracked research files.** 10 research files from `docs/*/research/` were untracked and permanently deleted during cleanup. Recovered from Backblaze backup by user.

Resolution: abandoned rebase. Reset local main to correct pre-session state (`030e36f`), applied worktree changes via `git checkout <sha> -- .`, force-pushed to remote.

## Process Improvements

- **RTK must not touch git commands.** Token savings on git output caused cascading confusion about repo state. The cost of a few extra tokens is negligible compared to the cost of misunderstanding git history. Now permanently removed.
- **Verify repo root consistency before merge.** If `git merge-base --is-ancestor` fails between local and remote, stop — rebase will not work. Check this before attempting.
- **`git clean` needs explicit file review.** Never run `git clean -fd` without checking what untracked files exist. Research documents and notes may not be committed.
- **Codex sandbox git workaround is fragile.** Three cycles now with the same `.git` rename pattern. Works but requires manual commit step after every Codex run. Consider documenting the exact handoff protocol or finding a better solution.
