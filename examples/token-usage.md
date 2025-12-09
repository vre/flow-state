# Token Usage for the examples

## youtube - Thieves HATE This Travel Gear (Zero Thefts in 10 Years (h-S0Lo6Xlr4))

Token usage by phase:

  | Step                     | Phase                       | Model  | Tokens | Time   | Cost  |
  |--------------------------|-----------------------------|--------|--------|--------|-------|
  | youtube-to-markdown      |                             |        |        |        |       |
  | 4                        | Identify paragraph breaks   | Sonnet | 16.3k  | -      | $0.05 |
  | 5                        | Summarize transcript        | Sonnet | 23.5k  | -      | $0.08 |
  | 6                        | Review and tighten summary  | Sonnet | 22.3k  | 1m 24s | $0.08 |
  | 7                        | Clean speech artifacts      | Haiku  | 26.0k  | 1m 5s  | $0.03 |
  | 8                        | Add topic headings          | Sonnet | 25.5k  | 2m 11s | $0.09 |
  |                          | Subtotal                    |        | 113.6k | ~5min  | $0.33 |
  | youtube-comment-analysis |                             |        |        |        |       |
  | 3                        | Extract insightful comments | Sonnet | 54.7k  | 1m 44s | $0.18 |
  |                          | Subtotal                    |        | 54.7k  | ~2min  | $0.18 |
  |                          | TOTAL                       |        | 168.3k | ~7min  | $0.51 |

  Note: Steps 4+5 ran in parallel so actual wall time was shorter than sum.