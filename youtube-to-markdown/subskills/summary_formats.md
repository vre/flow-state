# Content Classification & Format Routing

## 1. Classify content type

- TIPS: gear reviews, rankings, "X ways to...", practical advice lists, single-speaker opinions/complaints
- INTERVIEW: dialogue between 2+ participants, podcasts, conversations, Q&A, panel discussions
- EDUCATIONAL: single concept explained in depth, "how X works", mechanism breakdowns, cause-effect analysis
- TUTORIAL: step-by-step instructions, coding, recipes

Classification rules:
- INTERVIEW requires actual dialogue between 2+ participants. Single speaker → never INTERVIEW.
- Single speaker **listing** opinions or complaints → TIPS.
- Single speaker **explaining** mechanisms or cause-effect → EDUCATIONAL.
- The test: does the content **list** items (TIPS) or **explain why** something works (EDUCATIONAL)?

Ambiguity: classify by dominant structure. Default fallback: TIPS.

**Format escape hatch**: If the content doesn't fit any type well (narrative, comedy, motivational speech, poetry, etc.), use claim-bullets. Don't force a structured format on content that resists it.

## 2. Select format file

| Content type | Format file |
|---|---|
| TIPS | claim-bullets.md |
| INTERVIEW (long, multi-theme) | themed-claims.md |
| INTERVIEW (other) | claim-bullets.md |
| EDUCATIONAL | claim-bullets.md |
| TUTORIAL | step-list.md |

INTERVIEW routing: use themed-claims only for long (>30 min) multi-theme interviews or panels where topics shift clearly. Otherwise claim-bullets.

**Hybrid content**: If the video mixes discussion/analysis with step-by-step instruction (e.g. interview + cooking, architecture talk + coding), use claim-bullets as the primary format and embed step-list sections under `### [Part title]` headings where the video switches to tutorial mode.

Read the format file. Apply its template and rules to produce the summary.

## 3. Length budget (TRANSCRIPT_BYTES provided in prompt)

| Transcript size | Max summary ratio | Format constraint |
|---|---|---|
| < 8000 bytes | 30% | Override: read flat-bullets.md (max 5-8 bullets). Exception: TUTORIAL always uses step-list regardless of size. |
| 8000-15000 bytes | 15% | Use format but max 2-3 sections/units. |
| > 15000 bytes | 10% | Normal format rules. |

This is a hard ceiling, not a suggestion. If output exceeds the ratio, cut sections or compress bullets until it fits.
