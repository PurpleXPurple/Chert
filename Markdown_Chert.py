"""
Markdown_Chert.py — Markdown parser, HTML renderer, syntax highlighter.

KaTeX math + Mermaid diagrams + ctypes FastBuffer + LRU render cache.
"""

import html
import re
import sys
import ctypes
import ctypes.util
import threading
from functools import lru_cache
from pathlib import Path

from Chert_Managers import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat,
    WIKILINK_RE, TAG_RE, HEADING_RE, FRONTMATTER_RE,
)


# ══════════════════════════════════════════════════════════════════════════
# ctypes memory layer
# ══════════════════════════════════════════════════════════════════════════

_libc = None
for _name in ("msvcrt", "libc.so.6", "libc.so", "libc.dylib", "c"):
    try:
        _libc = ctypes.CDLL(ctypes.util.find_library(_name) or _name)
        if _libc:
            break
    except OSError:
        continue

if _libc is not None:
    _libc.memmove.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    _libc.memmove.restype = ctypes.c_void_p
    _memmove = _libc.memmove
else:
    _memmove = None


class FastBuffer:
    __slots__ = ("_buf", "_cap", "_len", "_owns")

    DEFAULT_CAP = 1 << 16

    def __init__(self, capacity=DEFAULT_CAP):
        self._cap = int(capacity)
        self._len = 0
        if _memmove is not None:
            self._buf = (ctypes.c_char * self._cap)()
            self._owns = True
        else:
            self._buf = bytearray(self._cap)
            self._owns = False

    def reset(self):
        self._len = 0

    def _grow(self, needed):
        new_cap = max(self._cap * 2, needed)
        if _memmove is not None:
            new_buf = (ctypes.c_char * new_cap)()
            _memmove(new_buf, self._buf, self._len)
            self._buf = new_buf
        else:
            self._buf.extend(b"\x00" * (new_cap - self._cap))
        self._cap = new_cap

    def append(self, s):
        b = s.encode("utf-8") if isinstance(s, str) else s
        n = len(b)
        if self._len + n > self._cap:
            self._grow(self._len + n)
        if _memmove is not None:
            src = (ctypes.c_char * n).from_buffer_copy(b)
            _memmove(ctypes.byref(self._buf, self._len), src, n)
        else:
            self._buf[self._len:self._len + n] = b
        self._len += n

    def value(self):
        if _memmove is not None:
            return bytes(self._buf[:self._len]).decode("utf-8", "replace")
        return self._buf[:self._len].decode("utf-8", "replace")

    def __len__(self):
        return self._len


class BufferPool:
    __slots__ = ("_tls",)

    def __init__(self):
        self._tls = threading.local()

    def acquire(self):
        buf = getattr(self._tls, "buffer", None)
        if buf is None:
            buf = FastBuffer()
            self._tls.buffer = buf
        else:
            buf.reset()
        return buf


_POOL = BufferPool()


# ══════════════════════════════════════════════════════════════════════════
# Precompiled patterns
# ══════════════════════════════════════════════════════════════════════════

_RE_FENCE = re.compile(r"```([a-zA-Z0-9_+\-]*)\n(.*?)```", re.DOTALL)
_RE_FENCE_START = re.compile(r"^```")
_RE_FENCE_OPEN = re.compile(r"^```([a-zA-Z0-9_+\-]*)\s*$")
_RE_MATH_DISPLAY_DOLLAR = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_RE_MATH_DISPLAY_BRACKET = re.compile(r"\\\[(.+?)\\\]", re.DOTALL)
_RE_MATH_INLINE_PAREN = re.compile(r"\\\((.+?)\\\)", re.DOTALL)
_RE_MATH_INLINE_DOLLAR = re.compile(r"(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)")

