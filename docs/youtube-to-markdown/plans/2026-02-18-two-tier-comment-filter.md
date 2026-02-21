# DONE: Two-Tier Comment Filter

## Problem

Comment insights subagent (Sonnet) receives 200 prefiltered comments as a single file (~48K tokens). The Read tool limit is 25K tokens, forcing 5 paginated reads. Result: 105 s, 84K context tokens, 9 tool calls.

Analysis of the Adam Savage video (hiNScN5ZR3c, 200 comments) showed:
- 20% (40) directly cited in insights
- 30% (60) corroborating
- 35% (70) noise (generic praise, off-topic)
- 15% (30) tangential

50% of comments produced zero value. The same insights would emerge from ~100 comments.

## Solution

Split `32_filter_comments.py` output into two tiers. Tier 1 goes directly to Sonnet. Tier 2 gets screened by inline Haiku to drop noise before joining tier 1.

```
32_filter_comments.py (existing junk removal)
  1060 → 200 comments
        │
  split_tiers() ← NEW
        │
        ├─ TIER 1: likes ≥ p75 OR length ≥ 400 chars
        │   → _comments_prefiltered.md (full format)
        │
        └─ TIER 2: rest
            → _comments_candidates.md (compact format)
                │
         Haiku inline prompt (in comment_extract.md Step 3)
                │
                └─ substantive comments appended to _comments_prefiltered.md
```

Expected result (based on hiNScN5ZR3c):
- Tier 1: ~76 comments (~10K tokens)
- Tier 2: 124 → Haiku keeps ~40 → ~5K tokens
- Sonnet receives: ~116 comments, ~17K tokens, single Read call
- Time: 105 s → ~36 s (Haiku 5.6 s + Sonnet ~30 s)

## Acceptance Criteria

- [x] AC1: `split_tiers()` uses p75 likes threshold calculated from parsed comments, not hardcoded absolute value
- [x] AC2: Tier 1 file ≤ 25K tokens (~100K chars). Print warning if exceeded.
- [x] AC3: Tier 2 compact format: `[N|@author|X likes] Full text` — one line per comment, no blank lines (amended: added @author, removed truncation since tier-2 texts are <400 chars)
- [x] AC4: Tier 2 file ≤ 25K tokens. Print warning if exceeded.
- [x] AC5: Haiku inline prompt in comment_extract.md produces KEEP list of comment numbers
- [x] AC6: Kept tier 2 comments appended to `_comments_prefiltered.md` in full format
- [x] AC7: `_comments_candidates.md` added to `get_comments_work_files()` for cleanup
- [x] AC8: Videos with ≤ 80 comments after junk filter skip tier split entirely (all go to prefiltered)
- [x] AC9: Existing tests pass (28), new tests cover split_tiers, format_compact, merge (28 new = 56 total)
- [+] AC10: Safety wrapper deferred to merge step when two-tier (discovered during review)

## Implementation

### Task 1: `lib/comment_filter.py` — add tier split functions [x]

```python
def calculate_likes_p75(comments: list[dict]) -> int:
    """Calculate p75 of likes distribution."""

def split_tiers(
    comments: list[dict],
    likes_threshold: int | None = None,
    length_threshold: int = 400,
) -> tuple[list[dict], list[dict]]:
    """Split into tier 1 (auto-keep) and tier 2 (needs screening).

    Args:
        comments: Filtered comments sorted by likes.
        likes_threshold: Minimum likes for tier 1. None = use p75.
        length_threshold: Minimum text length (chars) for tier 1.

    Returns:
        (tier1, tier2) comment lists.
    """

def format_compact(comments: list[dict], max_text: int = 300) -> str:
    """Format comments in compact one-line format for Haiku screening.

    Format: [original_index|X likes|Y chars] First max_text chars...
    """
```

Preserve original comment index in dict (`"index": N`) during `filter_comments` so tier 2 → prefiltered reassembly uses correct numbering.

### Task 2: `scripts/32_filter_comments.py` — write two output files [x]

Current: writes single `_comments_prefiltered.md`.

New behavior:
1. Parse and filter as before (junk removal, top 200)
2. If `len(filtered) <= 80`: write all to `_comments_prefiltered.md`, no candidates file. Print `"Filtered: X → Y comments (single tier)"`.
3. If `len(filtered) > 80`: call `split_tiers()`, write tier 1 to `_comments_prefiltered.md`, tier 2 to `_comments_candidates.md` in compact format. Print token estimate for each. Print warning if either > 100K chars.

Output:
```
Filtered: 1062 → 200 comments
Split: 76 tier-1 (~10K tok) + 124 tier-2 (~5K tok)
```

### Task 3: `subskills/comment_extract.md` — add Haiku screening step [x]

