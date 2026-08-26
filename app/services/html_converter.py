"""Deterministic Markdown-to-HTML conversion for Blogger-safe content.

Converts a small, well-defined Markdown subset into clean HTML suitable for
Blogger posts. Pure Python with no external dependencies, no network access,
and no LLM calls — fully deterministic.

Supported subset
----------------
- Headings ``#``/``##``/``###`` -> ``<h2>``/``<h3>`` (demoted by one level so
  the post body never competes with Blogger's own ``<h1>`` post title).
- Paragraphs separated by blank lines -> ``<p>``.
- Bullet lists (``-``, ``*``, ``+``) -> ``<ul><li>``.
- Numbered lists (``1.``, ``2)``, ...) -> ``<ol><li>``.
- Bold ``**x**`` / ``__x__`` -> ``<strong>``.
- Italic ``*x*`` / ``_x_`` -> ``<em>``.
- Horizontal rules (``---``, ``***``, ``___``) -> ``<hr>``.
- Hard line breaks within a paragraph are preserved as ``<br>``.
"""

import re
from html import escape

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_NUMBERED_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
_HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")


_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)\)")


def _inline(text: str) -> str:
    """Escape raw HTML, then apply inline Markdown (links, bold, italic).

    Bold is processed before italic so ``**x**`` is not partially consumed as
    ``*`` emphasis. ``__``/``_`` follow the same ordering. Markdown links are
    stashed first so their labels/URLs survive escaping.
    """
    links: list[tuple[str, str]] = []

    def _stash_link(match: re.Match) -> str:
        label = escape(match.group(1).strip())
        href = match.group(2).strip()
        links.append((label, href))
        return f"\x00{len(links) - 1}\x00"

    text = _LINK_RE.sub(_stash_link, text)
    text = escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    for idx, (label, href) in enumerate(links):
        text = text.replace(
            f"\x00{idx}\x00",
            f'<a href="{escape(href, quote=True)}">{label}</a>',
        )
    return text


def _heading_tag(level: int) -> str:
    """Demote Markdown heading levels into Blogger-safe h2/h3 tags."""
    return "h2" if level <= 1 else "h3"


def markdown_to_blogger_html(text: str) -> str:
    """Convert Markdown text to Blogger-safe HTML deterministically."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    blocks: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        stripped = lines[i].strip()

        # Blank line -> block separator.
        if not stripped:
            i += 1
            continue

        # Heading.
        heading = _HEADING_RE.match(stripped)
        if heading:
            tag = _heading_tag(len(heading.group(1)))
            blocks.append(f"<{tag}>{_inline(heading.group(2).strip())}</{tag}>")
            i += 1
            continue

        # Horizontal rule.
        if _HR_RE.match(stripped):
            blocks.append("<hr>")
            i += 1
            continue

        # Standalone image: ![alt](url) -> <img src="..." alt="..."/>.
        image = _IMAGE_RE.match(stripped)
        if image:
            alt = image.group(1).strip()
            src = image.group(2).strip()
            blocks.append(
                f'<img src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}"/>'
            )
            i += 1
            continue

        # Collect a contiguous run of non-blank lines as one block.
        block_lines: list[str] = []
        while i < n and lines[i].strip():
            block_lines.append(lines[i].strip())
            i += 1

        # Bullet list.
        if block_lines and all(_BULLET_RE.match(ln) for ln in block_lines):
            items = [
                f"<li>{_inline(_BULLET_RE.match(ln).group(1).strip())}</li>"
                for ln in block_lines
            ]
            blocks.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Numbered list.
        if block_lines and all(_NUMBERED_RE.match(ln) for ln in block_lines):
            items = [
                f"<li>{_inline(_NUMBERED_RE.match(ln).group(1).strip())}</li>"
                for ln in block_lines
            ]
            blocks.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Paragraph; preserve hard line breaks as <br>.
        inner = "<br>".join(_inline(ln) for ln in block_lines)
        blocks.append(f"<p>{inner}</p>")

    return "\n".join(blocks)


def insert_image_after_intro(content: str, image_url: str, alt: str) -> str:
    """Insert a Markdown image just after the first paragraph (the intro).

    The image becomes its own Markdown block, so the existing Markdown-to-HTML
    converter turns it into a standalone ``<img>`` placed after the article's
    introduction rather than at the bottom.
    """
    if not content or not content.strip():
        return content

    image_md = f"![{alt}]({image_url})"
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    saw_paragraph = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if saw_paragraph:
                # Insert after the blank line that ends the first paragraph.
                return "\n".join(lines[: idx + 1] + [image_md, ""] + lines[idx + 1 :])
            continue
        if _HEADING_RE.match(stripped) or _HR_RE.match(stripped) or _IMAGE_RE.match(stripped):
            continue
        saw_paragraph = True

    # No trailing blank line after the first paragraph; append near the top.
    return "\n".join(lines + ["", image_md, ""])
