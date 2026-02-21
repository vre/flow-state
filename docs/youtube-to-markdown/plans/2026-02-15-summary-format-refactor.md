# DONE: Summary Format Refactor

## Context

INTERVIEW format (heading + 2-3 sentence prose paragraph) is not scannable. Research conducted 2026-02-15: tested 3 existing formats + 5 new formats across 3 interview videos (ClawdBot, Claude Cowork, Peliteoreetikko). 24 variations evaluated total.

Winner: **Concept Card** — long claim heading, core idea as sentence, evidence bullets, implication as sentence.

## Research

Research document: `docs/youtube-to-markdown/research/2026-02-15-summary-format-research.md`

Contains:
- Web research findings (10 formats from literature)
- Test results for all 8 tested format approaches across 3 videos
- Assessments and decisions per format

## Acceptance Criteria

- [x] Format research documented
- [x] Format files created in `subskills/formats/` with concrete rules (7 files: 4 active + 3 archive)
- [x] `summary_formats.md` replaced with routing file (cross-cutting rules + routing table)
- [x] `transcript_summarize.md` updated with orchestrator handoff contract
- [x] All existing summarization constraints preserved (ads, budget, language, tightening)
- [x] Testing: INTERVIEW/TIPS/EDUCATIONAL through pipeline, structural checks pass. TUTORIAL deferred (no test video, format unchanged from existing)
- [x] Routing table integrity: all types mapped, all mapped files exist

## Constraints to Preserve

These exist in current `transcript_summarize.md` and MUST be carried over unchanged:

**Step 1 (summarizer)**:
- Ad/sponsor/self-promotion skipping ("like and subscribe", merch, etc.)
- Ad break merging (merge thematically connected content spanning ad breaks)
- Structure analysis (topic shifts, argument structure, narrative breaks)
- Single continuous topic → omit content unit headers
- Byte budget: <10% of transcript bytes

**Step 2 (copy editor)**:
- Byte budget enforcement: <10% of transcript bytes
- Hidden Gems dedup: remove if duplicates main content
- Tightness: cut filler words, compress verbose explanations, prefer lists over prose
- Language preservation: do not translate

## Tasks

### ~~1. Write research document~~ DONE

File: `docs/youtube-to-markdown/research/2026-02-15-summary-format-research.md` — written and reviewed.

### 2. Create format files

Directory: `subskills/formats/` (relative to skill root `.claude/skills/youtube-to-markdown/`)

Active (used in routing table):
- `concept-card.md` — INTERVIEW format (new, approved)
- `flat-bullets.md` — TIPS format (extracted from current summary_formats.md)
- `what-why-how.md` — EDUCATIONAL format (extracted from current summary_formats.md)
- `step-list.md` — TUTORIAL format (extracted from current summary_formats.md)

Archive (tested, documented, not in active use):
- `claim-first.md` — lighter version of concept card, potential for later
- `dialogue-essence.md` — interesting when speaker dynamics matter
- `interview-prose.md` — original INTERVIEW, kept as reference

Rejected (documented in research report only, no file):
- QEC — clickbait heading style, point hidden behind question
- Layered — too long, forced structure, layer 1 too condensed

