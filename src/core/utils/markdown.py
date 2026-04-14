"""Minimal Markdown-to-HTML converter for QTextBrowser rendering.

Handles headings, paragraphs, bold, italic, strikethrough, inline code,
code fences, links, images, unordered/ordered lists, blockquotes, tables,
and horizontal rules.
Produces clean semantic HTML without inline styles
so that QTextDocument.defaultStyleSheet CSS rules work as expected.
"""

import re
from html import escape as html_escape

_CODE_BLOCK_PLACEHOLDER = "\x00CB{index}\x00"
_INLINE_CODE_PLACEHOLDER = "\x01IC{index}\x01"
_CODE_BLOCK_PREFIX = "\x00CB"


# Compiled patterns
# GitHub blob URL to raw URL rewriting
_IMG_GH_BLOB = re.compile(r"!\[(.*?)\]\(https?://github\.com/([^/]+)/([^/]+)/blob/([^)]+)\)")
_IMG_TAG_GH = re.compile(
    r'<img([^>]*?)src=["\']https?://github\.com/([^/]+)/([^/]+)/blob/([^"\']+)(["\'])', re.IGNORECASE
)
_HTML_WRAPPERS = re.compile(r"</?(?:div|span|center|section|article|figure|figcaption|p)[^>]*>", re.IGNORECASE)
_INDENT_INLINE = re.compile(r"^[ \t]+(<(?:img|br|a|hr).*)$", re.IGNORECASE | re.MULTILINE)
_IMG_SIZE_ATTR = re.compile(r'\s*(?:width|height)=["\'][^"\']*["\']', re.IGNORECASE)

# Inline markdown
_MD_IMG = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_BOLD_EM = re.compile(r"\*{3}(.+?)\*{3}")
_MD_BOLD = re.compile(r"\*{2}(.+?)\*{2}")
_MD_BOLD_U = re.compile(r"__(.+?)__")
_MD_EM_STAR = re.compile(r"(?<!\w)\*(.+?)\*(?!\w)")
_MD_EM_UNDER = re.compile(r"(?<!\w)_(.+?)_(?!\w)")
_MD_STRIKE = re.compile(r"~~(.+?)~~")
_MD_AUTOLINK = re.compile(r"<(https?://[^>]+)>")

