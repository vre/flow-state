# Long Transcript Chunking for Polish Pipeline

## Problem

Polish pipeline fails on long transcripts (>~80 KB / ~20k tokens). Confirmed on peliteoreetikko (170 KB, 2h48min Finnish podcast):

- **Step 2 (Haiku, clean artifacts): Silent failure.** Copies input unchanged — no cleaning, no error. Haiku cannot meaningfully process 170 KB text.
- **Step 3 (Sonnet, add headings): Hard failure.** `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (32k default) exceeded when Sonnet tries to write full transcript + headings via Write tool.

**Scope:** Podcasts are a key use case — Lex Fridman (3-4h), Finnish podcasts (Sijoituskästi) routinely hit 2-4h. Steps that produce small output (Step 1: line numbers, summarization: <10% of input) work fine.

## Architecture Context

Key files (relative to `youtube-to-markdown/`):
- `SKILL.md` — main orchestrator, routes to subskills
- `subskills/transcript_polish.md` — polish pipeline (this plan's target)
- `subskills/transcript_summarize.md` — summary pipeline (not affected)
- `scripts/31_format_transcript.py` — paragraph formatting script

Polish pipeline steps (from `transcript_polish.md`):
- **Step 1:** Paragraph breaks — Sonnet subagent outputs line numbers only → `31_format_transcript.py` inserts breaks — **WORKS on long**
- **Step 2:** Clean artifacts — **Haiku** subagent reads full text, writes full cleaned text via Write tool — **FAILS SILENTLY on long** (copies input unchanged)
- **Step 3:** Add headings — **Sonnet** subagent reads full text, writes full text with headings via Write tool — **FAILS HARD on long** (MAX_OUTPUT_TOKENS exceeded)

## Current Pipeline Flow

```
transcript_extract → transcript_summarize (reads all, outputs <10% — works)
                   → transcript_polish:
                       Step 1: paragraph breaks (Sonnet, outputs line numbers only — ✓ works)
                       Step 2: clean artifacts (Haiku, reads + writes FULL text — ✗ silent failure >~80 KB)
                       Step 3: add headings (Sonnet, reads + writes FULL text — ✗ hard failure >32k output tokens)
```

## Constraints

- Summarization MUST NOT be chunked — cross-references and thematic coherence require full context
- Polish Step 1 (paragraph breaks) works — outputs only line numbers, not full text
- Polish Step 2 (clean artifacts) is a local operation per RQ1 evidence — Haiku "gives up" rather than producing wrong output, so chunking should be safe
- Polish Step 3 (headings) needs structural awareness but output could be small (heading text + insertion points)
- Chunk boundaries must not create artifacts (duplicate headings, lost context at joins)
- `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (env var, default 32k) is the hard ceiling for single Write tool calls

## Research Questions

### RQ1: What actually happens when Step 2 hits the output limit?

Test with peliteoreetikko transcript:
- First: `git log --oneline -- youtube-to-markdown/subskills/transcript_polish.md` to check if pipeline changed since 2026-01-24 extraction date. If yes, note which version was used originally
- Run current polish pipeline on the 173 KB transcript
- Document: does the subagent truncate? Error? Produce partial output?
- Check if Write tool is called with partial content or not called at all
- Record token usage and timing

#### RQ1 Findings (2026-03-03, corrected)

**Test:** Re-extracted peliteoreetikko (Vq1jvFiW7dM) from YouTube, ran full polish pipeline on raw transcript. Initial run (2026-03-02) was corrupted by session interruptions — re-run on 2026-03-03 for accurate data.

**Note:** Original extraction used lowercase video ID `vq1jvfiw7dm` — YouTube IDs are case-sensitive. Correct ID: `Vq1jvFiW7dM`.

**Pipeline version:** `bb80d23` (latest, 2 commits since original extraction).

**Input sizes through pipeline:**

| Step | Input | Output | Tokens (reported) | Tool uses | Duration |
|------|-------|--------|-------------------|-----------|----------|
| Extract (VTT→dedup) | VTT | 227 KB, 4563 lines | n/a (script) | n/a | ~5s |
| Step 1: paragraphs (Sonnet) | 227 KB | 82 paragraph break points | 144,131 | 43 | 426s |
| `31_format_transcript.py` | dedup.md + paragraphs.txt | 170 KB, 164 lines (82 paragraphs) | n/a (script) | n/a | <1s |
| Step 2: clean artifacts (Haiku) | 170 KB | **170 KB — NO CLEANING** | 55,676 | 12 | 415s |
| Step 3: add headings (Sonnet) | 170 KB | **FAIL — output token limit** | - | 10 | ~72 min |