Each file contains:
- Name, description, status (active/archive)
- Template (section structure only — no cross-cutting elements like TL;DR or ## main heading)
- Example (one complete section)
- Format-specific rules

Example rules for `concept-card.md`:
- Heading: one complete claim sentence, normal punctuation (no em-dash overuse)
- Core idea: one sentence, no label, no bold
- Bullets: 3-5 per section, front-loaded (weight at the beginning)
- Implication: one sentence, no label, no bold
- Separator: `---` before each section
- Section count: depends on video content, typically 5-8

### 3. Replace summary_formats.md with routing file

Current file contains both classification and formats. New version has three sections:

**Section 1 — Classification rules**:
- TIPS: gear reviews, rankings, "X ways to...", practical advice lists
- INTERVIEW: podcasts, conversations, Q&A, multiple perspectives
- EDUCATIONAL: concept explanations, analysis, "how X works"
- TUTORIAL: step-by-step instructions, coding, recipes
- Ambiguity tie-break: if video mixes types, classify by dominant structure. Default fallback: INTERVIEW (most flexible format).

**Section 2 — Routing table**:

| Content type | Format file |
|---|---|
| TIPS | flat-bullets.md |
| INTERVIEW | concept-card.md |
| EDUCATIONAL | what-why-how.md |
| TUTORIAL | step-list.md |

**Section 3 — Cross-cutting rules** (apply to ALL formats):
- Start headers from ## level (no H1)
- `## [Main heading for the entire video]` — mandatory first element
- `**TL;DR**: [1 sentence synthesis]` — mandatory, right after main heading
- `## Hidden Gems` — add if valuable tangential findings outside main structure
- No language switching: output in the language the video is spoken in

### 4. Update transcript_summarize.md

**Orchestrator handoff contract**:

Step 1 receives:
- `ROUTING: ./summary_formats.md`
- `FORMATS_DIR: ./formats/`

Step 1 reports (final message format):
```
summarize: wrote ${BASE_NAME}_summary.md [TYPE]
```
where `[TYPE]` is one of: TIPS, INTERVIEW, EDUCATIONAL, TUTORIAL.

Orchestrator parses `[TYPE]` from Step 1 output and passes to Step 2 as `CONTENT_TYPE`.

Step 2 receives:
- `ROUTING: ./summary_formats.md`
- `FORMAT: ./formats/<file>.md` (resolved by orchestrator from CONTENT_TYPE + routing table)

Step 2 reports (final message format):
```
tighten: wrote ${BASE_NAME}_summary_tight.md
```

**Step 1 prompt changes** (additions to existing prompt, not replacement):
- After classification step: resolve format file path from routing table → read format file
- Apply cross-cutting rules from ROUTING + format-specific rules from format file
- All existing constraints preserved: ad skipping, structure analysis, byte budget (see Constraints to Preserve)

**Step 2 prompt changes** (additions to existing prompt, not replacement):
- Receive FORMAT path directly (no need to classify or route)
- Read FORMAT file → verify output complies with format during tightening
- All existing constraints preserved: byte budget, Hidden Gems dedup, tightness, language (see Constraints to Preserve)

### 5. Testing

Test fixtures (video IDs, stable across environments):
- INTERVIEW: `DW4a1Cm8nG4` (Claude Cowork, 42min, English)
- TIPS or EDUCATIONAL: use any previously processed video of that type from output directory
- TUTORIAL: use any previously processed TUTORIAL video, or skip if none available

**Pass criteria per test**:

Structural checks (objective, automatable):
- Output contains `## ` main heading (line 1)
- Output contains `**TL;DR**:` (line 3 or within first 5 lines)
- INTERVIEW output contains `---` separators between sections
- INTERVIEW output contains `### ` section headings (claim sentences, not short labels)
- Byte budget: output size < 10% of transcript size
- Output language matches video language

Quality checks (human review):
- INTERVIEW: section headings are informative claim sentences (not "Setup", "Workflow")
- INTERVIEW: each section has core idea sentence + evidence bullets + implication sentence
- TIPS/EDUCATIONAL/TUTORIAL: output structure matches respective format template
- No content from ads/sponsors/self-promotion

**Regression matrix**:

| Type | Source | Check | Result |
|---|---|---|---|
| INTERVIEW | DW4a1Cm8nG4 | Full Concept Card structure | PASS — 8 sections, claim headings, core+bullets+implication |
| TIPS | h-s0lo6xlr4 | flat-bullets format preserved | PASS — bold categories, comma-separated items |
| EDUCATIONAL | MW6FMgOzklw | what-why-how format preserved | PASS — 4 sections, What/Why/How/What Then labels |
| TUTORIAL | (none available) | step-list format preserved | [>] deferred — format file unchanged from existing |

### 6. Routing table integrity check

After Task 3, verify:
- Every content type in classification rules has an entry in the routing table
- Every file referenced in the routing table exists in `subskills/formats/`
- Every active format file in `formats/` is referenced by at least one routing entry

## Rollback

If Concept Card quality drops in production:
1. Change routing table entry: INTERVIEW → `formats/interview-prose.md` (archive file)
2. No other files need to change — routing is the single switch point
3. This is a one-line change in `summary_formats.md`

Previous INTERVIEW format is preserved as `formats/interview-prose.md` for exactly this purpose.

## Reflection

### What went well

- Research-first approach eliminated format selection risk before any implementation
- Architecture (routing + separate files) emerged naturally from the format proliferation and proved clean to implement
- Two rounds of external review caught real bugs: path double-nesting, header rule conflict, cross-type guidance leak, contract drift
- Rollback is trivial — one-line routing change

### What changed from plan

- Path convention: plan originally used `formats/concept-card.md` in routing table, implementation stripped to just `concept-card.md` to avoid `FORMATS_DIR/formats/` double-nesting
- "Omit content unit headers" rule needed qualification — original rule conflicted with formats requiring section headings
- what-why-how.md cross-type guidance ("consider INTERVIEW for long content") removed — format files shouldn't suggest switching formats after classification
- Status-line contract extended with `[optional metadata]` in both writing-skills.md and writing-model-specific-prompts.md
- Handoff routing table removed from transcript_summarize.md (DRY — routing table lives only in summary_formats.md)

### Lessons learned

- Prompt file changes need the same path-consistency rigor as code. Three files referencing the same path with slightly different conventions produced ambiguity that a model agent could misinterpret.
- Format files that give cross-type guidance undermine deterministic routing. Once classified, the format is fixed — guidance belongs in classification, not in format files.
- External review found bugs that self-review missed in both rounds. Different reviewers find different categories of issues.
