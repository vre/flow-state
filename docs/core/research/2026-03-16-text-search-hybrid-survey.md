# Text Content Search Survey: Hybrid Approaches for Markdown, Docs & Journals

Date: 2026-03-16

## Context

Evaluated open-source tools for searching personal text content (markdown notes, documentation, transcripts, journals). Core hypothesis: pure semantic search is insufficient — needs structure (BM25, reranking, query expansion). Multilingual (Finnish/English) adds tokenization and cross-lingual challenges.

## Reference Tools

### 1. QMD (tobi/qmd) — Benchmark: hybrid done right

- Author: Tobi Lutke (Shopify CEO), ~15.7k stars, MIT, TypeScript/Bun
- **7-step hybrid pipeline**, fully local (~2GB GGUF models via node-llama-cpp)
- Storage: single SQLite DB with FTS5 (BM25) + sqlite-vec (vectors)

**Pipeline:**

1. BM25 probe — if dominant result (score >= 0.85), skip expensive steps ("strong signal bypass")
2. Query expansion — finetuned Qwen3-1.7B generates typed expansions:
   - `lex:` keyword variants → BM25
   - `vec:` natural language phrases → vector search
   - `hyde:` hypothetical document passages → vector search
3. Type-routed parallel search (FTS sync, vectors batched)
4. Reciprocal Rank Fusion (k=60, original query gets 2x weight)
5. Smart chunking (~900 tokens, 15% overlap, never splits code fences)
6. LLM re-ranking (Qwen3-reranker, cached by content hash)
7. Position-aware score blending (top retrieval results protected from reranker disagreement)

**Models:** embeddinggemma-300M (Q8_0), qwen3-reranker-0.6B (Q8_0), qmd-query-expansion-1.7B (Q4_K_M)

**MCP server:** stdio + HTTP, dynamic system instructions from index state, `qmd://` URI scheme

**Key design decisions:**
- Chunk-level reranking (not full docs) — avoids O(tokens) cost
- Query expansion + reranker scores cached in SQLite by hash
- Strong signal bypass saves expensive LLM calls when BM25 is confident
- Embedding format awareness (embeddinggemma vs Qwen3-Embedding prefixes)

### 2. txtai (neuml/txtai) — Swiss army knife

- Python, all-in-one AI framework: search, RAG, agents, QA, summarization, translation
- Hybrid search (sparse + dense) built-in, multimodal indexing
- Bindings: Python, JS, Java, Rust, Go

**Tradeoffs vs QMD:**
- (+) Broader capability set (pipelines, multimodal, agents)
- (+) More embedding model options
- (-) Kitchen-sink complexity — most users need 10% of features
- (-) No native BM25 at inverted-index quality (sparse index is approximate)
- (-) No query expansion or reranking pipeline
- (-) Heavy dependency tree (Python 3.10+, HuggingFace ecosystem)

### 3. Semantra (freedmand/semantra) — Pure semantic baseline

- Python CLI/UI for local semantic document search (PDF, text)
- MPNet/MiniLM embeddings, Annoy for ANN retrieval
- Query refinement via +/- tagging of results (interactive)

**Tradeoffs vs QMD:**
- (+) Dead simple UX: point at files, search
- (+) No generative models — treats source as authoritative
- (-) **Pure semantic only** — explicitly states it will miss exact text matches
- (-) No keyword/BM25 component at all — proper nouns and identifiers return noise
- (-) No server mode, no API, no MCP
- (-) Appears unmaintained

### 4. Meilisearch — Best user-facing search

- Rust, sub-50ms, typo tolerance, prefix matching, faceted search
- Recently added hybrid (semantic + full-text)
- Multi-language tokenization (CJK etc.)

**Tradeoffs vs QMD:**
- (+) Speed: sub-50ms design target
- (+) Typo tolerance and prefix matching — best for search-box UX
- (+) Multi-language tokenization more mature
- (+) Production-grade: single binary, Docker, SDKs
- (-) Designed for structured records (products, articles), not long-form documents
- (-) Semantic search is recent — less mature
- (-) No query expansion, no reranking
- (-) No smart document chunking
- (-) Enterprise features require paid license

