"""Prompt-injection defense for untrusted text reaching the LLM.

Canonical source — copies live in chrome-control/, firefox-control/,
youtube-to-markdown/, and wiki research scripts.
Keep in sync: copy this file, do not import across plugin boundaries.

Covers OWASP LLM01:2025 + Hines spotlighting:
- NFKC normalization (silent)
- Unicode Format-category (Cf) strip — zero-width, BIDI, tag chars
- Chat-template / role / instruction marker strip (iterative)
- Delimiter escape for leftover <| |> sequences
- Randomized nonce wrapper to defeat pre-computable boundaries
"""

import re
import secrets
import unicodedata

_MARKER_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"<\|[a-z0-9_]+?\|>", re.IGNORECASE),
    re.compile(
        r"\[/?(?:INST|SYS|AVAILABLE_TOOLS|TOOL_CALLS|TOOL_RESULTS)\]",
        re.IGNORECASE,
    ),
    re.compile(r"<<\s*/?(?:SYS|SYSTEM|USER|ASSISTANT)\s*>>", re.IGNORECASE),
    re.compile(r"</?(?:start|end)_of_turn>", re.IGNORECASE),
    re.compile(
        r"</?\s*(?:tool_results|tool_calls|tool_call|assistant|system|user|tool)"
        r"\s*(?:/?>|\s+[^>]*?/?>)",
        re.IGNORECASE,
    ),
    re.compile(r"</?untrusted_[A-Za-z0-9_:-]+>", re.IGNORECASE),
    re.compile(r"\[\s*EXTERNAL_[A-Z0-9_]+_(?:START|END)\s*\]", re.IGNORECASE),
    re.compile(r"\{\{UNTRUSTED CONTENT — [^}]*\}\}"),
)


def _strip_cf(text: str) -> str:
    """Strip all Unicode Format-category (Cf) characters."""
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def _strip_markers(text: str) -> tuple[str, bool]:
    """Iteratively strip marker patterns until stable."""
    found = False
    while True:
        new = text
        for pat in _MARKER_PATTERNS:
            new = pat.sub("", new)
        if new == text:
            return text, found
        found = True
        text = new


def sanitize_external_text(text: str) -> tuple[str, bool]:
    """Strip prompt-injection patterns from untrusted text.

    Order: NFKC normalize (silent) -> strip Cf chars -> iterative marker
    strip -> escape leftover delimiter chars.

    Returns:
        ``(safe_text, suspicious_patterns_found)``. The boolean is True iff
        the Cf-strip, marker-strip, or delimiter-escape steps changed
        the text. Plain NFKC normalization alone does NOT trigger the flag.
    """
    if not text:
        return text or "", False

    normalized = unicodedata.normalize("NFKC", text)
    suspicious = False

    stripped_cf = _strip_cf(normalized)
    if stripped_cf != normalized:
        suspicious = True

    current, markers_found = _strip_markers(stripped_cf)
    if markers_found:
        suspicious = True

    escaped = current.replace("<|", "&lt;|").replace("|>", "|&gt;")
    if escaped != current:
        suspicious = True

    return escaped, suspicious


_KIND_RE = re.compile(r"[A-Za-z0-9_]+$")


def wrap_untrusted(text: str, kind: str = "EMAIL") -> str:
    """Wrap text in randomized nonce delimiters.

    Format: ``[EXTERNAL_{KIND}_{8hex}_START]\\n{text}\\n[EXTERNAL_{KIND}_{8hex}_END]``.
    """
    if not _KIND_RE.fullmatch(kind):
        raise ValueError(f"kind must be alphanumeric/underscore, got: {kind!r}")
    nonce = secrets.token_hex(4)
    tag = kind.upper()
    return f"[EXTERNAL_{tag}_{nonce}_START]\n{text}\n[EXTERNAL_{tag}_{nonce}_END]"


def sanitize_result(obj):
    """Recursively sanitize all string keys and values in a JSON-serializable structure."""
    if isinstance(obj, str):
        safe, _ = sanitize_external_text(obj)
        return safe
    if isinstance(obj, dict):
        return {sanitize_result(k): sanitize_result(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_result(item) for item in obj]
    return obj
