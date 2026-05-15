# Step List

Status: active
Content type: TUTORIAL

Numbered steps with outcomes. Prerequisites at top, result at bottom. For step-by-step instructions, coding walkthroughs, recipes.

## Template

```
## [Main heading for the entire video — one sentence, informative]

**TL;DR**: [1 sentence synthesis]

**Prerequisites**: [if any]
1. [Step with outcome]
2. [Step with outcome]
3. [Step with outcome]
**Result**: [what you end up with]

## Hidden Gems
- [Gotcha, tip, or tangent outside the main steps]
```

## Example

```
## Build a Next.js app from scratch in 10 minutes

**TL;DR**: npx create-next-app scaffolds a production-ready TypeScript + Tailwind project in one command; the rest is replacing default content.

**Prerequisites**: Node.js 20+, npm, empty directory
1. `npx create-next-app@latest my-app` — scaffolds project with TypeScript and Tailwind
2. `cd my-app && npm run dev` — starts dev server on localhost:3000
3. Edit `app/page.tsx` — replace default content, see hot reload in browser
4. `npm run build` — produces optimized production bundle in `.next/`
**Result**: Running Next.js app with TypeScript, Tailwind, hot reload, ready for deployment

## Hidden Gems
- Passing `--empty` skips the sample files entirely — cleaner starting point than deleting defaults
```

## Rules

- Main heading: ## level, one sentence, informative
- TL;DR: mandatory, never remove, one sentence synthesis
- Prerequisites: list tools, versions, prior knowledge needed. Omit line if none
- Steps: numbered, each with concrete outcome or observable result
- Result: one sentence describing what the viewer has after completing all steps
- Keep steps sequential — each depends on the previous one
- Include commands verbatim when the video shows them
- Multi-part tutorials (multiple recipes, several projects): use `### [Part title]` heading per part, each with its own prerequisites/steps/result block
- Hidden Gems: end with `## Hidden Gems` if the tutorial contains useful tips, gotchas, or tangents outside the main steps. 1-3 bullets. Omit only if nothing qualifies.