### 5. Chroma / Qdrant — Infrastructure, not solutions

**Chroma:** Minimal vector DB, 4-function API. Vector-only in OSS (hybrid only on paid Cloud). You build chunking, embedding, ranking yourself.

**Qdrant:** High-performance vector engine (Rust, HNSW, SIMD). Sparse + dense vectors. Rich payload filtering with query planner. Production-grade (WAL, sharding, replication, quantization).

**Tradeoffs vs QMD:**
- (+) Better at scale (millions of vectors)
- (+) Production infrastructure (replication, sharding)
- (-) Building blocks, not a solution — you write the entire search pipeline
- (-) No document ingestion, no chunking, no ranking fusion
- (-) Overkill for document-scale search

### 6. Obsidian Smart Connections — Incumbent in-vault semantic search

- Obsidian plugin, source-available, built on jsbrains framework
- Local-first: zero-config embedding via transformers.js (WebGPU → WASM fallback)
- Block-level granularity: each heading/paragraph gets its own embedding vector
- Smart Connect app: separate MCP bridge product for ChatGPT/Claude access

**Architecture:**
- Smart Environment → Smart Sources (notes) → Smart Blocks (sub-heading segments)
- Both source-level (whole note) and block-level embeddings computed
- `embed_input`: strips excluded lines, prepends breadcrumbs (folder hierarchy), enforces token limits
- Data stored in `vault/.smart-env/`

**Embedding models (13 local, bundled):**

| Model | Dims | Max Tokens | Notes |
|---|---|---|---|
| TaylorAI/bge-micro-v2 (default) | 384 | 512 | Tiny, fast |
| Snowflake/arctic-embed-m | 768 | 512 | Better quality |
| onnx-community/embeddinggemma-300m | 768 | 2048 | Longer context |
| Xenova/jina-embeddings-v2-base-zh | 768 | 8192 | **Only multilingual local option** (zh/en) |
| nomic-ai/nomic-embed-text-v1.5 | 768 | 2048 | Some multilingual capability |

Cloud options: OpenAI, Gemini, Ollama, LM Studio, OpenRouter.

**Search mechanism: Pure vector, no hybrid.**
1. Query → embed → query vector
2. Brute-force cosine similarity over ALL filtered entities (no ANN index)
3. Statistical cutoff: stops returning results when score gap exceeds std dev
4. At least 3 results before cutoff applies; threshold relaxes by 1.5x if under 3

**Reranking infrastructure exists but is NOT wired in:**
- jsbrains framework includes `smart-rank-model` with Cohere reranker + local cross-encoders (jina-reranker-v1-tiny-en, mxbai-rerank-xsmall-v1, bge-reranker-base)
- `find_connections` flow: filter → nearest (cosine sim) → sort → limit → cache → return. No reranking step.

**Separate lexical search exists but is NOT combined with vector search:**
- `SmartSources.search()` does text frequency matching in batches of 10
- This is a separate code path from vector similarity — no hybrid fusion

**Tradeoffs vs QMD:**
- (+) Zero-config: install plugin, it indexes automatically
- (+) Block-level granularity: paragraph-level connections, not just document-level
- (+) Obsidian integration: inline connections view, backlink awareness
- (+) Breadcrumb context: folder hierarchy prepended to embeddings — adds structural signal
- (+) Live vault sync: file watcher auto-reindexes on change
- (+) Mobile support (WebGPU/WASM)
- (-) **Pure vector search** — no BM25, no hybrid ranking
- (-) **No query expansion** — vocabulary mismatch is unaddressed
- (-) **Reranking code exists but is unused** — missed opportunity
- (-) **Brute-force cosine over all entities** — no ANN index (Annoy, HNSW), scales poorly with vault size
- (-) **Statistical cutoff is fragile**: std dev threshold assumes score distribution is well-behaved. With noisy small embeddings (bge-micro-v2, 384d, 512 tokens), scores cluster tightly → cutoff may remove relevant results or include irrelevant ones
- (-) Default model (bge-micro-v2) is very small: 384d, 512 token max — long notes get truncated, quality is baseline
- (-) **No Finnish/multilingual model as default** — jina-v2-base-zh covers Chinese/English only. Finnish requires manual model selection and even then no model in the bundle handles Finnish well
- (-) No MCP in the plugin itself (Smart Connect app is a separate paid product)
- (-) Obsidian-locked: vault data in `.smart-env/` is not portable

