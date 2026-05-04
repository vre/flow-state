# Format Comparison Study — 2026-04-21 to 2026-04-27

## Background

Summary format was optimized on a narrow set of videos the developer watches (long tech interviews, educational). Short videos, rants, narratives, and listicles produced summaries that were 34-94% of transcript length (target: <10%). Root causes: no byte budget enforcement, format scaffolding exceeding input size, single-speaker misclassification.

## Test Matrix (20 videos)

| # | Video | Type | Duration | Transcript | Winner |
|---|---|---|---|---|---|
| 1 | Recursion in 100 Seconds | Ultra-short edu | 2 min | 2,040B | flat-bullets |
| 2 | TypeScript in 100 Seconds | Ultra-short edu | 2 min | 3,031B | flat-bullets (short override) |
| 3 | Rant about programming | Monologue/rant | 7 min | 9,545B | claim-bullets |
| 4 | Storytelling TEDx | Edu narrative | 17 min | 13,711B | claim-bullets |
| 5 | Changing story TED | Narrative | 16 min | 16,103B | claim-bullets |
| 6 | Andreessen Lex Fridman | Long podcast | 3h | 268,187B | claim-bullets |
| 8 | Women in tech panel | Panel 5 speakers | 1h | 52,951B | themed-claims |
| 9 | Ramsay 3 recipes | Tutorial | 20 min | 10,548B | step-list |
| 11 | Viking Age documentary | Short documentary | 10 min | 13,019B | claim-bullets |
| 12 | Jobs Stanford speech | Commencement | 15 min | 12,068B | claim-bullets |
| 15 | MKBHD Humane AI Pin | Product review | 25 min | 24,758B | claim-bullets |
| 16 | Veritasium entropy | Science explainer | 23 min | 23,576B | claim-bullets |
| 17 | Vox 2024 in 4 min | Ultra-short montage | 4 min | 3,753B | flat-bullets (short override) |
| 18 | Games April 2026 | Ranking list | 10 min | 9,404B | claim-bullets |
| 19 | Gaming 2026 Crazy | 2-person discussion | 40 min | 61,864B | claim-bullets |
| 20 | Gaming Trends | Trend list | 15 min | 21,524B | claim-bullets |
| 21 | AI Weekly | News roundup | 10 min | 11,265B | claim-bullets |
| 23 | Tim Ferriss interview | Long interview | 1.5h | 107,964B | themed-claims |
| 24 | Ramsay 10 min recipes | Multi-recipe | 30 min | 12,670B | step-list |
| 27 | TED2025 Watch Party | Multi-talk | 1h | 63,322B | claim-bullets |

## Format Scorecard

| Format | Wins | Losses | Verdict |
|---|---|---|---|
| claim-bullets | 14 | 1 (ultra-short) | Default for everything |
| flat-bullets | 2 | 1 (games list) | Only <5KB short override |
| themed-claims | 2 | 1 (TED multi-talk) | Long multi-theme interviews/panels |
| step-list | 2 | 0 | Tutorial/recipes only |
| what-why-how | 0 | 7 | Archived — claim-bullets always better |
| concept-card | 0 | 3 | Archived — 2-3x longer for same content |

## Key Findings

### claim-bullets wins because
- Bold claim is scannable — reader knows if they care before reading detail
- Flat list has zero structural overhead (no scaffolding)
- Scales from 2KB to 268KB transcripts
- Works across all content types: reviews, education, interviews, rants, listicles

### flat-bullets loses to claim-bullets except ultra-short
- Category labels tell topic but not *why it matters*
- Exception: <5KB transcript where claims add bulk without value

### themed-claims wins a narrow niche
- Long multi-theme interviews (Ferriss 1.5h) and panels (Women in Tech 1h)
- Theme headings group related claims — prevents flat list of 10+ disconnected bullets
- Does NOT help when topics don't shift clearly (TED multi-talk, short interviews)

### concept-card and what-why-how: archived
- concept-card: 3-5 evidence bullets + core idea + implication per section = 2-3x output vs claim-bullets for same information
- what-why-how: 4 labeled fields × N units = reader fatigue past 2 units. claim-bullets covers same ground without labels

### step-list: correct for tutorials
- Recipes and coding tutorials require sequential steps — claim-bullets cannot represent order dependency

## Budget Compliance

Claim-bullets mostly stays within budget on first pass. Tighten step handles remainder. Previous formats (concept-card, what-why-how) systematically exceeded budget because structural minimum floor > budget ceiling for medium transcripts.

## Classification Changes

- Single speaker opinions → TIPS (was defaulting to INTERVIEW)
- Single speaker explaining mechanism → EDUCATIONAL (not TIPS)
- INTERVIEW requires 2+ participants in dialogue
- Default fallback: TIPS (was INTERVIEW)

## Resulting Routing (active formats only)

| Content type | Format |
|---|---|
| TIPS | claim-bullets |
| EDUCATIONAL | claim-bullets |
| INTERVIEW (short/normal) | claim-bullets |
| INTERVIEW (long, multi-theme, >30 min) | themed-claims |
| TUTORIAL | step-list |
| Ultra-short (<5KB) | flat-bullets (override) |
| Escape hatch | claim-bullets |
