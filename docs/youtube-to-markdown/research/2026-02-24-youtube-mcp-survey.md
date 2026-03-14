# YouTube MCP Servers & Claude Skills Survey

**Date:** 2026-02-24
**Scope:** GitHub + Reddit, 20+ projects surveyed

---

## Executive Summary

The YouTube MCP ecosystem is fragmented across 20+ implementations. Most are transcript-only extractors with 1 tool. A few comprehensive servers exist with 8-40 tools covering the full YouTube Data API surface. Token efficiency is rarely addressed -- only 2-3 projects explicitly optimize for it. No server uses single-tool routing (action parameter pattern).

**Key finding:** Clear gap between "transcript-only" servers (majority) and "kitchen-sink" servers (pauling-ai with 40 tools, space-cadet with 14). No server balances breadth with token efficiency well, except kirbah/mcp-youtube which explicitly targets this but has limited adoption (12 stars).

---

## Tier 1: High-Star / High-Activity Projects

### 1. anaisbetts/mcp-youtube (494 stars)
- **URL:** https://github.com/anaisbetts/mcp-youtube
- **What:** Subtitle extraction via yt-dlp, feeds to Claude for summarization
- **Tools:** 1 (subtitle download)
- **Language:** JavaScript/TypeScript
- **Last updated:** March 2025 (v0.6.0)
- **Token efficiency:** None
- **Differentiator:** Most popular. Uses yt-dlp (no API key). Simple install via mcp-installer
- **Limitations:** Single capability, no metadata, no search, no comments

### 2. kimtaeyoon83/mcp-server-youtube-transcript (477 stars)
- **URL:** https://github.com/kimtaeyoon83/mcp-server-youtube-transcript
- **What:** Transcript extraction with ad filtering
- **Tools:** 1 (`get_transcript`)
- **Language:** TypeScript
- **Token efficiency:** None
- **Differentiator:** Built-in sponsorship/ad segment filtering, multi-format URL support (Shorts, video IDs), language fallback. Direct Innertube API (no API key)

### 3. ZubeidHendricks/youtube-mcp-server (450 stars)
- **URL:** https://github.com/ZubeidHendricks/youtube-mcp-server
- **What:** Comprehensive YouTube Data API integration
- **Tools:** ~12+ across 4 domains (videos, transcripts, channels, playlists)
- **Language:** TypeScript
- **Token efficiency:** None
- **Differentiator:** Broad feature set -- video details, search, channel stats, playlist operations, timestamped captions, multi-language transcripts

### 4. jkawamoto/mcp-youtube-transcript (311 stars)
- **URL:** https://github.com/jkawamoto/mcp-youtube-transcript
- **What:** Transcript retrieval with pagination for long videos
- **Tools:** 3 (`get_transcript`, `get_timed_transcript`, `get_video_info`)
- **Language:** Python (with Docker support)
- **Last updated:** February 2026 (v0.5.10) -- actively maintained
- **Token efficiency:** YES -- splits transcripts >50,000 chars with cursor-based pagination. Configurable `--response-limit`. Proxy support
- **Differentiator:** Best pagination story. Proxy rotation. Docker-ready

---

## Tier 2: Feature-Rich / Specialized Projects

### 5. op7418/Youtube-clipper-skill (1,400 stars, Claude Code Skill)
- **URL:** https://github.com/op7418/Youtube-clipper-skill
- **What:** AI-powered video clipper -- download, chapter, clip, translate subtitles, burn-in
- **Language:** Python + Shell
- **Token efficiency:** Claims "95% reduction in API calls" for batch subtitle translation
- **Differentiator:** Most starred YouTube project overall. Full video processing pipeline. Chinese-market focused. Requires FFmpeg + yt-dlp

### 6. pauling-ai/youtube-mcp-server (4 stars)
- **URL:** https://github.com/pauling-ai/youtube-mcp-server
- **What:** Full YouTube management -- Data API v3 + Analytics API + Reporting API
- **Tools:** 40 (!)
- **Language:** Python (FastMCP)
- **Last updated:** February 2026
- **Token efficiency:** Quota-aware (tracks API units)
- **Differentiator:** Most comprehensive. Video upload/publish, playlist CRUD, comment posting, revenue analytics. 40 tools = massive schema overhead

