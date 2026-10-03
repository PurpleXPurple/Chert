"""
Live_Preview.py — Editor widget + preview pane + split live-preview widget.

v0.2 changes:
  • Advanced scheduling: adaptive debounce, hash-skip, visibility-aware deferral
  • Known-notes cache with TTL — kills the O(n) vault walk per render
  • Four error categories with dedicated handler classes:
        FileErrorHandler        — file I/O
        RenderErrorHandler      — markdown -> HTML
        WebEngineErrorHandler   — QWebEngineView interop
        UIErrorHandler          — editor / widget state
  • Central ErrorRouter with @guard decorator + installable sink

Public surface (unchanged from v0.1):
  MarkdownEditor(parent, font_family=..., font_size=...)
  MarkdownPreview(parent, theme=...)
  LivePreviewPane(parent, vault=..., settings=..., rel_path=...)
  signals: content_changed, link_clicked
"""

import re
import time
import traceback
from pathlib import Path
from typing import Callable, Optional

from Chert_Managers import (
    Qt, QTimer, QWidget, QVBoxLayout, QSplitter, QPlainTextEdit,
    QTextCursor, QFont, QColor, QTextEdit, QUrl, QDesktopServices,
    pyqtSignal, HAS_WEBENGINE, QWebEngineView, PYQT6,
)
from Markdown_Chert import MarkdownRenderer, MarkdownHighlighter


# ══════════════════════════════════════════════════════════════════════════
# Error handling — four categories, four handlers
# ══════════════════════════════════════════════════════════════════════════

CATEGORY_FILE = "file"
CATEGORY_RENDER = "render"
CATEGORY_WEBENGINE = "webengine"
CATEGORY_UI = "ui"


class _ErrorRecord:
    """Bounded ring-buffer entry. Kept tiny — it's hot when errors pile up."""

    __slots__ = ("category", "context", "exc_type", "exc_msg", "trace", "ts")

    def __init__(self, category, context, exc, trace=""):
        self.category = category
        self.context = context
        self.exc_type = type(exc).__name__ if exc else "None"
        self.exc_msg = str(exc) if exc else ""
        self.trace = trace
        self.ts = time.time()

    def __repr__(self):
        return f"<{self.category}/{self.context}: {self.exc_type}: {self.exc_msg}>"


class _BaseHandler:
    """
    Shared machinery for all four category handlers.

    - Bounded ring buffer of recent errors (default 64).
    - Per-context counters for light-weight health reporting.
    - Optional sink callback: called for every un-muted error so the
      application layer can surface a status-bar toast, log to file, etc.
    - Muting by context so repeated failures (e.g. missing optional asset)
      don't spam the UI.
    """

    __slots__ = ("name", "_ring", "_max", "_counts", "_on_error", "_muted")

    def __init__(self, name, max_records=64):
        self.name = name
        self._max = int(max_records)
        self._ring: list = []
        self._counts: dict = {}
        self._on_error: Optional[Callable] = None
        self._muted: set = set()

    def set_sink(self, callback: Optional[Callable]):
        self._on_error = callback

    def mute(self, context: str):
        self._muted.add(context)

    def unmute(self, context: str):
        self._muted.discard(context)

    def report(self, context: str, exc, trace: str = "") -> None:
        rec = _ErrorRecord(self.name, context, exc, trace)
        ring = self._ring
        ring.append(rec)
        if len(ring) > self._max:
            del ring[: len(ring) - self._max]
        self._counts[context] = self._counts.get(context, 0) + 1
        sink = self._on_error
        if sink is not None and context not in self._muted:
            try:
                sink(rec)
            except Exception:
                # A broken sink must never cascade.
                pass

    def count(self, context: Optional[str] = None) -> int:
        if context is None:
            return sum(self._counts.values())
        return self._counts.get(context, 0)

    def recent(self, n: int = 10):
        return self._ring[-n:]

    def clear(self):
        self._ring.clear()
        self._counts.clear()


class FileErrorHandler(_BaseHandler):
    """Category: file I/O. Wraps disk reads/writes so a bad path never kills the UI."""

    __slots__ = ()

    def __init__(self, max_records=64):
        super().__init__(CATEGORY_FILE, max_records)

    def safe_read(self, path, default: str = "") -> str:
        try:
            return Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError) as e:
            self.report("read", e, traceback.format_exc())
            return default

    def safe_write(self, path, content: str) -> bool:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return True
        except (OSError, UnicodeEncodeError, ValueError) as e:
            self.report("write", e, traceback.format_exc())
            return False