# Block-level
_CODE_FENCE = re.compile(r"```\w*\n(.*?)```", re.DOTALL)
_CODE_INLINE = re.compile(r"`([^`\n]+)`")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)(?:\s+#+)?$")
_HEADING_FENCE = re.compile(r"^#{1,6}\s")
_HR = re.compile(r"^[-*_](?:\s*[-*_]){2,}\s*$")
_TABLE_SEP = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
_UL_ITEM = re.compile(r"^[-*+]\s")
_UL_ITEM_ALL = re.compile(r"^\s*[-*+]\s")
_UL_STRIP = re.compile(r"^\s*[-*+]\s+")
_OL_ITEM = re.compile(r"^\d+[.)]\s")
_OL_ITEM_ALL = re.compile(r"^\s*\d+[.)]\s")
_OL_STRIP = re.compile(r"^\s*\d+[.)]\s+")
_BQ_START = re.compile(r"^>")
_BQ_PREFIX = re.compile(r"^>\s?")

# GitHub changelog preprocessing
_IMG_TAG = re.compile(r"<img\s[^>]*/?>", re.IGNORECASE)
_IMG_SRC = re.compile(r'<img\s[^>]*src="([^"]+)"', re.IGNORECASE)
_COMMIT_URL = re.compile(r"https://github\.com/[^/\s]+/[^/\s]+/commit/([0-9a-fA-F]{7,40})(?=[^0-9a-fA-F]|$)")
_COMPARE_URL = re.compile(r"(?<![<\[(])(https://github\.com/[^/\s]+/[^/\s]+/compare/[^\s<>()]+)")
_PULL_URL = re.compile(r"(?<![\[(])https://github\.com/[^/\s]+/[^/\s]+/pull/(\d+)")
_PLAIN_HASH = re.compile(r"\b([0-9a-fA-F]{7,40})(?=\s*$)", re.MULTILINE)

# Helpers


def _replace_placeholders(html: str, placeholders: list[str], template: str) -> str:
    for index, value in enumerate(placeholders):
        html = html.replace(template.format(index=index), value)
    return html


def _md_inline(text: str) -> str:
    """Convert inline Markdown (bold, italic, links, images) to HTML."""
    text = _MD_IMG.sub(r'<img src="\2" alt="\1">', text)
    text = _MD_LINK.sub(r'<a href="\2">\1</a>', text)
    text = _MD_BOLD_EM.sub(r"<strong><em>\1</em></strong>", text)
    text = _MD_BOLD.sub(r"<strong>\1</strong>", text)
    text = _MD_BOLD_U.sub(r"<strong>\1</strong>", text)
    text = _MD_EM_STAR.sub(r"<em>\1</em>", text)
    text = _MD_EM_UNDER.sub(r"<em>\1</em>", text)
    text = _MD_STRIKE.sub(r"<del>\1</del>", text)
    text = _MD_AUTOLINK.sub(r'<a href="\1">\1</a>', text)
    return text


def _md_table(lines: list[str]) -> str:
    """Convert Markdown table lines into an HTML <table>."""

    def _cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    headers = _cells(lines[0])
    rows = [_cells(ln) for ln in lines[2:] if ln.strip()]
    html = "<table><thead><tr>" + "".join(f"<th>{_md_inline(h)}</th>" for h in headers) + "</tr></thead>"
    if rows:
        html += (
            "<tbody>"
            + "".join("<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            + "</tbody>"
        )
    return html + "</table>"


# Public API
def preprocess_readme(text: str) -> str:
    """Strip block-level HTML wrappers and rewrite GitHub blob URLs to raw URLs."""
    text = _IMG_GH_BLOB.sub(r"![\1](https://raw.githubusercontent.com/\2/\3/\4)", text)
    text = _IMG_TAG_GH.sub(r"<img\1src=\5https://raw.githubusercontent.com/\2/\3/\4\5", text)
    text = _HTML_WRAPPERS.sub("", text)
    text = _INDENT_INLINE.sub(r"\1", text)
    text = re.sub(
        r"(<img\b)([^>]*?)>",
        lambda m: m.group(1) + _IMG_SIZE_ATTR.sub("", m.group(2)) + ">",
        text,
        flags=re.IGNORECASE,
    )
    return text


def extract_img_srcs(html: str) -> list[str]:
    """Return all ``src`` URLs from ``<img>`` tags in *html*."""
    return _IMG_SRC.findall(html)


def convert_img_tags(text: str) -> str:
    """Convert HTML ``<img>`` tags to markdown ``![alt](url)`` syntax."""

    def _to_md(m: re.Match) -> str:
        tag = m.group(0)
        src_m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', tag)
        if not src_m:
            return tag
        alt_m = re.search(r'alt\s*=\s*["\']([^"\']*)["\']', tag)
        return f"![{alt_m.group(1) if alt_m else ''}]({src_m.group(1)})"

    return _IMG_TAG.sub(_to_md, text)


def strip_commit_links(changelog: str, repo_url: str = "") -> str:
    """Convert raw GitHub commit/PR/compare URLs in *changelog* to markdown links.

    If *repo_url* is given (e.g. ``https://github.com/amnweb/yasb``), bare
    commit hashes at the end of a line are also converted.
    """
    if not changelog:
        return changelog
    text = _COMMIT_URL.sub(lambda m: f"[{m.group(1)[:7]}]({m.group(0)})", changelog)
    text = _PULL_URL.sub(lambda m: f"[#{m.group(1)}]({m.group(0)})", text)
    text = _COMPARE_URL.sub(lambda m: f"<{m.group(1)}>", text)
    if repo_url:
        text = _PLAIN_HASH.sub(lambda m: f"[{m.group(1)[:7]}]({repo_url}/commit/{m.group(1)})", text)
    return text


def md_to_html(src: str) -> str:
    """Minimal Markdown-to-HTML converter for QTextBrowser rendering."""
    src = src.replace("\r\n", "\n")
    code_blocks: list[str] = []

    def _stash_code(m: re.Match) -> str:
        code = html_escape(m.group(1).rstrip("\n"))
        code_blocks.append(f"<pre><code>{code}</code></pre>")
        return _CODE_BLOCK_PLACEHOLDER.format(index=len(code_blocks) - 1)

    src = _CODE_FENCE.sub(_stash_code, src)
    inline_codes: list[str] = []

    def _stash_ic(m: re.Match) -> str:
        inline_codes.append(f"<code>{html_escape(m.group(1))}</code>")
        return _INLINE_CODE_PLACEHOLDER.format(index=len(inline_codes) - 1)

    src = _CODE_INLINE.sub(_stash_ic, src)

    lines = src.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        # Code block placeholder
        if stripped.startswith(_CODE_BLOCK_PREFIX):
            out.append(stripped)
            i += 1
            continue
        # Heading
        hm = _HEADING.match(stripped)
        if hm:
            lvl = len(hm.group(1))
            out.append(f"<h{lvl}>{_md_inline(hm.group(2))}</h{lvl}>")
            i += 1
            continue
        # Horizontal rule
        if _HR.match(stripped):
            out.append("<hr>")
            i += 1
            continue
        # Table
        if "|" in stripped and i + 1 < n and _TABLE_SEP.match(lines[i + 1].strip()):
            tlines: list[str] = []
            while i < n and "|" in lines[i]:
                tlines.append(lines[i])
                i += 1
            out.append(_md_table(tlines))
            continue
        # Blockquote
        if _BQ_START.match(stripped):
            bq: list[str] = []
            while i < n and _BQ_START.match(lines[i].strip()):
                bq.append(_BQ_PREFIX.sub("", lines[i], count=1))
                i += 1
            out.append(f"<blockquote>{md_to_html(chr(10).join(bq))}</blockquote>")
            continue
        # Unordered list
        if _UL_ITEM.match(stripped):
            items: list[str] = []
            while i < n and _UL_ITEM_ALL.match(lines[i]):
                items.append(_UL_STRIP.sub("", lines[i], count=1))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_md_inline(it)}</li>" for it in items) + "</ul>")
            continue
        # Ordered list
        if _OL_ITEM.match(stripped):
            items = []
            while i < n and _OL_ITEM_ALL.match(lines[i]):
                items.append(_OL_STRIP.sub("", lines[i], count=1))
                i += 1
            out.append("<ol>" + "".join(f"<li>{_md_inline(it)}</li>" for it in items) + "</ol>")
            continue
        # Paragraph — collect consecutive non-blank, non-block lines
        para: list[str] = []
        while (
            i < n
            and lines[i].strip()
            and not _HEADING_FENCE.match(lines[i].strip())
            and not _BQ_START.match(lines[i].strip())
            and not _HR.match(lines[i].strip())
            and not (_UL_ITEM.match(lines[i].strip()) and not para)
            and not (_OL_ITEM.match(lines[i].strip()) and not para)
            and not lines[i].strip().startswith(_CODE_BLOCK_PREFIX)
        ):
            para.append(lines[i].strip())
            i += 1
        if para:
            out.append("<p>" + "<br>".join(_md_inline(p) for p in para) + "</p>")

    html = "\n".join(out)
    html = _replace_placeholders(html, code_blocks, _CODE_BLOCK_PLACEHOLDER)
    return _replace_placeholders(html, inline_codes, _INLINE_CODE_PLACEHOLDER)