**Reddit signals:**
- smart-connections-cli (r/ObsidianMD, 0.09 upvote ratio): CLI to read SC embeddings from outside Obsidian for Claude Code — community hack to bridge the gap
- Multiple users seeking alternatives: "smart chat has been made paid" — feature gating frustration
- Separate DuckDB-based vault search project: "always wanted a knowledge assistant that respects backlinks and resurfaces ideas I've forgotten" — people building outside SC

### 7. ReasonDB — Tree navigation alternative

- Preserves document structure as hierarchy (headings -> sections -> paragraphs)
- LLM navigates the tree to find answers instead of embedding chunks
- Motivation: "when retrieval fails, debugging why the right chunk didn't surface is a black box"

**Tradeoffs vs QMD:**
- (+) Preserves document structure explicitly
- (+) LLM-navigated = contextually aware retrieval
- (-) Requires LLM calls for every retrieval (latency, cost)
- (-) No keyword/BM25 fallback
- (-) Early stage

## Comparative Matrix

| Dimension | QMD | Smart Connections | txtai | Semantra | Meilisearch | Chroma | Qdrant |
|---|---|---|---|---|---|---|---|
| BM25/full-text | SQLite FTS5 | Separate (unused in ranking) | Sparse (approx) | None | Excellent | None (OSS) | Payload filter |
| Vector search | sqlite-vec | Brute-force cosine | Sentence Transformers | MPNet/MiniLM | Added recently | Core | Core (HNSW) |
| ANN index | sqlite-vec | **None (linear scan)** | Yes | Annoy | Yes | Yes | HNSW |
| Query expansion | Finetuned 1.7B | No | No | No | No | No | No |
| Reranking | Qwen3-reranker | Code exists, **not wired** | No | No | No | No | No |
| Hybrid fusion | RRF with weights | **No** | Yes (basic) | No | Yes | No (OSS) | Dense+sparse |
| Block-level | Chunked (~900 tok) | **Yes (heading-level)** | Chunked | Chunked | No | Chunked | Chunked |
| Breadcrumbs/structure | No | **Yes (folder path)** | No | No | No | No | No |
| Live sync | Config-based | **Yes (file watcher)** | No | No | Yes (API push) | No | No |
| Fully local | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| MCP support | Yes (native) | Via Smart Connect app (paid) | Yes | No | Yes (community) | No | No |
| Obsidian integration | No | **Native** | No | No | No | No | No |
| Mobile | No | **Yes (WASM)** | No | No | No | No | No |
| Complexity | Low (single SQLite) | Low (plugin install) | High (framework) | Low | Low (single binary) | Low-med | High (infra) |
| Scale target | Personal (~10k docs) | Personal (vault) | Medium | Personal | Production | Production | Production |

## Key Insights

### 1. Pure semantic search fails predictably — and Smart Connections is pure semantic
Semantra admits it explicitly. Smart Connections has the same fundamental limitation: if you search "meeting notes from January" and the note says "kokoustiedot tammikuulta", pure cosine similarity with a small English-trained model (bge-micro-v2) will miss it. No amount of embedding quality fixes vocabulary mismatch — that requires query expansion or BM25 fallback.

Smart Connections' statistical cutoff (stop when score gap > std dev) adds another failure mode: with small embedding models, cosine scores cluster in a narrow band. The cutoff can't distinguish "relevant but differently worded" from "irrelevant" when all scores are 0.72-0.78.

### 2. Smart Connections wins on integration and structure, loses on retrieval quality
What SC does that QMD cannot:
- **Block-level embeddings** — paragraph-level connections, not just document-level. A long note with 8 headings creates 8 separate searchable vectors
- **Breadcrumb context** — folder path prepended to embedding input. "Projects/Client-A/meeting-notes" adds structural signal that pure content doesn't capture
- **Live vault sync** — immediate reindex on file change, mobile support
- **Obsidian-native UX** — inline connections sidebar, visual discovery during writing