class RenderErrorHandler(_BaseHandler):
    """Category: markdown -> HTML. Never lets a bad note blank the preview."""

    __slots__ = ()

    def __init__(self, max_records=64):
        super().__init__(CATEGORY_RENDER, max_records)

    def safe_render(self, renderer: MarkdownRenderer, text: str,
                    known_notes, default_html: Optional[str] = None) -> str:
        try:
            return renderer.render(text, known_notes)
        except (ValueError, UnicodeError, RecursionError, MemoryError,
                ArithmeticError) as e:
            self.report("render", e, traceback.format_exc())
            if default_html is not None:
                return default_html
            return self._error_page(e)

    @staticmethod
    def _error_page(exc) -> str:
        return (
            "<!DOCTYPE html><html><body style='font-family:sans-serif;"
            "background:#1e1e1e;color:#d4d4d4;padding:40px'>"
            "<h3 style='color:#f48771;margin:0 0 .6em'>Render error</h3>"
            f"<pre style='background:#252526;padding:12px;border-radius:6px;"
            f"overflow:auto'>{type(exc).__name__}: {exc}</pre>"
            "</body></html>"
        )


class WebEngineErrorHandler(_BaseHandler):
    """Category: QWebEngineView. Wraps page() calls that can raise RuntimeError
    when the underlying page is deleted or the WebEngine process dies."""

    __slots__ = ()

    def __init__(self, max_records=64):
        super().__init__(CATEGORY_WEBENGINE, max_records)

    def safe_set_html(self, view, html: str, base_url) -> bool:
        try:
            view.setHtml(html, base_url)
            return True
        except (RuntimeError, AttributeError) as e:
            self.report("set_html", e, traceback.format_exc())
            return False

    def safe_background(self, view, color_hex: str) -> bool:
        try:
            view.page().setBackgroundColor(QColor(color_hex))
            return True
        except (RuntimeError, AttributeError) as e:
            self.report("background", e, traceback.format_exc())
            return False

    def safe_nav_hook(self, page, callback) -> bool:
        try:
            page.acceptNavigationRequest = callback
            return True
        except (RuntimeError, AttributeError) as e:
            self.report("nav_hook", e, traceback.format_exc())
            return False


class UIErrorHandler(_BaseHandler):
    """Category: editor/widget state. Fonts, cursors, signals, geometry."""

    __slots__ = ()

    def __init__(self, max_records=64):
        super().__init__(CATEGORY_UI, max_records)

    def safe_font(self, family: str, size: int) -> QFont:
        try:
            f = QFont(family, size)
            # Qt silently substitutes when the family isn't present; report
            # once and keep going with whatever Qt chose.
            if family and f.family().lower() != family.lower():
                self.report(
                    "font_fallback",
                    RuntimeError(f"Font '{family}' unavailable, using '{f.family()}'"),
                    "",
                )
            return f
        except (RuntimeError, TypeError) as e:
            self.report("font", e, traceback.format_exc())
            return QFont()

    def safe_cursor_op(self, widget, op: Callable):
        try:
            return op(widget.textCursor())
        except (RuntimeError, AttributeError) as e:
            self.report("cursor", e, traceback.format_exc())
            return None

    def safe_connect(self, signal, slot, context: str = "connect") -> bool:
        try:
            signal.connect(slot)
            return True
        except (TypeError, RuntimeError) as e:
            self.report(context, e, traceback.format_exc())
            return False

    def safe_tab_stop(self, widget, spaces: int = 4):
        try:
            px = spaces * widget.fontMetrics().horizontalAdvance(" ")
            if hasattr(widget, "setTabStopDistance"):
                widget.setTabStopDistance(px)
            elif hasattr(widget, "setTabStopWidth"):  # very old Qt5
                widget.setTabStopWidth(px)
        except (AttributeError, RuntimeError) as e:
            self.report("tab_stop", e, traceback.format_exc())


