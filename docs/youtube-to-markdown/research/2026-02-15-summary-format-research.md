# INTERVIEW Summary Format Research

Research process for finding a better scannable summary format for YouTube interview videos.

## 1. Problem

INTERVIEW format produced heading + 2-3 sentence prose paragraph per section. The result is not scannable — everything looks like the same grey wall, no anchor points for the eye. Headings too short to tell whether the content is interesting. Text below the heading is dense but unstructured.

Example of the problem (current format):

```
### Parallel Workflow
Boris runs 5-10 concurrent sessions. Morning: kicks off 3 from phone. Half his coding
on iOS, rest split terminal/web. Use case: Co-work checks spreadsheets, Slack-messages
engineers about missing updates while he gets coffee.
```

### Test videos

Three interviews of different types:

- **Claude Cowork** — 42 min, 2 speakers, tech-focused
- **ClawdBot** — 28 min, 1 speaker, setup-focused
- **Peliteoreetikko** — 2h 48min, 2 speakers, Finnish, academic

Selection criteria: variation in length, language, structure, and content. If a format works for all three, it generalizes.

## 2. Web research: 10 formats from literature

Sources: collected known methods using search terms "summary formats", "note-taking methods", "structured note formats". Original authors cited per format. Individual URL references were not saved during the research session.

### 2.1 Progressive Summarization (Tiago Forte)

**Description**: Five layers: raw text → **bold** → ==highlight== → summary → remix. Each layer compresses the previous one.

**Visual structure**: Original text preserved, visual layers added on top. Reader chooses depth via bold and highlight levels.

**Why scannable**: Multiple reading speeds — highlights only, highlights + bold, full text.

**Weaknesses**: Does not restructure content, preserves original order. Requires multiple passes through material. Does not produce a single summary document.

**Markdown suitability**: Partial. `**bold**` works, `==highlight==` is not standard markdown (Obsidian supports it).

### 2.2 Cornell Notes (Walter Pauk, 1950s)

**Description**: Two columns (cue words on left, notes on right) + summary strip at bottom. Three spatial areas = three entry points.

**Visual structure**: Left column serves as index, right column contains details, bottom summarizes the entire page.

**Why scannable**: Left column cue words show topics immediately. Bottom summary suffices for quick overview.

**Weaknesses**: Rigid layout does not translate to markdown without CSS. Column structure requires tables or custom styles.

**Markdown suitability**: Poor. Table technically possible but readability suffers with long cells.

### 2.3 Zettelkasten (Niklas Luhmann)

**Description**: One note = one idea. Heading states a claim. Notes link to each other forming a network.

**Visual structure**: Atomic cards, each containing one thought in own words. Network structure emerges from linking.

**Why scannable**: Each card is independent and quick to read.

**Weaknesses**: Poor for a single summary — produces 15-30 separate notes per interview without one scannable artifact.

**Markdown suitability**: Good for individual cards, but requires multi-file structure to work.

### 2.4 Sketchnote Text Equivalent (Mike Rohde)

**Description**: Multiple text sizes, spatial grouping, containers around key findings, arrows for flow.

**Visual structure**: Visually rich — size variations, frames and grouping guide the eye.

**Why scannable**: Spatial variation creates natural anchor points.

**Weaknesses**: Does not scale, difficult to automate. Requires manual planning for each piece of content.

**Markdown suitability**: Poor. Markdown has no spatial control, font sizes, or containers.

### 2.5 Inverted Pyramid (Journalism)

**Description**: Most important first, least important last. Article can be cut from any point without losing the core.

**Visual structure**: Linear prose flow, ordered by importance.

**Why scannable**: First paragraphs suffice for the main point.

**Weaknesses**: Prose-based, no visual anchors. Does not work for multi-topic content — an interview covers 10-15 topics.

