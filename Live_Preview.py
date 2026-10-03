"""
Live_Preview.py — Editor widget + preview pane + split live-preview widget.

PyQt6-only. Advanced scheduling, known-notes TTL cache, four error
categories with dedicated handler classes.
"""

import re
import time
import traceback
from pathlib import Path
from typing import Callable, Optional

from Chert_Managers import (
    Qt, QTimer, QWidget, QVBoxLayout, QSplitter, QPlainTextEdit,
    QTextCursor, QFont, QColor, QTextEdit, QUrl, QDesktopServices,
    pyqtSignal, HAS_WEBENGINE, QWebEngineView,
)
from Markdown_Chert import MarkdownRenderer, MarkdownHighlighter


CATEGORY_FILE = "file"
CATEGORY_RENDER = "render"
CATEGORY_WEBENGINE = "webengine"
CATEGORY_UI = "ui"


class _ErrorRecord:
    __slots__ = ("category", "context", "exc_type", "exc_msg", "trace", "ts")

    def __init__(self, category, context, exc, trace=""):
        self.category = category
        self.context = context
        self.exc_type = type(exc).__name__ if exc else "None"
        self.exc_msg = str(exc) if exc else ""
        self.trace = trace
        self.ts = time.time()


class _BaseHandler:
    __slots__ = ("name", "_ring", "_max", "_counts", "_on_error", "_muted")

    def __init__(self, name, max_records=64):
        self.name = name
        self._max = int(max_records)
        self._ring = []
        self._counts = {}
        self._on_error = None
        self._muted = set()

    def set_sink(self, callback):
        self._on_error = callback

    def mute(self, context):
        self._muted.add(context)

    def unmute(self, context):
        self._muted.discard(context)

    def report(self, context, exc, trace=""):
        rec = _ErrorRecord(self.name, context, exc, trace)
        self._ring.append(rec)
        if len(self._ring) > self._max:
            del self._ring[: len(self._ring) - self._max]
        self._counts[context] = self._counts.get(context, 0) + 1
        if self._on_error is not None and context not in self._muted:
            try:
                self._on_error(rec)
            except Exception:
                pass

    def count(self, context=None):
        if context is None:
            return sum(self._counts.values())
        return self._counts.get(context, 0)

    def recent(self, n=10):
        return self._ring[-n:]

    def clear(self):
        self._ring.clear()
        self._counts.clear()


class FileErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=64):
        super().__init__(CATEGORY_FILE, max_records)

    def safe_read(self, path, default=""):
        try:
            return Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError) as e:
            self.report("read", e, traceback.format_exc())
            return default

    def safe_write(self, path, content):
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return True
        except (OSError, UnicodeEncodeError, ValueError) as e:
            self.report("write", e, traceback.format_exc())
            return False


class RenderErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=64):
        super().__init__(CATEGORY_RENDER, max_records)

    def safe_render(self, renderer, text, known_notes, default_html=None):
        try:
            return renderer.render(text, known_notes)
        except (ValueError, UnicodeError, RecursionError, MemoryError,
                ArithmeticError) as e:
            self.report("render", e, traceback.format_exc())
            if default_html is not None:
                return default_html
            return self._error_page(e)

    @staticmethod
    def _error_page(exc):
        return (
            "<!DOCTYPE html><html><body style='font-family:sans-serif;"
            "background:#1e1e1e;color:#d4d4d4;padding:40px'>"
            "<h3 style='color:#f48771;margin:0 0 .6em'>Render error</h3>"
            f"<pre style='background:#252526;padding:12px;border-radius:6px;"
            f"overflow:auto'>{type(exc).__name__}: {exc}</pre>"
            "</body></html>"
        )


class WebEngineErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=64):
        super().__init__(CATEGORY_WEBENGINE, max_records)

    def safe_set_html(self, view, html, base_url):
        try:
            view.setHtml(html, base_url)
            return True
        except (RuntimeError, AttributeError) as e:
            self.report("set_html", e, traceback.format_exc())
            return False

    def safe_background(self, view, color_hex):
        try:
            view.page().setBackgroundColor(QColor(color_hex))
            return True
        except (RuntimeError, AttributeError) as e:
            self.report("background", e, traceback.format_exc())
            return False

    def safe_nav_hook(self, page, callback):
        try:
            page.acceptNavigationRequest = callback
            return True
        except (RuntimeError, AttributeError) as e:
            self.report("nav_hook", e, traceback.format_exc())
            return False


class UIErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=64):
        super().__init__(CATEGORY_UI, max_records)

    def safe_font(self, family, size):
        try:
            f = QFont(family, size)
            if family and f.family().lower() != family.lower():
                self.report(
                    "font_fallback",
                    RuntimeError(f"Font '{family}' unavailable, using '{f.family()}'"),
                )
            return f
        except (RuntimeError, TypeError) as e:
            self.report("font", e, traceback.format_exc())
            return QFont()

    def safe_cursor_op(self, widget, op):
        try:
            return op(widget.textCursor())
        except (RuntimeError, AttributeError) as e:
            self.report("cursor", e, traceback.format_exc())
            return None

    def safe_connect(self, signal, slot, context="connect"):
        try:
            signal.connect(slot)
            return True
        except (TypeError, RuntimeError) as e:
            self.report(context, e, traceback.format_exc())
            return False

    def safe_tab_stop(self, widget, spaces=4):
        try:
            px = spaces * widget.fontMetrics().horizontalAdvance(" ")
            if hasattr(widget, "setTabStopDistance"):
                widget.setTabStopDistance(px)
            elif hasattr(widget, "setTabStopWidth"):
                widget.setTabStopWidth(px)
        except (AttributeError, RuntimeError) as e:
            self.report("tab_stop", e, traceback.format_exc())


