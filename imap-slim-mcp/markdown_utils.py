"""Markdown utilities for email body conversion.

Pure functions for:
- Preprocessing markdown for proper rendering
- Converting markdown to HTML
- Converting markdown to pre-markdown plain text (Gmail style)
"""

import re
from typing import Literal

import markdown
from pymdownx import emoji

# Markdown extensions for email formatting
MARKDOWN_EXTENSIONS = [
    "pymdownx.tilde",  # ~~strikethrough~~
    "pymdownx.tasklist",  # - [ ] checkboxes
    "pymdownx.mark",  # ==highlight==
    "pymdownx.betterem",  # smarter bold/italic
    "pymdownx.emoji",  # :emoji: shortcodes
    "nl2br",  # a newline inside a paragraph becomes <br>, as every mail composer does
]

# Extension configurations
MARKDOWN_EXTENSION_CONFIGS = {
    "pymdownx.emoji": {
        "emoji_generator": emoji.to_alt  # Unicode output, not CDN images
    }
}

VALID_FORMATS = {"markdown", "plain"}

# A line that is nothing but a run of one marker character, optionally indented
# and optionally quoted: an ASCII rule or a setext underline, not emphasis.
_MARKER_RUN_LINE = re.compile(r"^[ \t]*(?:>[ \t]*)*([*_=~])\1{2,}[ \t]*$")

# Keeps every separator as its own element so CRLF, LF and bare CR all survive.
# splitlines() is not used: it also recognises other Unicode line breaks and
# would rewrite them.
_LINE_SPLIT = re.compile(r"(\r\n|\n|\r)")

# URL pattern for autolinking (no email - avoids obfuscation issues)
# Negative lookbehind: skip URLs already in href="..."
URL_PATTERN = re.compile(r'(?<!href=")(https?://[^\s<>"]+)')


def autolink_urls(html: str) -> str:
    """Convert bare URLs to links in HTML, skip already linked URLs."""

    def replace_url(match):
        url = match.group(1)
        return f'<a href="{url}">{url}</a>'

    return URL_PATTERN.sub(replace_url, html)


def preprocess_markdown(text: str) -> str:
    """Fix common markdown issues before conversion.

    Ensures blank lines before block elements (lists, code blocks,
    blockquotes, headings) as required by markdown parsers.
    Only adds blank line at START of a list, not between items.

    Args:
        text: Raw markdown text

    Returns:
        Preprocessed markdown with proper blank lines
    """
    if not text:
        return text

    lines = text.split("\n")
    result = []
    prev_was_blank = True  # Start as if there was a blank line
    prev_was_list_item = False

    for line in lines:
        stripped = line.strip()
        is_blank = stripped == ""

        # Check if line is a list item
        is_list_item = (
            stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("+ ") or bool(re.match(r"^\d+\. ", stripped))
        )

        # Check if line starts other block elements (not list items)
        is_other_block = (
            stripped.startswith("> ")  # blockquote
            or stripped.startswith("```")  # code block
            or stripped.startswith("#")  # heading
        )

        # Add blank line before block element if previous line wasn't blank
        # For list items: only at list START (not between items)
        needs_blank = False
        if is_other_block and not prev_was_blank or is_list_item and not prev_was_blank and not prev_was_list_item:
            needs_blank = True

        if needs_blank:
            result.append("")

        result.append(line)
        prev_was_blank = is_blank
        prev_was_list_item = is_list_item

    return "\n".join(result)


def _apply_plain_substitutions(text: str) -> str:
    """The five conversions, over the whole body and in this order.

    Whole-body matters: the link expression spans newlines because both negated
    classes match them, so per-line processing would silently drop multi-line links.
    """
    # **bold** or __bold__ -> *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)

    # [text](url) -> text <url>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 <\2>", text)

    # ~~strike~~ -> plain (accessibility: screen readers would say "tilde tilde")
    text = re.sub(r"~~(.+?)~~", r"\1", text)

    # ==highlight== -> plain (accessibility: screen readers would say "equals equals")
    text = re.sub(r"==(.+?)==", r"\1", text)

    return text


def markdown_to_plain(text: str) -> str:
    """Convert markdown to pre-markdown plain text (Gmail style).

    Converts:
    - **bold** or __bold__ -> *bold*
    - [text](url) -> text <url>
    - ~~strike~~ -> text (markers removed for screen reader accessibility)
    - ==highlight== -> text (markers removed for screen reader accessibility)

    Preserves:
    - *italic* (unchanged)
    - Lists, headings, blockquotes (unchanged)
    - A line that is only a run of markers: an ASCII rule such as "=====" is not
      emphasis, and the unguarded expressions turned it into "=".

    Args:
        text: Markdown text

    Returns:
        Pre-markdown plain text suitable for email text/plain part
    """
    if not text:
        return text

    nonce = "0"
    while True:
        base = f"\x00{nonce}\x00"
        if base in text:
            nonce += "0"
            continue

        parts = _LINE_SPLIT.split(text)
        saved: dict[str, str] = {}
        for index in range(0, len(parts), 2):
            if _MARKER_RUN_LINE.match(parts[index]):
                token = f"{base}{len(saved)}\x00"
                saved[token] = parts[index]
                parts[index] = token

        converted = _apply_plain_substitutions("".join(parts))

        # The base being absent from the input is not enough: a substitution can
        # synthesise a token. "\x00==0==\x00==0==\x00" becomes "\x000\x000\x00",
        # which is token 0, and restoring would rewrite that user text.
        if any(converted.count(token) != 1 for token in saved):
            nonce += "0"
            continue

        for token, original in saved.items():
            converted = converted.replace(token, original)
        return converted


def convert_body(body: str, format_type: Literal["markdown", "plain"]) -> tuple[str | None, str]:
    """Convert email body to HTML and plain text.

    Eliminates duplication between create_draft and modify_draft. There is
    deliberately no default: a silent default is what let a caller send markdown
    believing it was sending plain text.

    Args:
        body: Raw body text
        format_type: "markdown" renders HTML plus a plain alternative; "plain"
            sends the body verbatim with no HTML part.

    Returns:
        Tuple of (html_body, plain_body)
        - html_body is None for plain format
        - plain_body is always returned
    """
    if format_type not in VALID_FORMATS:
        raise ValueError(
            f"Unknown format '{format_type}'. Use 'markdown' (renders HTML plus a plain alternative) "
            "or 'plain' (sent verbatim, no HTML). Both are explicit; there is no default."
        )

    if format_type == "markdown":
        preprocessed = preprocess_markdown(body)
        html_body = markdown.markdown(preprocessed, extensions=MARKDOWN_EXTENSIONS, extension_configs=MARKDOWN_EXTENSION_CONFIGS)
        html_body = autolink_urls(html_body)
        plain_body = markdown_to_plain(body)
        return html_body, plain_body
    else:
        # Plain format: no HTML
        return None, body
