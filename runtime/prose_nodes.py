# SPDX-License-Identifier: MIT
"""Extract prose from a CommonMark document, so a gate reads sentences and not syntax.

## Why this exists

Running a pattern over raw markdown counts things that are not prose. A first pass over
this workspace reported 106 em-dashes and 53 semicolons across seven files. Both numbers
were wrong. Semicolons in fenced Lean and Python, em-dashes inside link URLs and HTML
attributes, and rule names quoted inside code spans all counted as writing.

Two rules make this worse than ordinary noise. `Em-Dash Addiction` fires on a character
that any code fence may contain for unrelated reasons, and `Compulsive Counting` fires on
the words "three things", which a quoted example sentence in a rule table will contain by
design. A gate that flags a document for quoting the rule it complies with teaches people
to stop running it.

So: parse, walk, and read only the nodes a person reads as prose.

## What is skipped, and why

    fence, code_inline    source, not prose
    html_block, html_inline   markup
    link href             a URL is not a sentence
    image                 alt text is a caption, judged by different rules
    blockquote            usually a quotation from elsewhere; the writer did not write it

Headings and table cells are kept. A templated heading is a real trope, and a table cell
carrying an argument is prose that happens to sit in a grid.

## What it returns

`(text, line)` pairs, one per prose block, with the source line so a finding can point at
somewhere real. Offsets inside a block are not tracked: markdown-it gives line maps per
block token, and a character span inside a paragraph would be a guess dressed as a
measurement.
"""
from __future__ import annotations

from markdown_it import MarkdownIt

#: Inline node types whose content is markup or source rather than writing.
_SKIP_INLINE = {"code_inline", "html_inline", "image"}

#: Block node types skipped whole.
_SKIP_BLOCK = {"fence", "code_block", "html_block"}


def _inline_text(token) -> str:
    """Flatten an inline token to the text a reader sees.

    Link *text* is kept and the href discarded: the words in a link are read, the URL is
    not, and URLs are where a surprising number of em-dashes and semicolons live.
    """
    out: list[str] = []
    depth_skip = 0
    for child in token.children or []:
        if child.type in _SKIP_INLINE:
            continue
        if child.type == "link_open":
            continue          # keep the text, drop the href
        if child.type == "link_close":
            continue
        if child.type.endswith("_open") and child.type[:-5] in _SKIP_INLINE:
            depth_skip += 1
            continue
        if child.type.endswith("_close") and child.type[:-6] in _SKIP_INLINE:
            depth_skip = max(0, depth_skip - 1)
            continue
        if depth_skip:
            continue
        if child.type in ("text", "softbreak"):
            out.append(child.content if child.type == "text" else " ")
    return "".join(out)


def prose_blocks(markdown: str) -> list[tuple[str, int]]:
    """Prose blocks of a CommonMark document, as `(text, line)`."""
    md = MarkdownIt("commonmark")
    tokens = md.parse(markdown)

    blocks: list[tuple[str, int]] = []
    in_quote = 0
    for tok in tokens:
        if tok.type == "blockquote_open":
            in_quote += 1
            continue
        if tok.type == "blockquote_close":
            in_quote = max(0, in_quote - 1)
            continue
        if in_quote:
            continue
        if tok.type in _SKIP_BLOCK:
            continue
        if tok.type == "inline":
            text = _inline_text(tok).strip()
            if text:
                line = tok.map[0] + 1 if tok.map else 0
                blocks.append((text, line))
    return blocks


def prose_text(markdown: str) -> str:
    """All prose in one string, blocks separated by newlines."""
    return "\n".join(t for t, _ in prose_blocks(markdown))


# ---------------------------------------------------------------------------------------
# Controls. A stripper that returns everything is indistinguishable from no stripper at
# all, so each case below must actually lose something.
# ---------------------------------------------------------------------------------------

_SAMPLE = """
# A heading with an em-dash — kept

Prose with a semicolon; kept.

```python
x = 1;  # semicolon in code — dropped
```

Inline `code; with — punctuation` is dropped, surrounding words kept.

[link text](https://example.com/a;b—c) keeps the text, drops the href.

> A quotation; with an em-dash — dropped.

| cell; kept | second — kept |
|---|---|
"""


def _controls() -> None:
    text = prose_text(_SAMPLE)

    assert "kept" in text, "stripped everything"
    assert "x = 1" not in text, "fenced code survived"
    assert "code; with" not in text, "inline code survived"
    assert "example.com" not in text, "link href survived"
    assert "A quotation" not in text, "blockquote survived"
    assert "heading with an em-dash" in text, "headings must be kept"
    assert "cell" in text, "table cells must be kept"

    # The counts the naive approach gets wrong.
    raw_semis, raw_dashes = _SAMPLE.count(";"), _SAMPLE.count("—")
    got_semis, got_dashes = text.count(";"), text.count("—")
    print(f"  semicolons  raw {raw_semis} -> prose {got_semis}")
    print(f"  em-dashes   raw {raw_dashes} -> prose {got_dashes}")
    assert got_semis < raw_semis and got_dashes < raw_dashes, \
        "stripping changed nothing: the scan would keep counting syntax as writing"
    print("  all controls passed")


if __name__ == "__main__":
    print("prose_nodes controls:")
    _controls()