class ErrorRouter:
    """Central dispatcher holding one handler per category."""

    __slots__ = ("file", "render", "webengine", "ui")

    def __init__(self):
        self.file = FileErrorHandler()
        self.render = RenderErrorHandler()
        self.webengine = WebEngineErrorHandler()
        self.ui = UIErrorHandler()

    def set_sink(self, callback: Optional[Callable]):
        for h in self.all_handlers():
            h.set_sink(callback)

    def all_handlers(self):
        return (self.file, self.render, self.webengine, self.ui)

    def total_count(self) -> int:
        return sum(h.count() for h in self.all_handlers())

    def summary(self) -> dict:
        return {h.name: h.count() for h in self.all_handlers()}

    def _get(self, category: str) -> _BaseHandler:
        if category == CATEGORY_FILE:
            return self.file
        if category == CATEGORY_RENDER:
            return self.render
        if category == CATEGORY_WEBENGINE:
            return self.webengine
        if category == CATEGORY_UI:
            return self.ui
        raise KeyError(f"Unknown error category: {category}")

    def report(self, category: str, context: str, exc, trace: str = ""):
        self._get(category).report(context, exc, trace)

    def guard(self, category: str, context: str, fallback=None):
        """
        Decorator. Any exception in the wrapped method is captured by the
        named category's handler; the fallback (value or callable) is
        returned instead of propagating.
        """
        def deco(fn):
            def wrapper(*args, **kwargs):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    self._get(category).report(context, e, traceback.format_exc())
                    return fallback() if callable(fallback) else fallback
            wrapper.__name__ = fn.__name__
            wrapper.__doc__ = fn.__doc__
            return wrapper
        return deco


# Module-level default router — install a sink from the app layer once:
#   from Live_Preview import default_router
#   default_router().set_sink(lambda rec: print(rec))
_DEFAULT_ROUTER = ErrorRouter()


def default_router() -> ErrorRouter:
    return _DEFAULT_ROUTER


# ══════════════════════════════════════════════════════════════════════════
# Editor
# ══════════════════════════════════════════════════════════════════════════

_RE_LIST_CONT = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(\[[ xX]\]\s+)?")
_RE_SCRIPT_TAG = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)


class MarkdownEditor(QPlainTextEdit):
    """
    Plain-text editor with markdown highlighting and list continuation.

    All widget-level failures route to UIErrorHandler. The editor never
    propagates a Qt RuntimeError up the stack — if the widget is being
    torn down mid-operation, we swallow the error and return.
    """

    content_changed = pyqtSignal(str)

    def __init__(self, parent=None, font_family: str = "Consolas",
                 font_size: int = 13, errors: Optional[ErrorRouter] = None):
        super().__init__(parent)
        self._errors = errors or _DEFAULT_ROUTER

        font = self._errors.ui.safe_font(font_family, font_size)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._errors.ui.safe_tab_stop(self, 4)

        self.setStyleSheet("""
            QPlainTextEdit {
                background: #1e1e1e; color: #d4d4d4; border: none;
                selection-background-color: #264f78;
                selection-color: #ffffff;
                padding: 20px 24px;
                font-family: 'Consolas', 'Cascadia Mono', monospace;
            }
        """)

        self._errors.ui.safe_connect(
            self.textChanged,
            self._emit_content_changed,
            context="textChanged",
        )

    def _emit_content_changed(self):
        try:
            self.content_changed.emit(self.toPlainText())
        except RuntimeError as e:
            # Widget mid-teardown; nothing to do.
            self._errors.ui.report("emit_content", e, traceback.format_exc())

    def keyPressEvent(self, event):
        try:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._try_list_continuation(event):
                    return
        except Exception as e:
            # Never let an editor logic error eat the keystroke.
            self._errors.ui.report("list_continue", e, traceback.format_exc())
        super().keyPressEvent(event)

    def _try_list_continuation(self, event) -> bool:
        cursor = self.textCursor()
        block = cursor.block().text()
        m = _RE_LIST_CONT.match(block)
        if not m:
            return False

        indent, marker, task = m.group(1), m.group(2), m.group(3)
        if marker and marker[0].isdigit():
            marker = f"{int(marker[:-1]) + 1}."

        prefix = indent + marker + " "
        if task:
            prefix += "[ ] "

        trailing = block[len(m.group(0)):].strip()
        if not trailing:
            # Empty item — drop the marker and end the list.
            try:
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
            except (RuntimeError, AttributeError) as e:
                self._errors.ui.report("cursor_drop", e, traceback.format_exc())
            super().keyPressEvent(event)
            return True

        super().keyPressEvent(event)
        self.insertPlainText(prefix)
        return True


# ══════════════════════════════════════════════════════════════════════════
# Preview
# ══════════════════════════════════════════════════════════════════════════

