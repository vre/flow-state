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
    "fenced_code",  # ``` blocks
    "tables",  # pipe tables
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

# Fence delimiters, at column zero only: python-markdown's fenced_code does not
# recognise an indented fence, and a 4-space one becomes an indented code block
# containing literal backticks. The opener may carry any trailing text - "c#",
# "foo.bar" and "{.python #ex}" are all valid language tags - while the closer
# must be bare.
_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE = re.compile(r"^(`{3,}|~{3,})[ \t]*$")

# A table header row and the separator beneath it. The extension accepts both
# "| a | b |" and "a | b", and rejects a separator with no pipe, so ":---:" on
# its own must not be mistaken for one.
_TABLE_ROW = re.compile(r"^[^\n]*\|[^\n]*$")
_TABLE_SEP = re.compile(r"^[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)+\|?[ \t]*$|^[ \t]*\|[ \t|:-]*\|[ \t]*$")

# Blockquote marker with the 0-3 leading spaces markdown allows. Four spaces is
# indented code, not a quote.
_QUOTE_LINE = re.compile(r"^ {0,3}>")


def _line_records(text: str) -> list[tuple[str, str]]:
    """Split into (content, separator) pairs, preserving each line's exact ending.

    Both callers use this, so they cannot disagree about where lines end: one of
    them previously split on "\n" alone and would leave a stray "\r" attached.
    """
    parts = _LINE_SPLIT.split(text)
    records = []
    for i in range(0, len(parts), 2):
        records.append((parts[i], parts[i + 1] if i + 1 < len(parts) else ""))
    return records


def _fenced_flags(records: list[tuple[str, str]]) -> list[bool]:
    """Mark the lines of every CLOSED fence region, left to right.

    Reproduces the extension rather than approximating it: the closer must repeat
    the opener's delimiter exactly, anything else - including a delimiter of the
    other character - is content, and an opener with no closer is not a fence.
    """
    flags = [False] * len(records)
    index = 0
    while index < len(records):
        opener = _FENCE_OPEN.match(records[index][0])
        if opener:
            delimiter = opener.group(1)
            for close_at in range(index + 1, len(records)):
                closer = _FENCE_CLOSE.match(records[close_at][0])
                if closer and closer.group(1) == delimiter:
                    for line in range(index, close_at + 1):
                        flags[line] = True
                    index = close_at
                    break
        index += 1
    return flags


# URL pattern for autolinking (no email - avoids obfuscation issues)
# Negative lookbehind: skip URLs already in href="..."
URL_PATTERN = re.compile(r'(?<!href=")(https?://[^\s<>"]+)')

# Regions autolinking must not enter. <a> is included because the visible text of
# an existing anchor would otherwise be matched and nested inside a second one.
_NO_AUTOLINK = re.compile(r"(<pre\b.*?</pre>|<code\b.*?</code>|<a\b.*?</a>)", re.DOTALL)


def autolink_urls(html: str) -> str:
    """Convert bare URLs to links, leaving code and existing anchors alone.

    The guard lives here rather than in the caller so a future caller cannot
    forget it. This is NOT a general HTML parser: it assumes balanced, lowercase
    markup with no literal "</code>" inside an attribute, which holds because the
    only input is what python-markdown produced one line earlier in convert_body.
    """

    def replace_url(match):
        url = match.group(1)
        return f'<a href="{url}">{url}</a>'

    return "".join(
        segment if _NO_AUTOLINK.fullmatch(segment) else URL_PATTERN.sub(replace_url, segment) for segment in _NO_AUTOLINK.split(html)
    )


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

    records = _line_records(text)
    fenced = _fenced_flags(records)
    result = []
    prev_was_blank = True  # Start as if there was a blank line
    prev_was_list_item = False
    prev_was_quote = False

    for index, (line, separator) in enumerate(records):
        if fenced[index]:
            # Verbatim. Inserting a blank line here put it inside the code block.
            # The opening delimiter still needs separating from preceding text,
            # like any other block start.
            if (index == 0 or not fenced[index - 1]) and not prev_was_blank:
                result.append("\n")
            result.append(line + separator)
            prev_was_blank = False
            prev_was_list_item = False
            prev_was_quote = False
            continue

        stripped = line.strip()
        is_blank = stripped == ""

        is_list_item = (
            stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("+ ") or bool(re.match(r"^\d+\. ", stripped))
        )
        is_quote = bool(_QUOTE_LINE.match(line))
        is_heading = stripped.startswith("#")
        # An unpaired ``` is ordinary text, not a block start: it is never
        # flagged as fenced, so it never reaches the branch above.
        is_table_start = (
            bool(_TABLE_ROW.match(line))
            and index + 1 < len(records)
            and not fenced[index + 1]
            and bool(_TABLE_SEP.match(records[index + 1][0]))
        )

        needs_blank = False
        if (is_heading or is_table_start) and not prev_was_blank:
            needs_blank = True
        elif is_list_item and not prev_was_blank and not prev_was_list_item:
            needs_blank = True
        elif is_quote and not prev_was_blank and not prev_was_quote:
            # Only at the START of a quote: a blank between consecutive "> " lines
            # split one quoted paragraph into two and killed the line break.
            needs_blank = True

        if needs_blank:
            result.append("\n")

        result.append(line + separator)
        prev_was_blank = is_blank
        prev_was_list_item = is_list_item
        prev_was_quote = is_quote

    return "".join(result)


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
    - Fenced code blocks: the substitutions rewrote the author's code in the
      plain alternative.

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

        records = _line_records(text)
        fenced = _fenced_flags(records)
        saved: dict[str, str] = {}
        pieces = []
        for index, (line, separator) in enumerate(records):
            # Fenced regions and marker-run lines are protected by the same
            # scheme. Marker detection runs only outside fences, so the spans
            # cannot overlap and a token can never end up nested inside another.
            if fenced[index] or _MARKER_RUN_LINE.match(line):
                token = f"{base}{len(saved)}\x00"
                saved[token] = line
                pieces.append(token + separator)
            else:
                pieces.append(line + separator)

        converted = _apply_plain_substitutions("".join(pieces))

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