**Key findings:**

1. **Step 2 (Haiku) fails silently.** Haiku produced output that is byte-for-byte identical to input (170,284 bytes, 164 lines). All artifacts preserved: `>>` (82), `niinku` (76), `elikkä` (21). Haiku cannot effectively process 170 KB of text — it reads the file but cannot generate meaningful cleaned output at this scale. Instead of failing with an error, it copies the input unchanged.

2. **Step 3 (Sonnet) fails with error.** `CLAUDE_CODE_MAX_OUTPUT_TOKENS` (32k default) exceeded. Sonnet attempted to write the full transcript + headings (~42k tokens Finnish) via the Write tool, which exceeded the 32k output token limit per API call. The file was not created.

3. **The original problem hypothesis was correct.** Long transcripts DO break the polish pipeline. The failure modes are:
   - Step 2: Silent failure (no cleaning, no error)
   - Step 3: Hard failure (API error, no output)

**Root causes:**
- **Step 2:** Haiku's context window and output capacity are insufficient for 170 KB of content. The model appears to "give up" on the cleaning task and falls back to reproducing the input.
- **Step 3:** The `CLAUDE_CODE_MAX_OUTPUT_TOKENS` environment variable (default 32k) limits a single API response. When Sonnet tries to write the full transcript with headings in one Write call, it exceeds this limit.

**Implications for solution design:**
- **Chunking IS needed** for both Step 2 and Step 3 on transcripts >~80 KB (~20k tokens)
- **Heading-as-metadata (RQ3)** would eliminate Step 3's failure entirely — small output regardless of transcript size
- **Step 2 chunking** would let Haiku process manageable pieces (e.g., 10-20 paragraphs per chunk)
- Alternatively: use Sonnet for Step 2 on long transcripts (more capable, but 3-4x cost)

### RQ2: Chunking for Step 2 (artifact cleaning)

**Status:** Revised — Sonnet single-pass works for Finnish, FAILS for English. Chunking needed. Priority: HIGH.

RQ1 showed Haiku fails silently on 170 KB. Continuation approach is not applicable — Haiku doesn't truncate, it just does nothing. **Pre-chunking is the only viable strategy.**

Experiments to run on peliteoreetikko (82 paragraphs, 170 KB):

**A. Determine working chunk size for Haiku:**
- Test: 5, 10, 20 paragraphs per chunk. Measure: did Haiku actually clean? How many artifacts removed?
- Find the largest chunk size where Haiku still produces quality output
- Record token usage and duration per chunk

**B. Test Sonnet as alternative to chunked Haiku:**
- Run Step 2 with Sonnet on the full 170 KB transcript
- If Sonnet also fails: test Sonnet with chunks
- Compare quality: Sonnet-full (if works) vs Haiku-chunked vs Sonnet-chunked

**C. Overlap vs no-overlap:**
- Clean 82 paragraphs in non-overlapping chunks
- Clean same paragraphs with 2-paragraph overlap
- Diff outputs at chunk boundaries — are there artifacts? Is overlap needed for cleaning?
- Artifact cleaning is likely paragraph-local (unlike heading insertion), so overlap may be unnecessary

**D. Concatenation:**
- Simple concat of cleaned chunks — verify no content loss, no duplication, timestamps preserved

#### RQ2 Findings (2026-03-03)

**A. Haiku chunking — UNRELIABLE for non-English:**

Tested 5p (5 KB), 10p (15 KB), 20p (33 KB) chunks on peliteoreetikko:

| Chunk | Artifact removal | Language |
|-------|-----------------|----------|
| 5p (5 KB) | ✗ Translated to English | **FAIL** |
| 10p (15 KB) | ✓ Cleaned Finnish correctly | OK |
| 20p (33 KB) | ✗ Translated to English | **FAIL** |

Haiku randomly translates non-English text instead of cleaning it. Artifact counts (all zero) were misleading — artifacts disappeared because the text was translated, not cleaned. **Haiku is disqualified for non-English artifact cleaning** even with chunking.

Note: English transcripts untested — Haiku may work for English. But inconsistency makes it unsuitable as a reliable pipeline component.

**B. Sonnet full-pass — WORKS:**