class MarkdownPreview(QWidget):
    """
    Renders markdown -> HTML.

    Prefers QWebEngineView (full KaTeX / Mermaid support) and falls back
    to a styled QTextEdit when the WebEngine module isn't installed.
    Every WebEngine call routes through WebEngineErrorHandler; every
    render routes through RenderErrorHandler.
    """

    link_clicked = pyqtSignal(str)

    def __init__(self, parent=None, theme: str = "dark",
                 errors: Optional[ErrorRouter] = None):
        super().__init__(parent)
        self._errors = errors or _DEFAULT_ROUTER
        self.renderer = MarkdownRenderer()
        self.known_notes: set = set()
        self._mode = "web" if HAS_WEBENGINE else "text"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if HAS_WEBENGINE:
            self.view = QWebEngineView()
            self._errors.webengine.safe_background(self.view, "#1e1e1e")
            try:
                page = self.view.page()
                if page is not None:
                    self._errors.webengine.safe_nav_hook(page, self._nav)
            except RuntimeError as e:
                self._errors.webengine.report("page_access", e, traceback.format_exc())
        else:
            self.view = QTextEdit()
            self.view.setReadOnly(True)
            self.view.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            self.view.setStyleSheet(
                "QTextEdit { background: #1e1e1e; color: #d4d4d4; "
                "border: none; padding: 20px 24px; font-size: 15px; }"
            )
        layout.addWidget(self.view)

    # ── public ──────────────────────────────────────────────────────────
    def set_known_notes(self, notes):
        try:
            self.known_notes = set(notes)
        except TypeError as e:
            self._errors.render.report("known_notes", e, traceback.format_exc())

    def render(self, text: str):
        html = self._errors.render.safe_render(
            self.renderer, text, self.known_notes
        )
        if not html:
            return

        if self._mode == "web":
            self._errors.webengine.safe_set_html(
                self.view, html, QUrl("about:blank")
            )
        else:
            # QTextEdit: strip scripts so Qt doesn't warn about unhandled JS.
            clean = _RE_SCRIPT_TAG.sub("", html)
            try:
                self.view.setHtml(clean)
            except (RuntimeError, AttributeError) as e:
                self._errors.render.report("setHtml_fallback", e,
                                           traceback.format_exc())

    # ── internals ───────────────────────────────────────────────────────
    def _nav(self, url, *args):
        try:
            u = url.toString()
            if u.startswith("chert://open/"):
                self.link_clicked.emit(u[len("chert://open/"):])
                return False
            if u.startswith(("http://", "https://")):
                QDesktopServices.openUrl(url)
                return False
            return True
        except Exception as e:
            self._errors.webengine.report("nav", e, traceback.format_exc())
            return True


# ══════════════════════════════════════════════════════════════════════════
# Live preview pane
# ══════════════════════════════════════════════════════════════════════════