_RE_HEADING_ATX = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_RE_HR = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
_RE_CALLOUT = re.compile(r"^>\s*\[!([A-Za-z]+)\]\s*(.*)$")
_RE_QUOTE_LINE = re.compile(r"^> ?(.*)$")
_RE_UL_ITEM = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_RE_OL_ITEM = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_RE_TASK_ITEM = re.compile(r"^\[([ xX])\]\s+(.*)$")
_RE_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
_RE_TABLE_SEP = re.compile(r"^\|[\s\-:|]+\|\s*$")
_RE_CODE_PLACEHOLDER = re.compile(r"\x00CODE(\d+)\x00")
_RE_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_RE_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^\)]+)\)")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")
_RE_BOLD_ITALIC_3 = re.compile(r"\*\*\*(.+?)\*\*\*", re.DOTALL)
_RE_BOLD_ITALIC_U3 = re.compile(r"___(.+?)___", re.DOTALL)
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_RE_BOLD_U = re.compile(r"__(.+?)__", re.DOTALL)
_RE_ITALIC = re.compile(r"(?<!\*)\*([^\*\n]+?)\*(?!\*)")
_RE_ITALIC_U = re.compile(r"(?<!_)_([^_\n]+?)_(?!_)")
_RE_STRIKE = re.compile(r"~~(.+?)~~", re.DOTALL)
_RE_HIGHLIGHT = re.compile(r"==(.+?)==", re.DOTALL)


# ══════════════════════════════════════════════════════════════════════════
# Extraction helpers
# ══════════════════════════════════════════════════════════════════════════

def extract_wikilinks(text):
    return [(m.group(1).strip(), (m.group(2) or m.group(1)).strip())
            for m in WIKILINK_RE.finditer(text)]


def extract_tags(text):
    cleaned = _RE_FENCE.sub("", text)
    cleaned = _RE_INLINE_CODE.sub("", cleaned)
    return sorted({t.lower() for t in TAG_RE.findall(cleaned)})


def extract_headings(text):
    out = []
    lines = text.splitlines()
    n = len(lines)
    i = 0
    in_fence = False
    while i < n:
        line = lines[i]
        if _RE_FENCE_START.match(line):
            in_fence = not in_fence
            i += 1
            continue
        if not in_fence:
            m = _RE_HEADING_ATX.match(line)
            if m:
                out.append((len(m.group(1)), m.group(2).strip(), i))
        i += 1
    return out


def extract_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("\"'")
    return fm, text[m.end():]


# ══════════════════════════════════════════════════════════════════════════
# Asset URLs
# ══════════════════════════════════════════════════════════════════════════

KATEX_VERSION = "0.16.9"
MERMAID_VERSION = "10.9.0"

KATEX_CSS_CDN = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.css"
KATEX_JS_CDN = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.js"
KATEX_AR_CDN = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/contrib/auto-render.min.js"
MERMAID_JS_CDN = f"https://cdn.jsdelivr.net/npm/mermaid@{MERMAID_VERSION}/dist/mermaid.min.js"


def _local_asset(vault_dir, name):
    if not vault_dir:
        return None
    p = Path(vault_dir) / "_vendor" / name
    if p.exists():
        return p.resolve().as_uri()
    return None


# ══════════════════════════════════════════════════════════════════════════
# Renderer
# ══════════════════════════════════════════════════════════════════════════