| Metric | Value |
|--------|-------|
| Input | 170 KB (82 paragraphs, Finnish) |
| Output | 63 KB (195 lines) |
| Reduction | 63% |
| `>>` removed | 521 → 0 |
| `niinku` removed | 532 → 0 |
| `elikkä` removed | 26 → 0 |
| Language preserved | ✓ Finnish |
| Coverage | 00:00:00 – 02:46:25 (full) |
| Tokens | 114,378 |
| Tool uses | 10 |
| Duration | 728s (12 min) |

Quality is significantly better than Haiku:
- Proper nouns corrected: "Goldman Sachs" (was "Goldman Sax"), "No Limit Hold'em" (was "No Limited Holden")
- Speaker quotes added for direct speech
- Sentence structure improved, repetitions consolidated
- Natural Finnish preserved throughout

Output size (63 KB ≈ 16k Finnish tokens) is well under MAX_OUTPUT_TOKENS (32k). Sonnet handled the full transcript without chunking.

**C & D. Overlap and concatenation — NOT NEEDED:**

Since Sonnet handles the full transcript in a single pass, chunking is unnecessary. No boundary artifacts, no merge logic, no overlap strategy needed.

**E. English validation — Sonnet full-pass FAILS (2026-03-04):**

Tested on Lex Fridman OpenClaw (YFjfBk8HI5o), 3h16min, 169 KB, 58 paragraphs:

| Metric | Value |
|--------|-------|
| Input | 169 KB (58 paragraphs, English) |
| Output | **FAIL — MAX_OUTPUT_TOKENS exceeded** |
| Attempts | 2 (both hit 32k limit) |

English text has fewer speech artifacts than Finnish (no niinku/elikkä/>>). The Finnish transcript reduced 63% (170→63 KB) because artifact removal was aggressive. English cleaning would only reduce ~20-30%, keeping output at ~120-130 KB ≈ ~28-30k English tokens — right at the 32k limit. The Write tool call exceeded MAX_OUTPUT_TOKENS.

**This overturns the Finnish-only conclusion. Chunking IS needed for Step 2 on English transcripts at this size.**

**Revised conclusions:**
1. **Step 2 should use Sonnet, not Haiku.** Haiku is unreliable for non-English. Sonnet produces correct output.
2. **Chunking IS needed for Step 2** on transcripts where cleaned output exceeds ~32k tokens (~130 KB English, or any transcript with low artifact density).
3. **Finnish was a misleading test case** — 63% reduction from heavy artifacts made single-pass work. English (and other "cleaner" transcripts) won't compress enough.
4. **Threshold depends on language and artifact density:**
   - Finnish (heavy artifacts): single-pass works up to ~170 KB (output ~63 KB)
   - English (light artifacts): single-pass fails at ~169 KB (output ~120+ KB exceeds 32k tokens)
   - Safe universal threshold for chunking: ~100 KB input (conservative)
5. **Cost increase:** Sonnet is ~10x more expensive per token than Haiku, but produces correct output.
6. **C & D (overlap/concatenation) now relevant:** Need to test Sonnet-chunked on English transcript.

### RQ3: Heading insertion as metadata vs full rewrite

**Status:** Open. Priority: **CRITICAL** — Step 3 hard-fails, this is the primary solution.

RQ1 confirmed Step 3 cannot write full transcript + headings (exceeds 32k output tokens). Two alternatives:

**A. Heading-as-metadata:** Subagent outputs only insertion instructions:
```json
[
  {"before_paragraph": 3, "heading": "### Vastaa meidän kyselylomakkeeseen..."},
  {"before_paragraph": 46, "heading": "### Munuaisvaihtokauppa"}
]
```
A script then inserts headings. Output stays <1 KB regardless of transcript size.

**B. Scripted heading insertion (chaptered videos):** When chapters.json has chapters, heading insertion can be fully scripted — match chapter timestamps to paragraph timestamps, insert chapter names as headings. No LLM needed.

Experiments:
- Test approach A on peliteoreetikko: does Sonnet reliably reference paragraph numbers?
- Test approach B: script-only heading insertion from chapters.json. Compare quality with LLM approach.
- For videos without chapters: is approach A sufficient, or does the LLM need to read content to place headings well?

#### RQ3 Findings (2026-03-03)

**Tested both approaches on peliteoreetikko (82 paragraphs, 35 chapters).**

**Approach B (scripted) — `32_insert_headings.py`:**
- Script: `youtube-to-markdown/scripts/32_insert_headings.py`
- Algorithm: for each chapter, find first paragraph with timestamp >= chapter start_time, insert `### {chapter_title}` before it
- Result: 35 headings placed. Placement matches Sonnet Step 3's full-rewrite output exactly.
- Duration: instant (<1s). Cost: 0 tokens.
- Bug found and fixed: initial algorithm used <= (last paragraph before chapter) instead of >= (first paragraph of chapter). The heading should mark the START of new content.