### 7. kirbah/mcp-youtube (12 stars)
- **URL:** https://github.com/kirbah/mcp-youtube
- **What:** Token-optimized YouTube Data API server
- **Tools:** 8
- **Language:** TypeScript
- **Last updated:** February 2026 (v0.3.6)
- **Token efficiency:** YES -- explicit design goal. Lean response schemas, configurable result limiting
- **Differentiator:** Only project explicitly designed for token efficiency. Comment retrieval with reply depth control

### 8. coyaSONG/youtube-mcp-server (13 stars)
- **URL:** https://github.com/coyaSONG/youtube-mcp-server
- **What:** Advanced YouTube data with AI analysis features
- **Tools:** 14+
- **Language:** TypeScript (HTTP transport)
- **Differentiator:** AI-powered summaries, key moment extraction, segmented transcripts, video comparison

### 9. kyong0612/youtube-mcp (3 stars)
- **URL:** https://github.com/kyong0612/youtube-mcp
- **What:** Transcript tools with caching and translation
- **Tools:** 5
- **Language:** Go 1.24
- **Token efficiency:** Redis + in-memory caching, rate limiting
- **Differentiator:** Only Go implementation. Multiple output formats (plain, SRT, VTT). Batch processing. Proxy rotation

### 10. glonorce/youtube_mcp (1 star)
- **URL:** https://github.com/glonorce/youtube_mcp
- **Tools:** 7
- **Language:** Python 3.13+
- **Last updated:** February 2026
- **Token efficiency:** Quota-aware budgeting. Opt-in expensive operations
- **Differentiator:** Best safety design. Public data only by default. Shorts/live excluded. Endpoint allowlist

---

## Tier 3: Focused / Simple

| Project | Stars | Tools | Differentiator |
|---|---|---|---|
| cottongeeks/ytt-mcp | 72 | 1 | Raycast integration |
| mybuddymichael/youtube-transcript-mcp | 60 | 1 | Bun + Node.js |
| adhikasp/mcp-youtube | 47 | 1 | Early mover |
| sinco-lab/mcp-youtube-transcript | 30 | 1 | Paragraph vs continuous formatting |
| hancengiz/youtube-transcript-mcp | 3 | 2 | Best token economics docs ("60min = ~19k tokens") |
| bzurkowski/mcp-youtube | 3 | 8 | translate_video_transcript |
| labeveryday/youtube-mcp-server-enhanced | 5 | 15+ | yt-dlp, concurrent batch, TTL caching |
| Koomook/claude-skill-youtube-kr-subtitle | 20 | skill | Korean context-aware subtitle translation |

---

## Capability Matrix

| Capability | anaisbetts | kimtaeyoon | ZubeidH. | jkawamoto | kirbah | pauling | kyong0612 | bzurkowski |
|---|---|---|---|---|---|---|---|---|
| Transcript | x | x | x | x | x | x | x | x |
| Language selection | x | x | x | x | x | x | x | x |
| Pagination | | | | x | | | | |
| Video metadata | | | x | x | x | x | | x |
| Video search | | | x | | x | x | | x |
| Channel browse | | | x | | x | x | | x |
| Playlist handling | | | x | | | x | | x |
| Comments | | | | | x | x | | x |
| Translation | | | | | | | x | x |
| Ad filtering | | x | | | | | | |
| Token optimization | | | | x | x | | | |

---

## Design Patterns

### Tool Count Distribution
- **1 tool:** 8 projects (majority)
- **2-3 tools:** 5 projects
- **5-8 tools:** 4 projects
- **12-15 tools:** 5 projects
- **40 tools:** 1 project (pauling-ai)

### Transcript Source Strategy
- **yt-dlp:** anaisbetts, labeveryday -- no API key, heavy dependency
- **youtube-transcript-api (Python):** adhikasp, jkawamoto, space-cadet
- **Innertube API direct:** kimtaeyoon83, hancengiz -- no deps, no API key, lightweight
- **YouTube Data API v3:** ZubeidHendricks, kirbah, pauling -- requires API key

### What Nobody Does
- Single-tool action routing (0 projects)
- Progressive disclosure / help action
- Response compression for token savings
- Comment cross-analysis against content
- Modular parallel pipeline
