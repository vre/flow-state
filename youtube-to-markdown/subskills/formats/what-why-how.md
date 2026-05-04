# What-Why-How

Status: archive
Content type: EDUCATIONAL

Four labeled fields per content unit. Structured knowledge extraction for concept explanations and analysis.

## Template

```
### [Content Unit Title]
**What**: [definition/description]
**Why**: [reasoning/importance]
**How**: [mechanism/application]
**What Then**: [implications if actionable]
```

## Example

```
### Retrieval-Augmented Generation
**What**: LLM queries external knowledge base at inference time instead of relying solely on training data
**Why**: Reduces hallucination, keeps answers current without retraining
**How**: User query → embed → vector search → top-k chunks injected into prompt → LLM generates answer
**What Then**: Production RAG needs chunking strategy, embedding model selection, and relevance threshold tuning
```

## Rules

- All four labels mandatory: What, Why, How, What Then
- Each field: 1-2 sentences, no more
- What Then: omit only if content unit has no actionable implications
- **Max 2 content units**. If the topic requires 3 or more, the content is too broad for this format — switch to claim-bullets.md
- Best for: single concept or narrow topic explained in depth