**Approach A (Sonnet metadata JSON):**
- Sonnet read transcript + chapters.json, output 35 insertion instructions as JSON
- Duration: 97s. Cost: 52,390 tokens.
- Had same <= bug (because the prompt specified that algorithm). With corrected prompt, would produce identical results to scripted approach.
- For chaptered videos: no advantage over scripted approach. Same output, higher cost.

**Comparison: scripted vs Sonnet Step 3 full-rewrite (from first session):**
- Heading text: identical (both use chapter titles from chapters.json)
- Heading placement: identical (both place before first paragraph >= chapter start_time)
- The only difference: Step 3 full-rewrite also reformatted paragraph text (line breaks, minor edits) — this is a side effect, not the heading insertion's job

**Conclusions:**
1. **Chaptered videos → scripted approach (B).** Instant, deterministic, zero cost, identical output to LLM approach. `32_insert_headings.py` replaces Step 3 entirely.
2. **Non-chaptered videos → metadata approach (A).** LLM needed to identify topic boundaries. Output is small JSON (<1 KB), script inserts headings. Eliminates MAX_OUTPUT_TOKENS failure.
3. **Step 3 full-rewrite is never needed.** Both alternatives produce equivalent heading placement. The full-rewrite approach only "adds value" by accidentally reformatting text — which is Step 2's job, not Step 3's.
4. **English validation (2026-03-04):** Scripted heading insertion on Lex Fridman OpenClaw (169 KB, 58 paragraphs, 21 chapters) → 21 headings placed correctly, instant, 0 tokens. Confirmed script works across languages.

**Post-research decision (2026-03-06):** Always use AI-generated headings (metadata approach A), even for chaptered videos. Testing on Lex Fridman (21 chapters) showed AI generates 26 more granular headings with better topic names. chapters.json provided as context when available. Cost: +30-50k tokens. Scripted approach kept as fallback in `32_insert_headings.py`.

### RQ4: Failure threshold

**Status:** Substantially answered by RQ1 + RQ2 English validation.

#### RQ4 Findings (2026-03-04)

**The failure threshold depends on output size, not input size.** The 32k MAX_OUTPUT_TOKENS limit is the hard ceiling.

| Transcript | Input | Artifact density | Est. output | Sonnet single-pass |
|-----------|-------|-----------------|-------------|-------------------|
| Peliteoreetikko (fi) | 170 KB | High (niinku, >>, elikkä) | 63 KB (~16k tokens) | ✓ WORKS |
| Lex Fridman OpenClaw (en) | 169 KB | Low (um, uh, like) | ~120+ KB (~28-30k tokens) | ✗ FAILS |

**Key insight:** Finnish podcasts have unusually dense artifacts → 63% reduction. English conversational podcasts have ~20-30% reduction. The threshold is not a fixed input size — it's the estimated output size relative to 32k tokens.

**Practical thresholds:**
- Finnish/heavy artifacts: safe up to ~200 KB input
- English/light artifacts: safe up to ~100 KB input
- Universal conservative threshold: ~80 KB input (chunk above this regardless)

**Haiku threshold:** Not tested separately. Haiku is disqualified anyway (silent failure, language unreliability). Not worth pursuing.

### RQ5: Chunked cleaning quality

**Status:** DONE. Sonnet-chunked cleaning works on English.

#### RQ5 Findings (2026-03-05)

**Test:** Lex Fridman OpenClaw (YFjfBk8HI5o), 169 KB, 58 paragraphs, English.

**Chunk strategy:** ~20 paragraphs per chunk. The 65 KB middle chunk (paras 21-40) was too large for the subagent to process in one pass — split further into 28 KB + 38 KB sub-chunks.

| Chunk | Paragraphs | Input | Output | Reduction | Fillers removed | Timestamps |
|-------|-----------|-------|--------|-----------|-----------------|------------|
| 1 | 1-20 | 42 KB | 34 KB | 20% | 62 → 4 (94%) | 20/20 |
| 2a | 21-30 | 28 KB | 24 KB | 14% | — | — |
| 2b | 31-40 | 38 KB | 31 KB | 18% | — | — |
| 3 | 41-58 | 60 KB | 46 KB | 23% | 104 → 5 (95%) | 18/18 |
| **Total** | **1-58** | **169 KB** | **135 KB** | **20%** | **231 → 3 (99%)** | **58/58** |