class ErrorRouter:
    __slots__ = ("file", "render", "webengine", "ui")

    def __init__(self):
        self.file = FileErrorHandler()
        self.render = RenderErrorHandler()
        self.webengine = WebEngineErrorHandler()
        self.ui = UIErrorHandler()

    def set_sink(self, callback):
        for h in self.all_handlers():
            h.set_sink(callback)

    def all_handlers(self):
        return (self.file, self.render, self.webengine, self.ui)

    def total_count(self):
        return sum(h.count() for h in self.all_handlers())

    def summary(self):
        return {h.name: h.count() for h in self.all_handlers()}

    def _get(self, category):
        if category == CATEGORY_FILE:
            return self.file
        if category == CATEGORY_RENDER:
            return self.render
        if category == CATEGORY_WEBENGINE:
            return self.webengine
        if category == CATEGORY_UI:
            return self.ui
        raise KeyError(f"Unknown error category: {category}")

    def report(self, category, context, exc, trace=""):
        self._get(category).report(context, exc, trace)

    def guard(self, category, context, fallback=None):
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


_DEFAULT_ROUTER = ErrorRouter()


def default_router():
    return _DEFAULT_ROUTER


_RE_LIST_CONT = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(\[[ xX]\]\s+)?")
_RE_SCRIPT_TAG = re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)


class MarkdownEditor(QPlainTextEdit):
    content_changed = pyqtSignal(str)

    def __init__(self, parent=None, font_family="Consolas",
                 font_size=13, errors=None):
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
            self.textChanged, self._emit_content_changed,
            context="textChanged",
        )

    def _emit_content_changed(self):
        try:
            self.content_changed.emit(self.toPlainText())
        except RuntimeError as e:
            self._errors.ui.report("emit_content", e, traceback.format_exc())

    def keyPressEvent(self, event):
        try:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._try_list_continuation(event):
                    return
        except Exception as e:
            self._errors.ui.report("list_continue", e, traceback.format_exc())
        super().keyPressEvent(event)

    def _try_list_continuation(self, event):
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


class MarkdownPreview(QWidget):
    link_clicked = pyqtSignal(str)

    def __init__(self, parent=None, theme="dark", errors=None):
        super().__init__(parent)
        self._errors = errors or _DEFAULT_ROUTER
        self.renderer = MarkdownRenderer()
        self.known_notes = set()
        self._mode = "web" if HAS_WEBENGINE else "text"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if HAS_WEBENGINE and QWebEngineView is not None:
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

    def set_known_notes(self, notes):
        try:
            self.known_notes = set(notes)
        except TypeError as e:
            self._errors.render.report("known_notes", e, traceback.format_exc())

    def render(self, text):
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
            clean = _RE_SCRIPT_TAG.sub("", html)
            try:
                self.view.setHtml(clean)
            except (RuntimeError, AttributeError) as e:
                self._errors.render.report("setHtml_fallback", e,
                                           traceback.format_exc())

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


class LivePreviewPane(QSplitter):
    _MIN_DEBOUNCE_MS = 70
    _MAX_DEBOUNCE_MS = 220
    _KNOWN_NOTES_TTL = 1.5

    def __init__(self, parent=None, vault=None, settings=None,
                 rel_path=None, errors=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._errors = errors or _DEFAULT_ROUTER
        self.vault = vault
        self.settings = settings
        self.rel_path = rel_path

        font_family = settings.get("editor_font", "Consolas") if settings else "Consolas"
        font_size = settings.get("editor_font_size", 13) if settings else 13

        self.editor = MarkdownEditor(
            self, font_family=font_family, font_size=font_size,
            errors=self._errors,
        )
        self.highlighter = MarkdownHighlighter(self.editor.document())
        self.preview = MarkdownPreview(self, errors=self._errors)

        self.addWidget(self.editor)
        self.addWidget(self.preview)
        self.setSizes([620, 620])

        self._pending = False
        self._last_hash = 0
        self._last_known = frozenset()
        self._known_cache = None
        self._known_cache_ts = 0.0
        self._render_count = 0
        self._skip_count = 0
        self._last_render_ms = 0.0

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._render_now)

        self._errors.ui.safe_connect(
            self.editor.content_changed, self._on_content_changed,
            context="content_changed",
        )

    def load(self, text):
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

    def text(self):
        try:
            return self.editor.toPlainText()
        except RuntimeError as e:
            self._errors.ui.report("read_text", e, traceback.format_exc())
            return ""

    def render_stats(self):
        return {
            "renders": self._render_count,
            "skips": self._skip_count,
            "last_render_ms": self._last_render_ms,
        }

    def _on_content_changed(self, _text):
        if not self.isVisible():
            self._pending = True
            return

        try:
            size = self.editor.document().characterCount()
        except (RuntimeError, AttributeError):
            size = 0

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

    @staticmethod
    def _cheap_hash(text):
        n = len(text)
        if n <= 512:
            return hash(text)
        return hash((n, text[:128], text[n // 2 - 64: n // 2 + 64], text[-128:]))

    def _current_known_notes(self):
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

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending:
            self._debounce.start(self._MIN_DEBOUNCE_MS)

    def hideEvent(self, event):
        super().hideEvent(event)
        try:
            self._debounce.stop()
        except RuntimeError:
            pass
        if not self._pending:
            self._pending = True


__all__ = [
    "MarkdownEditor", "MarkdownPreview", "LivePreviewPane",
    "ErrorRouter", "FileErrorHandler", "RenderErrorHandler",
    "WebEngineErrorHandler", "UIErrorHandler", "default_router",
    "CATEGORY_FILE", "CATEGORY_RENDER", "CATEGORY_WEBENGINE", "CATEGORY_UI",
]