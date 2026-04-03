# youtube-to-markdown: run.py dispatcher

## Problem

Permission issues in youtube-to-markdown skill:

1. **Multiple permission prompts** — `printf`, `python3 -c`, `rm`, `python3 - <<'PY'` trigger security warnings ("consecutive quotes", "hidden arguments"). Each unique Bash pattern needs separate approval.
2. **Subagent inline code** — subagents improvise `python3 -c "..."` multiline scripts for analysis, triggering security warnings. They should use Read/Grep tools instead.

## Goal

Single `python3 ./scripts/run.py <cmd> [args]` entry point. One `Bash(python3:*)` permission covers all script invocations. No inline code from subagents.

## Scope

Phase 1 only. Tmp workdir (intermediate files in /tmp, move to dest) is deferred — it changes all scripts' I/O logic, separate project.

## Acceptance Criteria

- [x] AC1: All Bash calls in SKILL.md and subskills use `python3 ./scripts/run.py <cmd>` — verified by grep; no `printf`, `python3 -c`, heredoc Python, `rm`, or direct `XX_name.py` calls remain there
- [x] AC2: `run.py` dispatches to existing scripts (thin wrapper, no logic duplication)
- [x] AC3: `run.py flag <path>` and `run.py rm <path>` handle marker/temp files
- [x] AC4: Subagent task_tool prompts that only need Read/Write/Grep do not have Bash access. Inline Python/Bash was removed from the affected prompts.
- [x] AC5: Normal extraction flow now uses one Bash shape, `python3 ./scripts/run.py ...`; verified statically by command-path grep because the sandbox has no permission-prompt UI
- [x] AC6: Existing tests pass. `run.py` tests cover dispatch passthrough (stdout, stderr, exit code), unknown subcmd, missing args, path resolution relative to run.py, flag, rm, and guard

## Design

### run.py subcmd mapping

Thin wrapper: `run.py <cmd> [args]` → `subprocess.run(["python3", script_path, *args])`. Exit code and stdout/stderr pass through. Script path resolved relative to `run.py` location (`Path(__file__).parent`).

| Subcmd | Wraps | Notes |
|--------|-------|-------|
| `check` | `20_check_existing.py` | |
| `metadata` | `10_extract_metadata.py` | |
| `transcript` | `11_extract_transcript.py` | |
| `transcript-whisper` | `12_extract_transcript_whisper.py` | |
| `comments` | `13_extract_comments.py` | |
| `clean-vtt` | `30_clean_vtt.py` | |
| `format-transcript` | `31_format_transcript.py` | |
| `filter-comments` | `32_filter_comments.py` | |
| `merge-tier2` | `33_merge_tier2.py` | |
| `split-chunks` | `33_split_for_cleaning.py` | |
| `concat-cleaned` | `34_concat_cleaned.py` | |
| `insert-headings` | `35_insert_headings_from_json.py` | |
| `resolve-summary` | `36_resolve_summary.py` | |
| `assemble` | `50_assemble.py` | |
| `channel` | `22_list_channel.py` | |
| `backup` | `40_backup.py` | Passes inner verb (`backup`/`cleanup`) as first arg |
| `update-metadata` | `41_update_metadata.py` | |
| `prepare-update` | `21_prepare_update.py` | |
| `flag` | NEW — inline | `Path(arg).write_text("1\n")` |
| `rm` | NEW — inline | `Path(arg).unlink(missing_ok=True)` |
| `guard` | NEW — inline | File existence + size check, replaces `watch_guide.md` heredoc |

### guard subcmd

Replaces `python3 - <<'PY'` heredoc in `watch_guide.md`:
```
run.py guard <path> [--max-size 153600]
```
Prints `ok` if file exists and under max size, `skip: <reason>` otherwise. Exit 0 always.

### backup subcmd contract

`40_backup.py` expects inner verb: `backup <file>` or `cleanup <dir> <base_name>`. Dispatcher passes all args through:
```
run.py backup backup "<file>"
run.py backup cleanup "<dir>" "<base_name>"
```

### Subagent tool restriction

Subagent task_tool prompts fall into two categories:

1. **Analysis/write agents** (transcript_summarize, comment_summarize, transcript_polish chunks, synthesis): need Read + Write only. Add to prompt: `Do not use Bash. Use Read and Grep tools for file analysis, Write for output.`
2. **Comment screening agent** (comment_extract Step 3, haiku): read-only, no Bash needed. Already correct.

## Tasks

- [x] 1. Create `scripts/run.py` — argparse dispatcher, subcmd → script mapping, subprocess.run passthrough, `flag`/`rm`/`guard` subcmds
- [x] 2. Update SKILL.md — all script calls → `run.py <cmd>`, replace python3 -c
- [x] 3. Update subskills (transcript_extract, transcript_polish, comment_extract) — script call migration
- [x] 4. Update `watch_guide.md` — heredoc → `run.py guard`
- [x] 5. Update `update_flow.md` — printf → `run.py flag`, rm → `run.py rm`
- [x] 6. Update `channel_browse.md` — script call migration
- [x] 7. Update subagent task_tool prompts — add `Do not use Bash` where only Read/Write/Grep needed
- [x] 8. Tests for run.py (dispatch: stdout/stderr/exit passthrough, unknown subcmd error, missing args error, path resolution; flag: create + overwrite; rm: exists + missing; guard: exists + missing + oversize)
- [x] 9. Verify: option A, B, C, D extraction flows now route Bash calls through `run.py`; confirmed by grep plus the full `youtube-to-markdown` test suite. Interactive permission-prompt UI unavailable in sandbox.

## Reflection

<!-- Written post-implementation by IMP -->
<!-- ### What went well -->
<!-- ### What changed from plan -->
<!-- ### Lessons learned -->