**Quality assessment:**
- Filler removal: 99% (231 → 3 across full transcript)
- Timestamps: 100% preserved (58/58)
- Chunk boundaries: clean — no content loss, no duplication, no artifacts at joins
- Proper nouns and technical terms preserved correctly
- Natural conversational voice maintained
- No overlap needed — paragraph-level cleaning is local, boundaries are clean

**Failure during test:**
- 65 KB chunk (paras 21-40) failed twice: first attempt got stuck (agent read content but couldn't write), second attempt hit API ConnectionRefused. Split into 28+38 KB sub-chunks, both succeeded on retry.
- **Practical maximum per chunk: ~40-45 KB** (not the theoretical limit, but the reliable empirical boundary)

**Conclusions:**
1. **Sonnet-chunked cleaning works.** Quality is equivalent to single-pass (Finnish reference): 99% filler removal, full timestamp preservation, clean boundaries.
2. **~20 paragraph chunks (~40-45 KB each) are the sweet spot.** Large enough for context, small enough for reliable output.
3. **No overlap needed.** Artifact cleaning is paragraph-local. Concatenation is simple append.
4. **Parallel chunking is effective.** All chunks can be processed concurrently, total wall-clock time ≈ single chunk time.
5. **Cost:** ~4 chunks × ~35k tokens ≈ 140k tokens for a 3h English podcast. Comparable to Finnish single-pass (114k tokens).

### RQ6: Cost analysis

**Status:** Partially documented from experiments. Remaining: formal comparison table.

Known data points:
- Sonnet full-pass (Finnish, 170 KB): 114k tokens, 728s — ✓ works
- Sonnet full-pass (English, 169 KB): hit token limit, ~87k input tokens consumed before failure — ✗ wasted
- Sonnet chunked (English, 169 KB → 4 chunks): ~140k tokens total, ~3-4 min wall-clock (parallel) — ✓ works
- Haiku chunked (Finnish): unreliable, disqualified
- Scripted headings: 0 tokens, <1s — replaces Step 3 entirely
- Sonnet metadata headings: 52k tokens, 97s — unnecessary for chaptered videos

**Step 2 cost model (Sonnet):**
- Short transcripts (<80 KB): single pass, ~50-60k tokens
- Long transcripts (>80 KB): chunked (~20p chunks), ~120-150k tokens total
- Parallel execution: wall-clock time ≈ single chunk (~3-4 min)

Formal cost comparison deferred to implementation plan — enough data to design the solution.

## Test Corpus

| # | Video | URL | Language | Duration | Size |
|---|-------|-----|----------|----------|------|
| 1 | Peliteoreetikko (Sijoituskästi) | https://www.youtube.com/watch?v=Vq1jvFiW7dM | fi | 2h48min | 173 KB |
| 2 | Startup (Sijoituskästi) | https://www.youtube.com/watch?v=Mx7inUutMdM | fi | TBD | TBD |
| 3 | Lex Fridman — OpenClaw | https://www.youtube.com/watch?v=YFjfBk8HI5o | en | 3h16min | 169 KB (58p) |
| 4 | Lex Fridman — State of AI | https://www.youtube.com/watch?v=EV7WhVT270Q | en | TBD | TBD |
| 5 | Impact Theory | https://www.youtube.com/watch?v=Ccjcr5eYQZM | en | TBD | TBD |

Note: Finnish ~4 chars/token, English ~4.5 chars/token — a 200 KB English transcript is ~44k tokens, 200 KB Finnish is ~50k tokens

## Acceptance Criteria

- [x] RQ1: Failure modes documented (silent failure Step 2, hard failure Step 3)
- [x] RQ2: Step 2 model Haiku→Sonnet. Finnish single-pass works. **English single-pass FAILS** — chunking needed.
- [x] RQ3: Heading insertion — scripted for chaptered, metadata for non-chaptered. Script: `32_insert_headings.py`. Validated on both fi and en.
- [x] RQ4: Threshold depends on output size, not input. ~80 KB input conservative threshold. Language/artifact density is key variable.
- [x] RQ5: Sonnet-chunked quality validated on English — 99% filler removal, 100% timestamps, clean boundaries, ~20p chunks.
- [/] RQ6: Cost data collected from experiments. Formal comparison deferred to implementation plan.
- [x] Test corpus: 2 videos extracted — peliteoreetikko (fi, 170 KB) and Lex Fridman OpenClaw (en, 169 KB)
- [x] Research complete → ready to write implementation plan
