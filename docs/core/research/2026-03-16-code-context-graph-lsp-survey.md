# Code Context Survey: Graph Indexing, AST Tools & LSP for LLM-Assisted Development

Date: 2026-03-16

## Context

Evaluated open-source tools for giving LLMs structural understanding of codebases. Three competing paradigms: (1) AST-based graph databases, (2) tree-sitter skeleton/map approaches, (3) LSP (Language Server Protocol) as semantic oracle. Key question: when does each approach win, and can they be combined?

## Paradigm 1: AST → Graph Database

### 1.1 CodeGraphContext (CodeGraphContext/CodeGraphContext)

- Python, ~2.3k stars, MIT, v0.3.1
- Tree-sitter parsing → graph DB (KuzuDB default, FalkorDB, Neo4j)
- 18 languages (Python, JS, TS, Go, Rust, C, C++, C#, Java, Ruby, PHP, Kotlin, Scala, Swift, Haskell, Dart, Perl, Elixir)
- MCP server (JSON-RPC over stdio)

**Graph schema:** Repository → File → Directory → Module → Function → Class → Variable + relationships (CONTAINS, CALLS, IMPORTS, INHERITS, HAS_PARAMETER, IMPLEMENTS)

**Key tools:** `find_code`, `analyze_code_relationships`, `execute_cypher_query`, `find_dead_code`, `calculate_cyclomatic_complexity`, `watch_directory` (live reindex via watchdog)

**Strengths:**
- Broad language support (18)
- Cypher queries give LLM flexible exploration
- Persistent graph — no reparse per query
- Low storage (MBs)
- Live file watching for incremental updates

**Weaknesses:**
- AST-level only — no type system awareness
- Cannot resolve dynamic dispatch (`obj.save()` → which `save()`?)
- Call resolution is heuristic (import-based), not type-based
- No semantic/vector search component

### 1.2 CodeGraph CLI (al1-nasir/codegraph-cli)

- Python, AST graph (SQLite) + vector embeddings (LanceDB)
- **Only 3 languages** (Python, JS, TS)
- 5 embedding model tiers: Hash (0 deps) → MiniLM (80MB) → BGE-Base (440MB) → Jina-Code (550MB) → Qodo-1.5B (6.2GB)
- CrewAI multi-agent system with 4 specialized agents

**Tradeoffs vs CodeGraphContext:**
- (+) Hybrid: graph traversal + semantic search — solves the entry-point problem
- (+) Impact analysis with multi-hop dependency tracing
- (+) Rich visualization (browser, Mermaid)
- (-) Only 3 languages — severely limits applicability
- (-) Large dependency surface (CrewAI, LanceDB, SQLite, tree-sitter)
- (-) Switching embedding models requires full re-index

### 1.3 GOG — Graph-Oriented Generation (research paper)

- r/MachineLearning post (37 upvotes), white paper + framework
- AST → DAG of all dependencies → deterministic shortest-path traversal
- Claims 70% average token reduction vs vector RAG

**Key insight:** "RAG treats strict software architecture like a probabilistic novel"

**Key criticism (Reddit):** "It's extremely precise after the first step, but the first step is just keyword matching — and real codebases don't always use obvious keywords." Entry-point discovery remains unsolved.

**Counter-argument:** "Graph traversal wins where RAG struggles most: following dependency chains outward from a known entry point. Embeddings lose the structural relationship that A calls B which modifies C — graph traversal preserves it."

## Paradigm 2: Tree-sitter Skeleton/Map

### 2.1 Aider Repo Map

- Built into Aider (AI pair programming tool)
- Tree-sitter → dependency graph → **PageRank-style ranking** → token budget
- 17+ languages
- Sends ranked symbol map as flat text to LLM

**Key design:** Dynamic token budget (default 1k, expands when no files in chat). PageRank prioritizes most-referenced symbols.

**Tradeoffs:**
- (+) Elegant: sends only what matters globally
- (+) Zero external dependencies, battle-tested
- (-) Not query-aware — same map regardless of question
- (-) Not queryable — one-shot context dump, no drill-down
- (-) 1k default token budget risks omitting relevant symbols

### 2.2 Tree-sitter MCP Skeleton Server (r/ClaudeCode, thinkyMiner)

- MCP server exposing `get_file_skeleton("server.py")` → class/function/method signatures
- Agent asks for skeleton first, then reads only relevant sections

**Tradeoffs:**
- (+) Simple and effective for file-level navigation
- (-) No cross-file relationships
- (-) No ranking or prioritization

### 2.3 ast-grep

- Rust, structural code search + rewrite using code-like patterns
- Pattern: `console.log($MSG)` finds all console.log calls
- 18+ languages, very fast (Rust + multi-core)

**Tradeoffs:**
- (+) Intuitive pattern syntax — write code to find code
- (+) Rewrite capability (refactoring)
- (+) Fast — handles tens of thousands of files in seconds
- (-) Single-file scope — no cross-file analysis
- (-) No indexing — re-parses every query
- (-) No ranking or relevance scoring

## Paradigm 3: LSP (Language Server Protocol)

### 3.1 What LSP provides that AST/graph tools cannot

LSP performs **type-aware static analysis** — it understands the type system, not just syntax.

| Capability | LSP | Tree-sitter graph |
|---|---|---|
| Go to definition | Exact, type-aware | Heuristic, import-based |
| Find references | All real call sites | Text-based linking (false positives) |
| Type info / hover | Full type signature, docs | None |
| Diagnostics | Errors, warnings, suggestions | None |
| Rename / refactor | Semantically correct across files | None |
| Dynamic dispatch resolution | Yes (with type info) | No |

**Concrete example of the difference:**

```python
class User:
    def save(self): ...
class Config:
    def save(self): ...

def process(obj: User):
    obj.save()  # which save()?
```

- **Pyright:** knows `obj.save()` → `User.save()` because `obj: User`
- **Tree-sitter graph:** sees `.save()` call → cannot resolve without type info, links to both or guesses from imports

### 3.2 LSP quality by language

| Language | Best LSP | Type system | LSP advantage over graph |
|---|---|---|---|
| **Python** | Pyright | Optional (type hints) | Large if type hints present. Without hints, LSP also guesses |
| **TypeScript** | tsserver | Strong, mandatory | Very large — TS type system too rich for AST-level analysis |
| **JavaScript** | tsserver + JSDoc | Absent | Small — both guess, LSP slightly better via inference |
| **Rust** | rust-analyzer | Strong, algebraic | Very large — traits, generics, lifetimes invisible from AST |
| **Go** | gopls | Static, simple | Moderate — Go's simplicity means AST-level gets closer |
| **Java** | Eclipse JDTLS | Strong, nominal | Large — interfaces, generics, inheritance |
| **C/C++** | clangd | Weak/manual | Moderate — preprocessor, templates are opaque to tree-sitter |

### 3.3 LSP-MCP ecosystem (current state)

Active but fragmented, no dominant standard yet:

| Project | Implementation | Approach |
|---|---|---|
| **mcp-language-server** (isaacphi) | Go | Generic — wraps any LSP |
| **lsp-mcp** (jonrad) | TypeScript | Generic |
| **mcp-lsp-bridge** (rockerBOO) | Multi-lang | 20+ languages supported |
| **cclsp** (ktnyt) | — | Claude Code specific, no IDE required |
| **mcp-gopls** (Yantrio) | Go | gopls-specific |
| **LSP4J-MCP** (stephanj) | Java | Eclipse JDTLS for Claude |
| **JetBrains MCP plugin** | All JB languages | IDE's full semantic index + refactoring |

**Performance:** ~4,300 tokens → ~700 tokens for equivalent code exploration (6x reduction). `findReferences` returns 23 actual call sites vs 500+ grep matches. ~50ms per query.

**JetBrains MCP plugin** (35 upvotes r/ClaudeCode): Exposes IntelliJ's full refactoring — rename across 47 references, 18 files, including interface calls. Build passes, undo works. This is the most capable code-context-for-LLM tool available, but requires JetBrains IDE running.

### 3.4 LSP weaknesses for LLM context

**1. Point query, not batch query.** LSP answers "what is this symbol" one location at a time. LLM must chain: `findReferences("save") → 23 results → getDefinition(result1) → ...`. Each call is a separate tool call. A graph answers in one Cypher query.

**2. Requires running process.** Pyright: ~200-500MB RAM. rust-analyzer: can consume gigabytes, minutes to start. tsserver: reasonable but slow in monorepos. Graph tools: SQLite file, no process.

**3. No "big picture" view.** LSP cannot answer: "show module architecture", "what are the most critical functions", "identify dead code patterns". Graph tools can compute PageRank-style metrics on nodes.

**4. No history.** LSP shows current state only. Graph tools can diff indexes across time.

## Paradigm 4: Trigram Text Search

### Zoekt (sourcegraph/zoekt)

- Originally from Google, maintained by Sourcegraph
- Trigram inverted index — language-agnostic, regex/substring
- ctags integration for symbol-aware ranking, optional BM25

**Tradeoffs:**
- (+) Proven at massive scale (powers Sourcegraph)
- (+) Language-agnostic — works on any text
- (+) Very fast substring/regex
- (-) Text search only — no structural understanding
- (-) Index 3-5x source size
- (-) Overkill for single-repo

## Comparative Matrix

| Dimension | CodeGraphContext | Aider Map | CodeGraph CLI | LSP-MCP | ast-grep | Zoekt |
|---|---|---|---|---|---|---|
| **Core approach** | AST → graph DB | AST → ranked text | AST + vectors | Type-aware analysis | AST pattern match | Trigram index |
| **Type awareness** | No | No | No | **Yes** | No | No |
| **Cross-file** | Yes (Cypher) | Yes (PageRank) | Yes (graph) | Yes (references) | No | Yes (multi-repo) |
| **Query-aware** | Yes | No (global rank) | Yes (RAG) | Yes (point query) | Yes (pattern) | Yes (text query) |
| **Semantic search** | No | No | Yes (vectors) | No | No | No |
| **Batch queries** | Yes (Cypher) | N/A (one-shot) | Yes | No (point queries) | Yes | Yes |
| **Big picture** | Yes (metrics, dead code) | Yes (PageRank) | Yes (impact) | No | No | No |
| **Refactoring** | No | No (via LLM) | No (via agents) | **Yes** (rename etc) | **Yes** (rewrite) | No |
| **Languages** | 18 | 17+ | 3 | Per-LSP (1-many) | 18+ | Any |
| **Runtime cost** | SQLite file | In-memory | SQLite + LanceDB | Running LSP process | On-the-fly parse | Index server |
| **MCP support** | Yes | No (Aider-internal) | No | Yes (multiple) | No | No |
| **Maturity** | Growing (2.3k stars) | Battle-tested | Early | Fragmented | Mature (9k+ stars) | Mature (Sourcegraph) |

## Key Insights

### 1. The entry-point problem is the critical unsolved challenge
All graph/AST tools are excellent at traversal *once you know where to start*. Finding the right starting node requires either keyword matching (brittle) or semantic search (probabilistic). CodeGraph CLI's hybrid approach (graph + vectors) is the only attempt to solve both, but only supports 3 languages.

### 2. LSP and graph tools complement, don't compete
- **LSP** for precision: exact type resolution, reference finding, refactoring
- **Graph** for architecture: module structure, dependency analysis, hot-spot identification
- Optimal: LSP-MCP for precise symbol work + graph for navigation and big-picture context

### 3. LSP-MCP is the highest-value underexploited opportunity
LSP servers already exist for every major language. The bridge to MCP is thin (~50ms overhead). Yet no standard has emerged. JetBrains MCP plugin demonstrates the ceiling — full IDE-quality refactoring for LLMs — but requires IDE running.

### 4. The "120x token reduction" claim needs nuance
Graph MCP servers claim 10-120x token reduction. This is real for structural queries ("who calls X") but misleading for understanding queries ("how does this module work") where the LLM needs to read actual code. The right metric is task completion quality, not token count.

### 5. Reddit community signals
- Strongest enthusiasm: graph-based code indexing MCP servers (69-79 upvotes, 0.9+ ratio)
- Common question in comments: "how does this differ from LSP?" — indicates the community recognizes the overlap
- Practical concern: "I kind of want the LLM to read all the files periodically so it can discover edge cases" — graph/LSP may over-optimize for token efficiency at the cost of serendipitous understanding
- Language support is a gate: "I work in Clojure" — niche languages are underserved by tree-sitter approaches

## Recommendation for Evaluation

**For Python projects with Pyright:**
1. Install an LSP-MCP bridge (mcp-language-server or cclsp) — immediate value from type-aware references
2. Consider CodeGraphContext for architecture-level queries — complements LSP
3. Skip CodeGraph CLI unless you want semantic search over code (and only use Python)

**For TypeScript/JavaScript:**
1. LSP (tsserver) via MCP is highest value — TS type system is too rich for AST-level tools
2. CodeGraphContext adds marginal value for cross-module dependency visualization

**For Rust:**
1. rust-analyzer via MCP is essential — traits, generics, lifetimes are invisible to tree-sitter
2. Graph tools add little value given rust-analyzer's depth

**For Go:**
1. gopls via mcp-gopls — direct integration available
2. CodeGraphContext adds reasonable value — Go's simplicity means AST-level analysis is closer to LSP quality than in other languages

**For multi-language repos:**
1. CodeGraphContext for unified cross-language graph
2. Per-language LSP for precision work
3. Zoekt or ast-grep for fast structural search

## Sources

- [1]: https://github.com/CodeGraphContext/CodeGraphContext "CodeGraphContext — Graph-based code indexing"
- [2]: https://github.com/al1-nasir/codegraph-cli "CodeGraph CLI — AST + vector hybrid"
- [3]: https://github.com/aider-chat/aider "Aider — AI pair programming with repo map"
- [4]: https://github.com/sourcegraph/zoekt "Zoekt — Google's trigram code search"
- [5]: https://github.com/ast-grep/ast-grep "ast-grep — Structural code search"
- [6]: https://github.com/isaacphi/mcp-language-server "mcp-language-server — Generic LSP-MCP bridge"
- [7]: https://github.com/ktnyt/cclsp "cclsp — Claude Code LSP integration"
- [8]: https://github.com/Yantrio/mcp-gopls "mcp-gopls — Go LSP as MCP"
- [9]: r/ClaudeCode — "JetBrains IDE Index MCP Server" (1pbncqd)
- [10]: r/LocalLLaMA — "MCP server that indexes codebases into a knowledge graph" (1rjt4hh)
- [11]: r/MachineLearning — "Graph-Oriented Generation (GOG)" (1rmz1zr)
- [12]: r/ClaudeCode — "tree-sitter based MCP server" (1rota9u)
