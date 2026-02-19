# What-Why-How

Status: active
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
- Works best with 2-5 content units per video. Beyond 7 units, merge related topics to reduce count