**Markdown suitability**: Good (prose is markdown's core form), but the scannability problem remains unsolved.

### 2.6 QEC — Question / Evidence / Conclusion (Cal Newport)

**Description**: Repeating block structure: question, evidence, conclusion. Questions serve as cognitive hooks.

**Visual structure**: Clear three-part split that repeats. Question stands out visually.

**Why scannable**: Topics visible quickly from questions.

**Weaknesses**: Forces everything into Q&A form. "Clickbait headline" feel — point hidden behind the question.

**Markdown suitability**: Good. `### Q:` + bullets + `→` conclusion work natively.

### 2.7 MOC — Map of Content (Nick Milo)

**Description**: Central note links to detailed notes. Sections group links by theme.

**Visual structure**: Link list grouped under headings. Functions as a navigation hub.

**Why scannable**: Headings + link texts convey content quickly.

**Weaknesses**: Requires multiple files. Overcomplicated for a single summary.

**Markdown suitability**: Technically excellent (links are markdown's core feature), but multi-file overhead is not justified.

### 2.8 CER — Claim / Evidence / Reasoning (Science Education)

**Description**: Three named blocks per insight: claim, evidence, reasoning. Claim gives takeaway in one line.

**Visual structure**: Repeating three-block structure with labels.

**Why scannable**: Claim block shows the main point immediately.

**Weaknesses**: Formal and academic. Does not handle narratives, stories, or emotional content naturally.

**Markdown suitability**: Good. Labels + bullets work.

### 2.9 Outline Method (Traditional Academic)

**Description**: Indentation shows hierarchy. Numbers and letters create order.

**Visual structure**: Indentation levels are the only visual variation.

**Why scannable**: Hierarchy visible quickly from indentation.

**Weaknesses**: Monotonous — no visual variation beyond indentation level. In long documents everything looks the same.

**Markdown suitability**: Excellent. Indentation and lists are markdown's basic structure.

### 2.10 Dashboard / Briefing (Executive Reporting)

**Description**: Fixed areas: metadata, TL;DR, findings, quotes, action items. Everything on one page.

**Visual structure**: Zone-divided page, visually enriched with different elements.

**Why scannable**: Fixed structure — reader knows where to find what.

**Weaknesses**: Lossy — forces more compression than content allows. Difficult to render in plain markdown.

**Markdown suitability**: Moderate. Basic elements work, but no native support for visual zone layout.

### Markdown suitability summary

**Work in markdown**: QEC, CER, Outline, claim-based formats — their core structures (headings, bullets, bold) are native markdown.

**Require layout features**: Cornell, Dashboard, Sketchnote — columns, spatial areas and containers cannot be represented in plain markdown.

**Require multi-file structure**: Zettelkasten, MOC — only work when producing multiple files, which is not the summary plugin's goal.

## 3. Tested formats

Each format was tested on all three videos. Common example content: "Parallel Workflow" from the Cowork video.

### 3.1 Original INTERVIEW prose (current)

**Template**:
```
### [Content Unit Title]
[2-3 sentence narrative. "Quote if impactful."]
```

**Example**:
```
### Parallel Workflow
Boris runs 5-10 concurrent sessions. Morning: kicks off 3 from phone. Half his coding
on iOS, rest split terminal/web. Use case: Co-work checks spreadsheets, Slack-messages
engineers about missing updates while he gets coffee.
```

**Assessment per video**:
- **Cowork**: Heading "Parallel Workflow" says nothing about the claim. Prose below is dense but unstructured. Reader must read the entire paragraph to know what it's about.
- **ClawdBot**: Same problem. Short headings like "Setup" or "Workflow" don't differentiate sections.
- **Peliteoreetikko**: 15+ prose paragraphs in sequence. Eye finds no anchor points. Grey wall.

**Decision**: **Rejected**. Archived as reference.

### 3.2 TIPS adapted for interview

**Template**:
```
- **[Category]**: [item], [item], [item]
```

**Example**:
```
- **Parallel sessions**: 5-10 concurrent, kicks off 3 from phone mornings
- **Platform split**: Half iOS, rest terminal/web
- **Delegation**: Co-work checks spreadsheets, Slack-pings engineers autonomously
```

**Assessment per video**:
- **ClawdBot**: Works. Content naturally breaks into short fragments.
- **Cowork**: Works. Concrete tips fit the category + list format.
- **Peliteoreetikko**: Does not work. Academic content doesn't break into short fragments — each bullet bloats to 3-line prose, eliminating the format's advantage.

**Decision**: **Not suitable for interviews generally**. Works when content naturally breaks into short fragments, but doesn't generalize to narrative or academic content.

### 3.3 EDUCATIONAL adapted for interview

**Template**:
```
### [Content Unit Title]
**What**: [definition]
**Why**: [reasoning]
**How**: [mechanism]
**What Then**: [implications]
```

**Example**:
```
### Parallel Workflow
**What**: 5-10 concurrent Claude sessions simultaneously
**Why**: Frees human from sequential task bottleneck
**How**: Morning kickoff from phone, Co-work handles spreadsheets + Slack autonomously
**What Then**: Developer focuses on direction, not execution
```

**Assessment per video**:
- **ClawdBot**: Does not work. Setup-focused content doesn't fit the What/Why/How/What Then frame naturally.
- **Cowork**: Does not work. Four labels per section is too much structural overhead. Labels force filling fields even when content doesn't naturally divide into four parts.
- **Peliteoreetikko**: Mechanical repetition across 7+ sections. Same four-block pattern repeats until the reader becomes numb to the structure.

**Decision**: **Not suitable for interviews**. Pattern forces filler words, structure repeats heavily in longer summaries.

### 3.4 TUTORIAL adapted for interview

**Template**:
```
1. [Step with outcome]
2. [Step with outcome]
```

**Example**:
```
1. Morning: kick off 3 sessions from phone
2. Co-work checks spreadsheets, Slack-messages engineers
3. Split remaining work: iOS / terminal / web
```

**Assessment per video**:
- **ClawdBot**: Works — video is structurally almost a tutorial, so sequencing is natural.
- **Cowork**: Partially works — Boris gave concrete setup instructions, but some content is opinions and experiences that aren't steps.
- **Peliteoreetikko**: Creative but not a summary. Academic discussion forced into steps, which is a narrative rearrangement that loses context and nuance.

**Decision**: **Does not generalize to interviews**. Works when content has natural sequencing, but forces sequence on content where none exists.

### 3.5 Claim-first bullets (new)

**Template**:
```
### [Claim as long informative heading]
- [evidence bullet, front-loaded]
- [evidence bullet]
- [evidence bullet]
```

**Example**:
```
### Running 5-10 parallel sessions beats going deep on one task
- Boris kicks off tasks from terminal, phone, and web simultaneously
- "Tending to your Claudes" — bounce between sessions, unblock each
- Parallel execution offsets slower per-task speed
- Real example: Slack-message engineers whose status columns are empty, go get coffee
```

**Assessment per video**:
- **ClawdBot**: Works. Long informative headings tell immediately what the section is about.
- **Cowork**: Works. Heading tells whether bullets are worth reading. Bullets are fast to scan — first word or three tells whether to read the full sentence.
- **Peliteoreetikko**: Works. 15 sections scannable at heading level.

**User observation**: "I can scan from the heading whether the bullets interest me, and bullets are a fast way to scan from the beginning word or three whether I read the whole sentence. First words' significance is high."

**Decision**: **Archived**. Lighter version of Concept Card. Missing the core idea sentence (context without reading bullets) and implication sentence (what this means) that give the reader choice points.

### 3.6 QEC — Question / Evidence / Conclusion (new)

**Template**:
```
### Q: [Sharp question]
- [evidence]
- [evidence]
- → [conclusion]
```

**Example**:
```
### Q: Why does Boris run 5-10 sessions instead of focusing on one?
- Kicks off tasks from terminal, phone, and web simultaneously
- Co-work handles spreadsheets and Slack autonomously
- Individual task speed matters less than total throughput
- → Parallelism beats depth — the workflow shifts from "doing" to "tending"
```

**Assessment per video**: Question form forces the reader to read the entire question to find out if the answer interests them. The point is hidden behind the question and not visible when scanning. Clickbait headline feel.

**User assessment**: "I don't think I like this making questions format — I need to read more to discover the point I might not care about. Kind of click headlines style."

**Decision**: **Rejected**. Question form hides the main point at the cost of scannability.

### 3.7 Layered — claim list + evidence (new)

**Template**:
```
### Layer 1: Key claims
- **[Claim 1]**
- **[Claim 2]**

### Layer 2: Claims with evidence
#### [Claim 1]
- [evidence]
- [evidence]
```

**Example**:
```
### Layer 1: Key claims
- **Running 5-10 parallel sessions beats going deep on one task**
- **Once the plan is good, the code is good**

### Layer 2: Claims with evidence
#### Running 5-10 parallel sessions beats going deep on one task
- Morning: kicks off 3 sessions from phone
- Terminal, web, iOS, Android simultaneously
- Workflow shifts from "doing" to "tending"
```

**Assessment per video**: Layer 1 is too condensed to be useful without context — bare claim without any hint of what's underneath. Layer 2 repeats the same headings. This was the longest of all tested formats.

**User assessment**: "Key claims might be too condensed to be useful without knowing the topic. Then in layer 2 repeats the headers."

**Decision**: **Rejected**. Repetition between layers and summary layer's lack of context make the format useless.

### 3.8 Dialogue Essence — who said what (new)

**Template**:
```
### [Topic heading]
> **[Speaker]**: [compressed quote]
- [context/evidence]
> **[Other speaker]**: [response]
```

**Example**:
```
### The real advantage is parallelism, not speed
> **Boris**: 5-10 sessions daily. Half my coding on iOS. Kick off 3 from phone in the morning.
- Co-work handles spreadsheets and Slack-messages engineers autonomously
> **Greg**: How do you manage context across that many?
> **Boris**: You don't go deep — you tend to them like a generalist.
```

**Assessment per video**: Interesting mix of quotes and summary. Better headings than original INTERVIEW format. But long, too many quotes. More "editor's cut" than summary — a condensed version of the interview, not an analytical summary.

**User assessment**: "Interesting mix of interview quotes and summary... I feel this is more transcript editor's cut than summary."

**Decision**: **Archived**. Potential when speaker dynamics are essential to the content (e.g. debates, disagreements).

### 3.9 Concept Card v1 (new)

**Template**:
```
---
#### [Concept name]
**Core idea**: [one sentence]
**Evidence**:
- [bullet]
- [bullet]
**So what**: [one sentence]
```

**Assessment per video**:
- **Cowork**: Interesting middle ground. Easier to read at selected depth than claim-first. Heading + "Core idea" together give sufficient picture without bullets.
- **ClawdBot**: Shorter headings + "Core idea" sentence didn't add value with this content. Labels ("Core idea:", "Evidence:", "So what:") added visual noise.

**User assessment (Cowork)**: "This is also interesting middle ground... Easier to read to selected depth before scanning forward than format_new1."

**User assessment (ClawdBot)**: "Somehow I don't think the shorter headings and the core and.. it is not so good with this."

**Decision**: Promising structure but labels and short headings problematic. Iterate.

### 3.10 Concept Card v2

**Change from v1**: Longer claim heading (like claim-first), core idea text without label, implication without label. Labels removed entirely.

**Problem**: Em-dash (—) overused in headings. Nearly every heading contained an em-dash, making headings visually identical and harder to scan.

**User assessment**: "Its overuse is confusing, it can be handled with other structures, even a comma works."

**Decision**: Direction correct, em-dash problem needs fixing.

### 3.11 Concept Card v3 (winner)

**Template**:
```
---
### [Long claim heading, one sentence, normal punctuation]

[Core idea in one sentence. No label, no bold, no bullet.]

- [evidence, front-loaded]
- [evidence]
- [evidence]

[Implication in one sentence. No label, no bold, no bullet.]
```

**Example**:
```
---
### Running 5-10 parallel sessions beats going deep on one task

Boris typically runs concurrent sessions across terminal, web, iOS, and Android simultaneously.

- Morning: kicks off 3 sessions from phone
- Co-work handles spreadsheets and Slack-messages engineers autonomously
- Workflow becomes "tending to your Claudes" — checking blockers, steering, bouncing
- Engineers adopted this first; Cowork extends it to sales, design, PMs

Individual task speed matters less than total throughput across concurrent work.
```

**Assessment per video**:
- **Cowork**: Works. Long heading states the claim. Core idea sentence gives context without reading bullets. Bullets are scannable. Implication sentence closes and gives the "so what" answer.
- **ClawdBot**: Works. Informative headings make 10+ sections a scannable list.
- **Peliteoreetikko**: Works. 15 academic sections stay readable. Core idea sentence provides sufficient context even when the topic is unfamiliar.

**Structural strengths**:
- **Heading**: Long claim sentence — when scanning you immediately know if the section is interesting
- **Core idea**: Context in one sentence — no need to read bullets to know what it's about
- **Bullets**: Front-loaded — first word or two tells whether to read to the end
- **Implication**: "So what" answer — why this matters
- **Separator** (`---`): Visual boundary between sections

**Decision**: **Approved. New INTERVIEW format.**

## 4. Iteration history: Concept Card v1 → v2 → v3

| Version | Change | Problem | Solution |
|---------|--------|---------|----------|
| v1 | Short headings + labels ("Core idea:", "Evidence:", "So what:") | Short headings didn't work on ClawdBot. Labels added visual noise without information value. | → v2: lengthen headings, remove labels |
| v2 | Longer claim heading, labels removed, plain text for core idea and implication | Em-dash (—) overused in headings — every heading looked the same. | → v3: normal punctuation |
| v3 | Em-dash fix, normal punctuation in headings | — | Approved |

Iteration demonstrated two things:
1. Labels are visual noise when structure is already clear from position (core idea = first sentence, implication = last sentence)
2. Heading length and informativeness are the single most important factor for scannability

## 5. Decision

INTERVIEW format replaced with **Concept Card** format (v3).

**Format hierarchy**:
- **Concept Card** (v3) — new INTERVIEW default. Works across all tested content types.
- **Claim-first bullets** — lighter alternative. Works but lacks core idea/implication layer that gives the reader choice points without reading bullets.
- **Dialogue Essence** — archived for future use. Potential when speaker dynamics are essential to the content.

## 6. Test file paths

Note: `/tmp/claude/` paths are session-local and do not survive restarts. They document what was produced in the research session 2026-02-15. Reproducible tests use video IDs (DW4a1Cm8nG4, h-s0lo6xlr4, MW6FMgOzklw) and skill pipeline runs.

### Original video summaries

- `/Users/vre/Sync/Obsidian/Joplinpoplin/Youtube/2026-01-23 - youtube - I got a private lesson on Claude Cowork & Claude Code (DW4a1Cm8nG4).md`
- `/Users/vre/Sync/Obsidian/Joplinpoplin/Youtube/2026-01-24 - youtube - ClawdBot is the most powerful AI tool I've ever used in my (Qkqe-uRhQJE).md`
- `/Users/vre/Sync/Obsidian/Joplinpoplin/Youtube/2025-11-25 - youtube - maailman nro.1 peliteoreetikko bottini voittaa parhaat (vq1jvfiw7dm).md`

### Old format tests (TIPS / EDUCATIONAL / TUTORIAL)

- `/tmp/claude/format_test_cowork.md`
- `/tmp/claude/format_test_clawdbot.md`
- `/tmp/claude/format_test_peliteoreetikko.md`

### New format tests

- `/tmp/claude/format_new1_*.md` — Claim-first bullets
- `/tmp/claude/format_new2_*.md` — QEC
- `/tmp/claude/format_new3_*.md` — Layered
- `/tmp/claude/format_new4_*.md` — Dialogue Essence
- `/tmp/claude/format_new5_*.md` — Concept Card v1
- `/tmp/claude/format_card2_*.md` — Concept Card v2
- `/tmp/claude/format_card3_*.md` — Concept Card v3 (winner)
