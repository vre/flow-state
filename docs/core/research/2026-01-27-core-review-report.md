# Architectural Code Review Report

**Date:** 2026-01-27
**Scope:** `youtube-to-markdown`, `imap-stream-mcp`
**Guidelines:**
- **Primary:** "Pure functions + thin `main()` glue" (Project Standard)
- **Secondary:** "Architecture Patterns with Python" (Separation of Concerns), "Fluent Python" (Idiomatic Code)

## Executive Summary
Both projects generally adhere to the "Pure functions + thin glue" philosophy. Entry points (`scripts/*.py`, `imap_stream_mcp.py`) are minimal, delegating work to library modules. Type hinting and docstrings are consistent.

However, strict architectural boundaries are violated in both projects:
1.  **`youtube-to-markdown`**: Contains a "Low Cohesion" types module (`shared_types.py`) that mixes definitions, implementations, and business logic.
2.  **`imap-stream-mcp`**: Suffers from **Circular Dependencies** between `session.py` and `imap_client.py`, managed via fragile local imports.

---

## Project 1: `youtube-to-markdown`

### Findings
1.  **Anti-Pattern: The "junk drawer" `shared_types.py`**
    - **Observation:** `lib/shared_types.py` contains:
        - Protocols (`FileSystem`, `CommandRunner`) - **Good**
        - Data Classes (`VideoMetadata`) - **Good**
        - *Concrete Implementations* (`RealFileSystem`) - **Bad** (Should be in `infrastructure.py` or `adapters.py`)
        - *Business Logic* (`extract_video_id`, `format_duration`) - **Bad** (Should be in `utils.py` or domain logic)
    - **Impact:** High coupling. Importing a type requires importing the entire implementation logic.

2.  **DRY Violation: `extract_video_id`**
    - **Observation:** The function `extract_video_id` is defined in `lib/shared_types.py` AND `lib/comment_extractor.py`.
    - **Impact:** Bug risk. Fixing regex in one place leaves the other broken.

3.  **Architecture Alignment**
    - **Positive:** `YouTubeDataExtractor` uses manual Dependency Injection (constructor injection of `fs` and `cmd`). This aligns perfectly with "No DI Frameworks" while maintaining testability.

### Recommendations
1.  **Refactor `shared_types.py`**:
    - Move *Protocols* and *Data Classes* to `lib/types.py` (or keep in `shared_types` but clean it).
    - Move *Implementations* (`RealFileSystem`, etc.) to `lib/adapters.py`.
    - Move *Utility Functions* (`extract_video_id`, etc.) to `lib/utils.py`.
2.  **Deduplicate**: Remove the copy of `extract_video_id` from `lib/comment_extractor.py` and import it.

---

## Project 2: `imap-stream-mcp`

### Findings
1.  **Critical: Circular Dependency (`imap_client` ↔ `session`)**
    - **Observation:**
        - `imap_client.py` imports `session` (inside functions) to get connections.
        - `session.py` imports `imap_client` (inside functions) to get credentials and create connections.
    - **Impact:** Fragile code. Refactoring or static analysis tools may fail. Breaks the "Layered Architecture" principle where dependencies should point in one direction.

2.  **Architecture Alignment**
    - **Positive:** `imap_stream_mcp.py` acts as a perfect "Action Dispatcher" (Command Pattern). It parses the request and routes to a specific function, keeping the interface clean (~500 tokens context).
    - **Positive:** `markdown_utils.py` is a model example of "Pure Functions".

### Recommendations
1.  **Extract Configuration/Connection Logic**:
    - Create a new module `config.py` (or `connection.py`) that handles:
        - `get_credentials()`
        - `create_imap_client()` (factory function)
        - `list_accounts()`
    - **New Dependency Graph**:
        - `session.py` imports `config.py` (to create connections).
        - `imap_client.py` imports `session.py` (to get sessions) and `config.py` (for utils).
        - No cycle.

---

## Next Steps

**Option A (Recommended):** I can perform the refactoring for **`youtube-to-markdown`** first, as it is lower risk and improves the codebase immediately.
**Option B:** I can tackle the circular dependency in **`imap-stream-mcp`**.
