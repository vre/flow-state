"""Markdown utilities for email body conversion.

Pure functions for:
- Preprocessing markdown for proper rendering
- Converting markdown to HTML
- Converting markdown to pre-markdown plain text (Gmail style)
"""

import re
from typing import Optional

import markdown
from pymdownx import emoji


# Markdown extensions for email formatting
MARKDOWN_EXTENSIONS = [
    'pymdownx.tilde',      # ~~strikethrough~~
    'pymdownx.tasklist',   # - [ ] checkboxes
    'pymdownx.mark',       # ==highlight==
    'pymdownx.betterem',   # smarter bold/italic
    'pymdownx.emoji',      # :emoji: shortcodes
]

# Extension configurations
MARKDOWN_EXTENSION_CONFIGS = {
    'pymdownx.emoji': {
        'emoji_generator': emoji.to_alt  # Unicode output, not CDN images
    }
}


def preprocess_markdown(text: str) -> str:
    """Fix common markdown issues before conversion.

    Ensures blank lines before block elements (lists, code blocks,
    blockquotes, headings) as required by markdown parsers.

    Args:
        text: Raw markdown text

    Returns:
        Preprocessed markdown with proper blank lines
    """
    if not text:
        return text

    lines = text.split('\n')
    result = []
    prev_was_blank = True  # Start as if there was a blank line

    for line in lines:
        stripped = line.strip()
        is_blank = stripped == ''

        # Check if line starts a block element
        is_block_start = (
            stripped.startswith('- ') or
            stripped.startswith('* ') or
            stripped.startswith('+ ') or
            re.match(r'^\d+\. ', stripped) or  # ordered list
            stripped.startswith('> ') or  # blockquote
            stripped.startswith('```') or  # code block
            stripped.startswith('#')  # heading
        )

        # Add blank line before block element if previous line wasn't blank
        if is_block_start and not prev_was_blank:
            result.append('')

        result.append(line)
        prev_was_blank = is_blank

    return '\n'.join(result)


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
    - Checkboxes (unchanged)

    Args:
        text: Markdown text

    Returns:
        Pre-markdown plain text suitable for email text/plain part
    """
    if not text:
        return text

    # **bold** or __bold__ -> *bold*
    text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
    text = re.sub(r'__(.+?)__', r'*\1*', text)

    # [text](url) -> text <url>
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 <\2>', text)

    # ~~strike~~ -> plain (accessibility: screen readers would say "tilde tilde")
    text = re.sub(r'~~(.+?)~~', r'\1', text)

    # ==highlight== -> plain (accessibility: screen readers would say "equals equals")
    text = re.sub(r'==(.+?)==', r'\1', text)

    return text


def convert_body(body: str, format_type: str = "markdown") -> tuple[Optional[str], str]:
    """Convert email body to HTML and plain text.

    Eliminates duplication between create_draft and modify_draft.

    Args:
        body: Raw body text (markdown or plain)
        format_type: "markdown" (default) or "plain"

    Returns:
        Tuple of (html_body, plain_body)
        - html_body is None for plain format
        - plain_body is always returned
    """
    if format_type == "markdown":
        preprocessed = preprocess_markdown(body)
        html_body = markdown.markdown(
            preprocessed,
            extensions=MARKDOWN_EXTENSIONS,
            extension_configs=MARKDOWN_EXTENSION_CONFIGS
        )
        plain_body = markdown_to_plain(body)
        return html_body, plain_body
    else:
        # Plain format: no HTML
        return None, body