class MarkdownRenderer:
    __slots__ = ("css", "vault_dir", "_render_cached")

    def __init__(self, vault_dir=None):
        self.css = self._default_css()
        self.vault_dir = Path(vault_dir) if vault_dir else None
        self._render_cached = lru_cache(maxsize=64)(self._render_uncached)

    def render(self, text, known_notes=None):
        if known_notes:
            try:
                key_notes = tuple(sorted(known_notes))
            except TypeError:
                key_notes = tuple(sorted(str(x) for x in known_notes))
        else:
            key_notes = ()
        return self._render_cached(text, key_notes)

    def _render_uncached(self, text, known_notes):
        known = set(known_notes)
        fm, body = extract_frontmatter(text)

        buf = _POOL.acquire()
        self._render_body(body, known, buf)
        body_html = buf.value()

        fm_html = ""
        if fm:
            parts = ['<div class="frontmatter">']
            for k, v in fm.items():
                parts.append(
                    f'<div><span class="k">{html.escape(k)}:</span> '
                    f'<span class="v">{html.escape(str(v))}</span></div>'
                )
            parts.append("</div>")
            fm_html = "".join(parts)

        return self._wrap_document(fm_html + body_html)

    def _wrap_document(self, body):
        katex_css = _local_asset(self.vault_dir, "katex.min.css") or KATEX_CSS_CDN
        katex_js = _local_asset(self.vault_dir, "katex.min.js") or KATEX_JS_CDN
        katex_ar = _local_asset(self.vault_dir, "auto-render.min.js") or KATEX_AR_CDN
        mermaid_js = _local_asset(self.vault_dir, "mermaid.min.js") or MERMAID_JS_CDN

        return (
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            f'<link rel="stylesheet" href="{katex_css}">'
            f"<style>{self.css}</style>"
            f'<script defer src="{katex_js}"></script>'
            f'<script defer src="{katex_ar}"></script>'
            f'<script defer src="{mermaid_js}"></script>'
            "<script>\n"
            "(function(){\n"
            "  function boot(){\n"
            "    if (window.renderMathInElement){\n"
            "      try {\n"
            "        renderMathInElement(document.body, {\n"
            "          delimiters: [\n"
            "            {left:'$$',right:'$$',display:true},\n"
            "            {left:'\\\\[',right:'\\\\]',display:true},\n"
            "            {left:'$',right:'$',display:false},\n"
            "            {left:'\\\\(',right:'\\\\)',display:false}\n"
            "          ],\n"
            "          throwOnError:false,\n"
            "          ignoredTags:['script','noscript','style','textarea','pre','code']\n"
            "        });\n"
            "      } catch(e){ console.warn('KaTeX:', e); }\n"
            "    }\n"
            "    if (window.mermaid){\n"
            "      try {\n"
            "        mermaid.initialize({startOnLoad:false, theme:'dark',\n"
            "          securityLevel:'strict', fontFamily:'Segoe UI'});\n"
            "        mermaid.run({querySelector:'.mermaid'});\n"
            "      } catch(e){ console.warn('Mermaid:', e); }\n"
            "    }\n"
            "  }\n"
            "  if (document.readyState === 'loading'){\n"
            "    document.addEventListener('DOMContentLoaded', boot);\n"
            "  } else { boot(); }\n"
            "})();\n"
            "</script>"
            f"</head><body>{body}</body></html>"
        )

    def _render_body(self, text, known, buf):
        code_blocks = []

        def stash_code(m):
            code_blocks.append((m.group(1) or "", m.group(2)))
            return f"\x00CODE{len(code_blocks)-1}\x00"

        text = _RE_FENCE.sub(stash_code, text)
        text = html.escape(text)
        lines = text.split("\n")

        buf_append = buf.append
        inline = self._inline

        in_ul = False
        in_ol = False
        in_quote = False
        in_table = False
        table_rows = []

        def close_blocks():
            nonlocal in_ul, in_ol, in_quote
            if in_ul:
                buf_append("</ul>")
                in_ul = False
            if in_ol:
                buf_append("</ol>")
                in_ol = False
            if in_quote:
                buf_append("</blockquote>")
                in_quote = False

        def flush_table():
            nonlocal in_table, table_rows
            if in_table and table_rows:
                rows_html = []
                for i, row in enumerate(table_rows):
                    cells = row.strip("|").split("|")
                    tag = "th" if i == 0 else "td"
                    cell_html = "".join(
                        f"<{tag}>{inline(c.strip(), known)}</{tag}>"
                        for c in cells
                    )
                    rows_html.append(f"<tr>{cell_html}</tr>")
                buf_append("<table>" + "".join(rows_html) + "</table>")
            in_table = False
            table_rows = []

        for raw_line in lines:
            if raw_line and raw_line[0] == "\x00":
                m = _RE_CODE_PLACEHOLDER.match(raw_line)
                if m:
                    close_blocks()
                    flush_table()
                    idx = int(m.group(1))
                    lang, code = code_blocks[idx]
                    if lang == "mermaid":
                        buf_append(
                            '<div class="mermaid">'
                            + html.escape(code)
                            + "</div>"
                        )
                    else:
                        cls = f' class="language-{lang}"' if lang else ""
                        buf_append(
                            f"<pre><code{cls}>"
                            + html.escape(code)
                            + "</code></pre>"
                        )
                    continue

            line = raw_line
            s = line.strip()
            if s and s[0] == "|" and s[-1] == "|" and not in_quote:
                if _RE_TABLE_SEP.match(s):
                    continue
                if not in_table:
                    close_blocks()
                    in_table = True
                table_rows.append(s)
                continue
            elif in_table:
                flush_table()

            if line and line[0] == "#":
                m = _RE_HEADING_ATX.match(line)
                if m:
                    close_blocks()
                    lvl = len(m.group(1))
                    buf_append(
                        f"<h{lvl}>{inline(m.group(2), known)}</h{lvl}>"
                    )
                    continue

            if _RE_HR.match(line):
                close_blocks()
                buf_append("<hr>")
                continue

            if line.startswith(">"):
                m = _RE_CALLOUT.match(line)
                if m:
                    close_blocks()
                    buf_append(
                        f'<div class="callout">'
                        f'{inline(m.group(2), known)}</div>'
                    )
                    continue
                if not in_quote:
                    close_blocks()
                    buf_append("<blockquote>")
                    in_quote = True
                inner = _RE_QUOTE_LINE.match(line)
                if inner:
                    buf_append(inline(inner.group(1), known) + "<br>")
                continue
            elif in_quote:
                buf_append("</blockquote>")
                in_quote = False

            m = _RE_UL_ITEM.match(line)
            if m:
                item = m.group(3)
                task = _RE_TASK_ITEM.match(item)
                if task:
                    checked = task.group(1).lower() == "x"
                    item_html = (
                        f'<input type="checkbox" disabled '
                        f'{"checked" if checked else ""}> '
                        f"{inline(task.group(2), known)}"
                    )
                else:
                    item_html = inline(item, known)
                if not in_ul:
                    close_blocks()
                    buf_append("<ul>")
                    in_ul = True
                buf_append(f"<li>{item_html}</li>")
                continue
            elif in_ul and not (line.startswith("  ") or line.startswith("\t")):
                buf_append("</ul>")
                in_ul = False

            m = _RE_OL_ITEM.match(line)
            if m:
                if not in_ol:
                    close_blocks()
                    buf_append("<ol>")
                    in_ol = True
                buf_append(f"<li>{inline(m.group(3), known)}</li>")
                continue
            elif in_ol and not (line.startswith("  ") or line.startswith("\t")):
                buf_append("</ol>")
                in_ol = False

            if not line.strip():
                close_blocks()
                continue

            close_blocks()
            buf_append(f"<p>{inline(line, known)}</p>")

        close_blocks()
        flush_table()

    def _inline(self, text, known):
        codes = []

        def stash_code(m):
            codes.append(m.group(1))
            return f"\x01{len(codes)-1}\x01"

        text = _RE_INLINE_CODE.sub(stash_code, text)

        text = _RE_IMAGE.sub(
            lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}">',
            text,
        )
        text = _RE_LINK.sub(
            lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>',
            text,
        )
        text = WIKILINK_RE.sub(
            lambda m: self._wikilink_repl(m, known),
            text,
        )
        text = TAG_RE.sub(
            lambda m: f'<span class="tag">#{m.group(1)}</span>',
            text,
        )

        text = _RE_BOLD_ITALIC_3.sub(r"<strong><em>\1</em></strong>", text)
        text = _RE_BOLD_ITALIC_U3.sub(r"<strong><em>\1</em></strong>", text)
        text = _RE_BOLD.sub(r"<strong>\1</strong>", text)
        text = _RE_BOLD_U.sub(r"<strong>\1</strong>", text)
        text = _RE_ITALIC.sub(r"<em>\1</em>", text)
        text = _RE_ITALIC_U.sub(r"<em>\1</em>", text)

        text = _RE_STRIKE.sub(r"<del>\1</del>", text)
        text = _RE_HIGHLIGHT.sub(r"<mark>\1</mark>", text)

        if codes:
            for i, c in enumerate(codes):
                text = text.replace(f"\x01{i}\x01",
                                    f"<code>{html.escape(c)}</code>")
        return text

    def _wikilink_repl(self, m, known):
        target = m.group(1).strip()
        alias = (m.group(2) or target).strip()
        target_i = sys.intern(target)
        if target_i in known:
            is_known = True
        else:
            stem = Path(target_i).stem
            stem_i = sys.intern(stem)
            if stem_i in known:
                is_known = True
            else:
                is_known = any(Path(k).stem == stem_i for k in known)
        cls = "wikilink" if is_known else "wikilink missing"
        return (
            f'<a href="chert://open/{html.escape(target_i)}" '
            f'class="{cls}">{html.escape(alias)}</a>'
        )

    def _default_css(self):
        return r"""
:root { color-scheme: dark; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  font-size: 15px; line-height: 1.7; color: #d4d4d4; background: #1e1e1e;
  max-width: 860px; margin: 0 auto; padding: 36px 32px 80px;
  word-wrap: break-word; overflow-wrap: anywhere;
}
h1,h2,h3,h4,h5,h6 { font-weight: 600; line-height: 1.3; margin: 1.6em 0 .6em; color: #fff; }
h1 { font-size: 1.9em; border-bottom: 1px solid #333; padding-bottom: .3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid #2a2a2a; padding-bottom: .2em; }
h3 { font-size: 1.25em; } h4 { font-size: 1.1em; } h5,h6 { font-size: 1em; color: #c0c0c0; }
p { margin: .9em 0; }
a { color: #569cd6; text-decoration: none; }
a:hover { text-decoration: underline; }
a.wikilink { color: #c586c0; }
a.wikilink.missing { color: #808080; text-decoration: underline dashed; }
code {
  font-family: 'Cascadia Mono','Consolas','JetBrains Mono',monospace;
  font-size: .92em; background: #2a2a2a; padding: 2px 6px;
  border-radius: 4px; color: #ce9178;
}
pre {
  background: #252526; border: 1px solid #333; border-radius: 6px;
  padding: 14px 18px; overflow-x: auto; margin: 1em 0;
}
pre code { background: none; padding: 0; color: #d4d4d4; font-size: .9em; }
blockquote {
  border-left: 3px solid #c586c0; margin: 1em 0; padding: .4em 1em;
  background: rgba(197,134,192,.06); color: #b0b0b0;
}
ul,ol { padding-left: 1.8em; margin: .8em 0; }
li { margin: .3em 0; }
hr { border: none; border-top: 1px solid #333; margin: 2em 0; }
table { border-collapse: collapse; margin: 1em 0; width: 100%; }
th,td { border: 1px solid #333; padding: 8px 12px; text-align: left; }
th { background: #252526; font-weight: 600; }
img { max-width: 100%; height: auto; border-radius: 4px; }
.tag {
  display: inline-block; color: #4ec9b0;
  background: rgba(78,201,176,.1); padding: 1px 8px;
  border-radius: 10px; font-size: .88em; margin: 0 2px;
}
.frontmatter {
  background: #252526; border: 1px solid #333; border-radius: 6px;
  padding: 10px 16px; margin-bottom: 1.5em; font-size: .9em; color: #808080;
}
.frontmatter .k { color: #9cdcfe; }
.frontmatter .v { color: #ce9178; }
mark { background: #613214; color: #ffd7a8; padding: 0 3px; border-radius: 2px; }
del { color: #808080; }
.callout {
  border-left: 4px solid #569cd6; background: rgba(86,156,214,.08);
  padding: 10px 16px; border-radius: 0 6px 6px 0; margin: 1em 0;
}
.katex { font-size: 1.05em; }
.katex-display { margin: 1.2em 0; overflow-x: auto; overflow-y: hidden; }
.mermaid {
  background: #1a1a1a; border: 1px solid #333; border-radius: 6px;
  padding: 16px; margin: 1em 0; text-align: center; overflow-x: auto;
}
.mermaid svg { max-width: 100%; height: auto; }
"""


