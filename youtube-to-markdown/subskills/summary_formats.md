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

**Format escape hatch**: If the content doesn't fit any type well (narrative, comedy, motivational speech, poetry, etc.), use flat-bullets. Don't force a structured format on content that resists it.

## 2. Select format file

| Content type | Format file |
|---|---|
| TIPS | flat-bullets.md |
| INTERVIEW | concept-card.md |
| EDUCATIONAL | what-why-how.md |
| TUTORIAL | step-list.md |

Read the format file. Apply its template and rules to produce the summary.

## 3. Length budget (TRANSCRIPT_BYTES provided in prompt)

| Transcript size | Max summary ratio | Format constraint |
|---|---|---|
| < 5000 bytes | 30% | Ignore format template. Output: ## heading + TL;DR + flat bullet list (max 5-7 bullets). No sections, no labels, no scaffolding. |
| 5000-15000 bytes | 15% | Use format but max 2-3 sections/units. |
| > 15000 bytes | 10% | Normal format rules. |

This is a hard ceiling, not a suggestion. If output exceeds the ratio, cut sections or compress bullets until it fits.

## 4. Cross-cutting rules

Apply to ALL formats, in addition to format-specific rules:

- Start headers from ## level (no H1)
- First element: `## [Main heading for the entire video]` — one sentence, informative
- Second element: `**TL;DR**: [1 sentence synthesis]` — mandatory, never remove
- Last section (optional): `## Hidden Gems` — valuable tangents/side narratives outside main structure
- No language switching: output in the language the video is spoken in
- Preserve structural elements specific to each format (Prerequisites, Result, What/Why/How)
