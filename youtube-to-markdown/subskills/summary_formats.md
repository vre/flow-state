# Content Classification & Format Routing

## 1. Classify content type

- TIPS: gear reviews, rankings, "X ways to...", practical advice lists
- INTERVIEW: multiple claims or perspectives, opinion-driven analysis, podcasts, conversations, Q&A
- EDUCATIONAL: single concept explained in depth, "how X works", mechanism breakdowns
- TUTORIAL: step-by-step instructions, coding, recipes

Ambiguity: classify by dominant structure. Default fallback: INTERVIEW.

## 2. Select format file

| Content type | Format file |
|---|---|
| TIPS | flat-bullets.md |
| INTERVIEW | concept-card.md |
| EDUCATIONAL | what-why-how.md |
| TUTORIAL | step-list.md |

Read the format file. Apply its template and rules to produce the summary.

## 3. Cross-cutting rules

Apply to ALL formats, in addition to format-specific rules:

- Start headers from ## level (no H1)
- First element: `## [Main heading for the entire video]` — one sentence, informative
- Second element: `**TL;DR**: [1 sentence synthesis]` — mandatory, never remove
- Last section (optional): `## Hidden Gems` — valuable tangents/side narratives outside main structure
- No language switching: output in the language the video is spoken in
- Preserve structural elements specific to each format (Prerequisites, Result, What/Why/How)