Add Step 3 after existing Step 2:

```markdown
## Step 3: Screen tier-2 comments (if candidates file exists)

If `<output_directory>/${BASE_NAME}_comments_candidates.md` exists:

task_tool:
- subagent_type: "general-purpose"
- model: "haiku"
- prompt:
  INPUT: <output_directory>/${BASE_NAME}_comments_candidates.md
  OUTPUT_APPEND: <output_directory>/${BASE_NAME}_comments_prefiltered.md

  Read INPUT. Each line is a comment: [N|X likes|Y chars] text...

  Output ONLY a comma-separated list of comment numbers (N) that contain
  substantive content: personal experience, product names/models, technical
  details, specific recommendations, failure reports, or meaningful stories.

  Drop: generic praise, off-topic, pure jokes, vague opinions without specifics.

  Format: KEEP: 17, 45, 51, ...

Parse KEEP numbers. For each kept number, find the matching comment from
the parsed data (by original index) and append to _comments_prefiltered.md
in full format.
```

Wait — the orchestrator needs the parsed comments in memory to do the append. Alternative: the append is done by a new script.

### Task 4: `scripts/33_merge_tier2.py` — merge Haiku-kept comments [x]

```
Usage: 33_merge_tier2.py <candidates.md> <prefiltered.md> <keep_numbers>
```

- Reads candidates file, extracts comments by original index from keep list
- Formats in full markdown format (### N. @Author...)
- Appends to prefiltered file
- Renumbers all comments sequentially in the final file
- Prints: `"Merged: +40 from tier-2 (116 total)"`

This keeps the orchestrator out of the data path — it only passes the KEEP string from Haiku to the script.

### Task 5: `lib/intermediate_files.py` — add candidates file [x]

Add `f"{base_name}_comments_candidates.md"` to `get_comments_work_files()`.

### Task 6: Tests [x]

In `tests/youtube-to-markdown/test_comment_filter.py`:

```
TestCalculateLikesP75:
  - test_p75_basic_distribution
  - test_p75_all_same_likes
  - test_p75_single_comment
  - test_p75_empty_list

TestSplitTiers:
  - test_split_by_likes_threshold
  - test_split_by_length_threshold
  - test_split_combined_or_logic
  - test_split_auto_p75_when_none
  - test_split_preserves_original_index

TestFormatCompact:
  - test_compact_format_structure
  - test_compact_truncates_long_text
  - test_compact_no_blank_lines

TestSkipTierSplit:
  - test_80_or_fewer_all_go_to_prefiltered
```

In `tests/youtube-to-markdown/test_merge_tier2.py`:

```
TestMergeTier2:
  - test_merge_appends_kept_comments
  - test_merge_renumbers_sequentially
  - test_merge_empty_keep_list
  - test_merge_preserves_existing_prefiltered
```

## Risks

1. **Threshold overfitting**: p75/400 validated on one video. Different video types (tutorials with few comments, viral with 10K) may behave differently. The p75 relative threshold adapts, but 400 chars is absolute. Monitor first 5 runs.
2. **Haiku false negatives**: Inline Haiku dropped 68% of tier 2 (kept 32%). Some valuable short comments may be lost. Acceptable because tier 1 already captured all high-engagement content.
3. **Renumbering confusion**: After merge, comment numbers in `_comments_prefiltered.md` won't match original YouTube order. This is fine — the insights agent doesn't reference by number.

## Not in scope

- Changing the initial 200 comment cap
- Modifying Sonnet insights prompt
- Token counting (char/4 estimate sufficient)

## Reflection

### What went well
- Plan was precise enough to implement all 6 tasks without ambiguity
- Compact format design (`[N|@author|X likes] text`) worked cleanly — simple to parse, token-efficient
- p75 adaptive threshold avoids hardcoded values, adapts to different video profiles
- Delegating merge to a script (`33_merge_tier2.py`) kept orchestrator out of data path

### What changed from plan
- AC3 compact format: added `@author`, removed truncation (tier-2 texts already <400 chars)
- AC10 discovered: safety wrapper deferred to merge step when two-tier
- Task 4 renumbering: plan specified global sequential renumber, but code review revealed body text corruption. Changed to append-with-correct-number (no global renumber)
- KEEP parser: made tolerant of case variations, trailing periods, multiline output, non-numeric tokens
- Added deduplication of KEEP indices and stale candidates cleanup (not in plan)

### Lessons learned
- Global regex renumbering on user-generated content is inherently unsafe. Direct numbering (count existing + enumerate) is safer.
- LLM output parsing needs defensive tolerance from the start. The KEEP parser went through 3 iterations.
- Codex CLI as external code reviewer caught real bugs that unit tests missed. Two review rounds were needed — first round fixes introduced new issues.