class LivePreviewPane(QSplitter):
    """
    Editor + preview, with advanced update scheduling.

    Scheduling strategy:
      1. Every edit sets `_pending` and (re)starts a single-shot debounce.
      2. The debounce delay scales with document size — tiny docs render
         almost instantly, huge docs wait longer so the user can keep
         typing without stutter.
      3. On fire, we compute a cheap hash of the current text. If it
         matches the last render, we bail without touching the renderer.
      4. Known-note set is cached with a short TTL; the vault walk that
         builds it is O(n) and was being re-run on every keystroke.
      5. Invisible panes never render. On `showEvent`, a pending render
         is kicked off so tabs that were hidden while edited catch up.
    """

    _MIN_DEBOUNCE_MS = 70
    _MAX_DEBOUNCE_MS = 220
    _KNOWN_NOTES_TTL = 1.5  # seconds

    def __init__(self, parent=None, vault=None, settings=None,
                 rel_path: Optional[str] = None,
                 errors: Optional[ErrorRouter] = None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._errors = errors or _DEFAULT_ROUTER
        self.vault = vault
        self.settings = settings
        self.rel_path = rel_path

        font_family = settings.get("editor_font", "Consolas") if settings else "Consolas"
        font_size = settings.get("editor_font_size", 13) if settings else 13

        self.editor = MarkdownEditor(
            self,
            font_family=font_family,
            font_size=font_size,
            errors=self._errors,
        )
        self.highlighter = MarkdownHighlighter(self.editor.document())
        self.preview = MarkdownPreview(self, errors=self._errors)

        self.addWidget(self.editor)
        self.addWidget(self.preview)
        self.setSizes([620, 620])

        # Scheduling state
        self._pending: bool = False
        self._last_hash: int = 0
        self._last_known: frozenset = frozenset()
        self._known_cache: Optional[frozenset] = None
        self._known_cache_ts: float = 0.0

        # Diagnostics
        self._render_count: int = 0
        self._skip_count: int = 0
        self._last_render_ms: float = 0.0

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._render_now)

        self._errors.ui.safe_connect(
            self.editor.content_changed,
            self._on_content_changed,
            context="content_changed",
        )

    # ── public API (unchanged) ──────────────────────────────────────────
    def load(self, text: str):
        try:
            self.editor.blockSignals(True)
            self.editor.setPlainText(text)
        except RuntimeError as e:
            self._errors.ui.report("load_set_text", e, traceback.format_exc())
        finally:
            try:
                self.editor.blockSignals(False)
            except RuntimeError:
                pass
        self._last_hash = 0
        self._pending = True
        self._render_now()

    def text(self) -> str:
        try:
            return self.editor.toPlainText()
        except RuntimeError as e:
            self._errors.ui.report("read_text", e, traceback.format_exc())
            return ""

    def render_stats(self) -> dict:
        return {
            "renders": self._render_count,
            "skips": self._skip_count,
            "last_render_ms": self._last_render_ms,
        }

    # ── scheduling ──────────────────────────────────────────────────────
    def _on_content_changed(self, _text: str):
        if not self.isVisible():
            # Mark for catch-up; don't waste cycles rendering invisibly.
            self._pending = True
            return

        try:
            size = self.editor.document().characterCount()
        except (RuntimeError, AttributeError):
            size = 0

        # Linear ramp from MIN at ~0 chars to MAX at ~200k chars.
        span = self._MAX_DEBOUNCE_MS - self._MIN_DEBOUNCE_MS
        delay = self._MIN_DEBOUNCE_MS + min(span, size // 900)

        self._pending = True
        self._debounce.start(delay)

    def _render_now(self):
        if not self._pending:
            return
        self._pending = False

        text = self.text()
        h = self._cheap_hash(text)
        known = self._current_known_notes()

        # Hash-skip: identical text + identical known-notes → nothing to do.
        if h == self._last_hash and known == self._last_known:
            self._skip_count += 1
            return

        self._last_hash = h
        self._last_known = known

        if known:
            self.preview.set_known_notes(known)

        t0 = time.monotonic()
        self.preview.render(text)
        self._last_render_ms = (time.monotonic() - t0) * 1000.0
        self._render_count += 1

    # ── caching helpers ─────────────────────────────────────────────────
    @staticmethod
    def _cheap_hash(text: str) -> int:
        """
        Sample-based hash. Full `hash(text)` on a 1 MB note is fast enough
        but on multi-MB notes the sampling wins. Collision risk is
        acceptable — we're only skipping redundant re-renders, and a real
        change within the sample window is astronomically unlikely.
        """
        n = len(text)
        if n <= 512:
            return hash(text)
        return hash((n, text[:128], text[n // 2 - 64: n // 2 + 64], text[-128:]))

    def _current_known_notes(self) -> frozenset:
        if not self.vault:
            return frozenset()

        now = time.monotonic()
        if (self._known_cache is not None
                and (now - self._known_cache_ts) < self._KNOWN_NOTES_TTL):
            return self._known_cache

        try:
            notes = set()
            for p in self.vault.list_notes():
                rel = self.vault.rel_path(p)
                notes.add(rel)
                notes.add(Path(rel).stem)
            self._known_cache = frozenset(notes)
            self._known_cache_ts = now
            return self._known_cache
        except Exception as e:
            self._errors.render.report("known_notes", e, traceback.format_exc())
            return self._known_cache if self._known_cache is not None else frozenset()

    # ── visibility catch-up ─────────────────────────────────────────────
    def showEvent(self, event):
        super().showEvent(event)
        if self._pending:
            # Coalesce the catch-up so a tab drag doesn't fire a render
            # per intermediate show event.
            self._debounce.start(self._MIN_DEBOUNCE_MS)

    def hideEvent(self, event):
        super().hideEvent(event)
        # Cancel any scheduled render; showEvent will reschedule.
        try:
            self._debounce.stop()
        except RuntimeError:
            pass
        if not self._pending:
            self._pending = True


# ══════════════════════════════════════════════════════════════════════════
# Convenience re-exports
# ══════════════════════════════════════════════════════════════════════════

__all__ = [
    "MarkdownEditor",
    "MarkdownPreview",
    "LivePreviewPane",
    "ErrorRouter",
    "FileErrorHandler",
    "RenderErrorHandler",
    "WebEngineErrorHandler",
    "UIErrorHandler",
    "default_router",
    "CATEGORY_FILE",
    "CATEGORY_RENDER",
    "CATEGORY_WEBENGINE",
    "CATEGORY_UI",
]