# ══════════════════════════════════════════════════════════════════════════
# Syntax highlighter
# ══════════════════════════════════════════════════════════════════════════

class MarkdownHighlighter(QSyntaxHighlighter):
    __slots__ = ("_formats", "_rules")

    def __init__(self, document):
        super().__init__(document)
        self._formats = {}
        self._rules = []
        self._build()

    def _fmt(self, color, bold=False, italic=False, underline=False,
             size=None, family=None, bg=None):
        f = QTextCharFormat()
        f.setForeground(QColor(color))
        if bold:
            f.setFontWeight(QFont.Weight.Bold)
        if italic:
            f.setFontItalic(True)
        if underline:
            f.setFontUnderline(True)
        if size:
            f.setFontPointSize(size)
        if family:
            f.setFontFamily(family)
        if bg:
            f.setBackground(QColor(bg))
        return f

    def _build(self):
        F = self._formats
        F["h1"] = self._fmt("#ffffff", bold=True, size=22)
        F["h2"] = self._fmt("#ffffff", bold=True, size=19)
        F["h3"] = self._fmt("#ffffff", bold=True, size=16)
        F["h4"] = self._fmt("#e6e6e6", bold=True, size=14)
        F["h5"] = self._fmt("#e0e0e0", bold=True)
        F["h6"] = self._fmt("#d0d0d0", bold=True)
        F["bold"] = self._fmt("#dcdcaa", bold=True)
        F["italic"] = self._fmt("#c586c0", italic=True)
        F["code"] = self._fmt("#ce9178", family="Consolas", bg="#2a2a2a")
        F["link"] = self._fmt("#569cd6", underline=True)
        F["wikilink"] = self._fmt("#c586c0", underline=True)
        F["tag"] = self._fmt("#4ec9b0")
        F["quote"] = self._fmt("#6a9955", italic=True)
        F["hr"] = self._fmt("#555555", bold=True)
        F["marker"] = self._fmt("#808080")
        F["highlight"] = self._fmt("#ffd7a8", bg="#613214")
        F["strike"] = self._fmt("#808080")
        F["math"] = self._fmt("#dcdcaa")
        F["mermaid"] = self._fmt("#4ec9b0", bold=True, bg="#1a1a1a")

        self._rules = [
            (_RE_BOLD_ITALIC_3, F["bold"]),
            (_RE_BOLD_ITALIC_U3, F["bold"]),
            (_RE_BOLD, F["bold"]),
            (_RE_BOLD_U, F["bold"]),
            (_RE_ITALIC, F["italic"]),
            (_RE_ITALIC_U, F["italic"]),
            (_RE_INLINE_CODE, F["code"]),
            (WIKILINK_RE, F["wikilink"]),
            (_RE_LINK, F["link"]),
            (_RE_IMAGE, F["link"]),
            (TAG_RE, F["tag"]),
            (_RE_HIGHLIGHT, F["highlight"]),
            (_RE_STRIKE, F["strike"]),
            (_RE_MATH_INLINE_PAREN, F["math"]),
            (_RE_MATH_INLINE_DOLLAR, F["math"]),
        ]

    def highlightBlock(self, text):
        prev_state = self.previousBlockState()

        if prev_state == 1:
            if _RE_FENCE_START.match(text):
                self.setFormat(0, len(text), self._formats["code"])
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, len(text), self._formats["code"])
                self.setCurrentBlockState(1)
            return

        if _RE_FENCE_START.match(text):
            lang_match = _RE_FENCE_OPEN.match(text)
            if lang_match and lang_match.group(1) == "mermaid":
                self.setFormat(0, len(text), self._formats["mermaid"])
            else:
                self.setFormat(0, len(text), self._formats["code"])
            self.setCurrentBlockState(1)
            return

        if text and text[0] == "#":
            m = _RE_HEADING_ATX.match(text)
            if m:
                key = f"h{len(m.group(1))}"
                fmt = self._formats.get(key)
                if fmt:
                    self.setFormat(0, len(text), fmt)
                    return

        if text.startswith(">"):
            self.setFormat(0, len(text), self._formats["quote"])

        if _RE_HR.match(text):
            self.setFormat(0, len(text), self._formats["hr"])
            return

        m = _RE_UL_ITEM.match(text) or _RE_OL_ITEM.match(text)
        if m:
            g = m.group(2)
            self.setFormat(m.start(2), len(g), self._formats["marker"])

        rules = self._rules
        setFormat = self.setFormat
        for pattern, fmt in rules:
            for mm in pattern.finditer(text):
                setFormat(mm.start(), mm.end() - mm.start(), fmt)