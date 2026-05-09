"""Prompt-injection defense for untrusted text reaching the LLM.

Covers OWASP LLM01:2025 + Hines spotlighting:
- NFKC normalization (silent)
- Invisible/format-character strip (zero-width, BIDI)
- Chat-template / role / instruction marker strip
- Randomized nonce wrapper to defeat pre-computable boundaries

All marker patterns compiled module-level with re.IGNORECASE.
"""

import re
import secrets
import unicodedata

_INVISIBLE_RE = re.compile("[​‌‍﻿‪‫‬‭‮⁦⁧⁨⁩‎‏؜]")

_MARKER_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"<\|[a-z0-9_]+?\|>", re.IGNORECASE),
    re.compile(r"\[/?(?:INST|SYS|AVAILABLE_TOOLS|TOOL_CALLS|TOOL_RESULTS)\]", re.IGNORECASE),
    re.compile(r"<<\s*/?(?:SYS|SYSTEM|USER|ASSISTANT)\s*>>", re.IGNORECASE),
    re.compile(
        r"</?\s*(?:tool_results|tool_calls|tool_call|assistant|system|user|tool)"
        r"\s*(?:/?>|\s+[^>]*?/?>)",
        re.IGNORECASE,
    ),
    re.compile(r"</?untrusted_[A-Za-z0-9_:-]+>", re.IGNORECASE),
    re.compile(r"\[\s*EXTERNAL_[A-Z0-9_]+_(?:START|END)\s*\]", re.IGNORECASE),
)


def sanitize_external_text(text: str) -> tuple[str, bool]:
    """Strip prompt-injection patterns from untrusted text.

    Order: NFKC normalize (silent) -> strip invisibles -> strip markers ->
    escape leftover delimiter chars.

    Args:
        text: Untrusted input (email subject, body, filename, etc.).

    Returns:
        ``(safe_text, suspicious_patterns_found)``. The boolean is True iff
        the invisible-strip, marker-strip, or delimiter-escape steps changed
        the text. Plain NFKC normalization alone does NOT trigger the flag.
    """
    if not text:
        return text or "", False

    normalized = unicodedata.normalize("NFKC", text)
    suspicious = False

    stripped_invisibles = _INVISIBLE_RE.sub("", normalized)
    if stripped_invisibles != normalized:
        suspicious = True

    current = stripped_invisibles
    for pattern in _MARKER_PATTERNS:
        new = pattern.sub("", current)
        if new != current:
            suspicious = True
            current = new

    escaped = current.replace("<|", "&lt;|").replace("|>", "|&gt;")
    if escaped != current:
        suspicious = True

    return escaped, suspicious


def wrap_untrusted(text: str) -> str:
    """Wrap text in randomized nonce delimiters.

    Format: ``[EXTERNAL_EMAIL_<8hex>_START]\\n{text}\\n[EXTERNAL_EMAIL_<8hex>_END]``.
    Same nonce in START/END within one call; nonces differ across calls
    (8 hex chars from ``secrets.token_hex(4)``).

    Args:
        text: Sanitized untrusted text to wrap.

    Returns:
        Wrapped string with nonce-bracketed delimiters.
    """
    nonce = secrets.token_hex(4)
    return f"[EXTERNAL_EMAIL_{nonce}_START]\n{text}\n[EXTERNAL_EMAIL_{nonce}_END]"
