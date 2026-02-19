# Step List

Status: active
Content type: TUTORIAL

Numbered steps with outcomes. Prerequisites at top, result at bottom. For step-by-step instructions, coding walkthroughs, recipes.

## Template

```
**Prerequisites**: [if any]
1. [Step with outcome]
2. [Step with outcome]
3. [Step with outcome]
**Result**: [what you end up with]
```

## Example

```
**Prerequisites**: Node.js 20+, npm, empty directory
1. `npx create-next-app@latest my-app` — scaffolds project with TypeScript and Tailwind
2. `cd my-app && npm run dev` — starts dev server on localhost:3000
3. Edit `app/page.tsx` — replace default content, see hot reload in browser
4. `npm run build` — produces optimized production bundle in `.next/`
**Result**: Running Next.js app with TypeScript, Tailwind, hot reload, ready for deployment
```

## Rules

- Prerequisites: list tools, versions, prior knowledge needed. Omit line if none
- Steps: numbered, each with concrete outcome or observable result
- Result: one sentence describing what the viewer has after completing all steps
- Keep steps sequential — each depends on the previous one
- Include commands verbatim when the video shows them
