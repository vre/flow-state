# Planning Reflection: Graph Link Support — Cut 1

**Plan**: `docs/plans/2026-04-25-graph-links-cut1.md`
**Date**: 2026-04-25

## What the review process caught

Two review rounds, 18 findings total. The critical ones:

1. **Wrong tiebreaker in `resolve_wikilink`** — initial plan used "shortest path" when Obsidian uses proximity to source file. Would have produced incorrect resolution for vaults with duplicate filenames. The frame's `source_path` parameter was there for a reason; I dropped it thinking it was unnecessary for Cut 1.

2. **Unbounded HTTP concurrency** — `backlinks` and `broken_links` would have fired thousands of concurrent HTTP requests via `asyncio.gather`. The existing `read_files` pattern doesn't batch. Adding batching (50 files) prevents API overwhelm.

3. **`outlinks` didn't resolve targets** — Frame expected resolved paths (`notes/foo.md`), plan returned raw wikilink text (`foo`). Misread of the frame's return format.

4. **`broken_links` resolution scope** — Using `list_vault_files(path)` for both scan set and resolution set would produce false positives when scanning a subdirectory (links to files outside the subdirectory would appear broken).

5. **Missing `resolve_relative_path`** — Markdown links are relative to the source file. No function existed to resolve `../foo.md` against a source path. Both `backlinks` and `broken_links` depended on this.

## Key design decisions

- **Embeds (`![[...]]`) included** — They create graph edges in Obsidian. Tagged with `"embed": true` so callers can filter if needed.
- **Markdown images excluded** — `![alt](img.png)` is not a navigational link. Negative lookbehind `(?<!!)` handles this.
- **Code blocks not filtered** — Acceptable simplification. Most graph tools do the same. Could revisit in Cut 2 if needed.
- **`[[#heading]]` self-references excluded** — Out of scope for Cut 1. Would need source file tracking in `parse_links` to resolve.
- **Heading fragment validation skipped** — `[[foo#heading]]` only checks `foo.md` exists, not that the heading exists within it. Reasonable for Cut 1.

## Lessons

The frame provided `source_path` in the function signature for a reason. When a frame specifies a parameter, assume it's there for a reason before dropping it. The "simplification" cost a review round.
