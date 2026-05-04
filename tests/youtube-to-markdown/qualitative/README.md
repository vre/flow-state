# Qualitative Test Matrix — youtube-to-markdown

Stress-tests summarization across video types, lengths, and structures that differ from the typical content the skill was optimized for.

## Test Matrix

| # | Video | Duration | Type | Tests |
|---|---|---|---|---|
| 1 | Recursion in 100 Seconds (rf60MejMz3E) | ~2 min | Ultra-short educational | Summary longer than input? |
| 2 | TypeScript in 100 Seconds (zQnBQ4tB3ZA) | ~2 min | Ultra-short overview | Same — minimal content |
| 3 | A rant about professional programming (uDmXeqfS3no) | ~? | Monologue/rant | Misclassification as INTERVIEW |
| 4 | The magical science of storytelling - TEDx (Nj-hdQMa3uA) | ~17 min | Educational/narrative | Story vs. facts tension |
| 5 | How changing your story can change your life - TED (O_MQr4lHm0c) | ~16 min | Personal narrative | Emotion-driven, not informational |
| 6 | Marc Andreessen: Lex Fridman #458 (OHWnPOKh_S0) | ~3h | Long podcast | Scale of concept card |
| 7 | Harvard CS50 2023 full (LfaMVlDaQ24) | ~26h | Mega lecture | Absurd extreme |
| 8 | Women in Technology Panel (T44XdGH5s-8) | ~? | Panel, multi-speaker | Real multi-speaker dynamics |

## Evaluation Criteria

Per video:
- **Classification**: what skill chose vs. what's correct
- **Length ratio**: summary bytes / transcript bytes (target <10%)
- **Quality** (1-5): information density, no fluff, actionable
- **Structure fit**: does the chosen format match the content?
- **Edge case**: what broke or almost broke

## Running

```bash
cd /path/to/flow-state
# Extract to qualitative/videos/<slug>/
# Option A (summary + comments) unless stated otherwise
```

Results go in `results/<date>-<slug>.md`. Videos dir is gitignored.