What QMD does that SC cannot:
- **Hybrid retrieval** — BM25 catches exact terms that embeddings miss
- **Query expansion** — generates synonym/paraphrase variants automatically
- **Reranking** — cross-encoder validates retrieval quality after initial pass
- **Strong signal bypass** — avoids expensive computation when simple keyword match is sufficient

### 3. The unrealized potential in Smart Connections
SC's jsbrains framework already includes cross-encoder reranking models (jina-reranker, bge-reranker) and a separate lexical search path. The code is there but not connected to the main retrieval flow. If these were wired together:
- Lexical + vector → hybrid fusion (even simple score interpolation would help)
- Cross-encoder reranking on top-K results → quality jump

This would not require architectural changes — the adapter infrastructure already exists. The fact that it isn't connected suggests either deliberate simplicity or work-in-progress.

### 4. QMD's query expansion is unique
No other local tool finetunes a model for typed query expansion (lex/vec/hyde). This is the biggest quality differentiator — it addresses vocabulary mismatch, which is the #1 failure mode of both BM25 and vector search.

### 5. Multilingual gap is real
None of these tools address Finnish/English cross-lingual search natively.

Smart Connections' situation: the only bundled multilingual model is jina-v2-base-zh (Chinese/English). Finnish is not covered. The default bge-micro-v2 is English-only, 384d, 512 tokens — Finnish agglutinative words consume tokens faster and produce lower-quality embeddings.

Approaches:
- QMD's query expansion could generate cross-lingual terms (if model supports Finnish)
- Meilisearch has better multi-language tokenization infrastructure
- Multilingual embedding models (e.g. multilingual-e5, intfloat/multilingual-e5-large) help but don't solve vocabulary mismatch
- Most promising: query expansion that generates both Finnish and English terms from either language input
- For Smart Connections: user could manually select a multilingual model via Ollama adapter, but this loses zero-config simplicity

### 6. The solution landscape splits into "solutions" vs "infrastructure"
- Solutions (QMD, Smart Connections, Semantra, Meilisearch): opinionated, ready to use, narrower scope
- Infrastructure (Chroma, Qdrant, txtai): flexible, you build the solution, higher complexity
- For personal knowledge management, a solution wins — the pipeline is the hard part, not the vector math

### 7. Smart Connections' real value is discovery, not search
SC is best understood as a **discovery tool** (serendipitous connections) rather than a **search tool** (find specific content). The sidebar showing "related notes" while writing is the killer feature — it surfaces connections you didn't think to look for. For deliberate search ("find my notes about X"), the lack of keyword matching and query expansion makes it unreliable.

QMD is the opposite: optimized for deliberate search, no passive discovery mode.

## Sources

- [1]: https://github.com/tobi/qmd "QMD — Local search engine for markdown files"
- [2]: https://github.com/neuml/txtai "txtai — All-in-one AI framework"
- [3]: https://github.com/freedmand/semantra "Semantra — Local semantic search"
- [4]: https://github.com/meilisearch/meilisearch "Meilisearch — Lightning-fast search API"
- [5]: https://github.com/chroma-core/chroma "Chroma — AI-native embedding database"
- [6]: https://github.com/qdrant/qdrant "Qdrant — Vector similarity search engine"
- [7]: r/MachineLearning — "file based memory vs embedding search" (1qgwtas)
- [8]: r/MachineLearning — "2025 Year in Review: old methods quietly solving problems" (1pumssb)
- [9]: r/LocalLLaMA — "ReasonDB – LLM navigates a tree instead of vector search" (1rf4pwa)
- [10]: https://github.com/brianpetro/obsidian-smart-connections "Obsidian Smart Connections plugin"
- [11]: https://github.com/brianpetro/jsbrains "jsbrains — Smart Connections framework"
- [12]: r/ObsidianMD — "smart-connections-cli" (1rqoez7) — CLI to read SC embeddings from outside Obsidian
- [13]: r/ObsidianMD — "local vector search for Obsidian vault with DuckDB" (1qwn6mq)
- [14]: r/ObsidianMD — "EzRAG - Semantic Search using Google Gemini" (1ozohwo)
