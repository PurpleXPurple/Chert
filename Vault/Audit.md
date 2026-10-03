# The Four Missing Files

You're right — the GUI shell (`UI_Chert.py`, `Panels_Chert.py`, `Dialogs_Chert.py`, `Theme_Chert.py`) was the last pass. The four core files are still what they were in the PyQt6-only rewrite. Here they are as one clean set, with the BSP fix baked into `Graph_Chert.py`.

**What changed from the last paste:**
- `Graph_Chert.py`: `setBspTreeDepth(8)` removed (that was the warning).
- `Live_Preview.py`: no `PYQT6` import (already done).
- `Chert_Managers.py`: unchanged from the PyQt6-only rewrite.
- `Markdown_Chert.py`: unchanged.

---

## `Chert_Managers.py`

```python
"""
Chert_Managers.py — Qt compatibility, vault, indexes, settings.

PyQt6-only. No PyQt5 fallback, no enum shim.
"""

from __future__ import annotations

import os
import re
import sys
import json
import time
import errno
import sqlite3
import threading
import functools
import contextlib
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    Qt, QObject, QTimer, QPointF, QPoint, QRectF, QRect, QSize,
    QFileSystemWatcher, pyqtSignal, QUrl, QModelIndex, QThread,
)
from PyQt6.QtGui import (
    QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor,
    QPainter, QPen, QBrush, QKeySequence, QPixmap, QIcon, QImage,
    QImageReader, QMovie, QTransform, QPolygonF, QPainterPath,
    QTextDocument, QDesktopServices, QFontDatabase, QPalette,
    QLinearGradient, QAction, QFileSystemModel,
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTabWidget, QTreeView, QPlainTextEdit, QDockWidget,
    QListWidget, QListWidgetItem, QGraphicsScene,
    QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QGraphicsEllipseItem, QGraphicsSimpleTextItem,
    QGraphicsPixmapItem, QToolBar, QLineEdit, QLabel, QStatusBar,
    QMessageBox, QInputDialog, QMenu, QDialog, QDialogButtonBox,
    QFormLayout, QPushButton, QFileDialog, QTextEdit, QComboBox,
    QCheckBox, QSizePolicy, QFrame, QTabBar, QSlider,
)

HAS_WEBENGINE = False
QWebEngineView = None
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    pass


CHERT_DIR = sys.intern(".chert")
MD_EXT = sys.intern(".md")

WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|([^\]]+))?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([A-Za-z][A-Za-z0-9_/\-]*)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

SCHEMA_VERSION = 2

_READ_CHUNK = 1 << 16
_CHUNK_THRESHOLD = 1 << 20
_WATCH_COALESCE_MS = 150
_POLL_INTERVAL_MS = 2000
_POLL_MAX_MS = 30000
_DEFAULT_MAX_RECORDS = 64

_WIN_LONG_PATH_PREFIX = "\\\\?\\" if os.name == "nt" else ""


def diagnose_environment() -> dict:
    return {
        "python_version": sys.version,
        "python_bits": 64 if sys.maxsize > 2**32 else 32,
        "platform": sys.platform,
        "binding": "PyQt6",
        "webengine": HAS_WEBENGINE,
        "install_hint": "python -m pip install PyQt6 PyQt6-WebEngine",
    }


# ══════════════════════════════════════════════════════════════════════════
# Error handlers
# ══════════════════════════════════════════════════════════════════════════

class _ErrorRecord:
    __slots__ = ("category", "context", "exc_type", "exc_msg", "target", "ts")

    def __init__(self, category, context, exc, target=""):
        self.category = category
        self.context = context
        self.exc_type = type(exc).__name__ if exc else "None"
        self.exc_msg = str(exc) if exc else ""
        self.target = target
        self.ts = time.monotonic()


class _BaseHandler:
    __slots__ = ("name", "_ring", "_max", "_counts", "_sink", "_muted", "_lock")

    def __init__(self, name, max_records=_DEFAULT_MAX_RECORDS):
        self.name = name
        self._max = int(max_records)
        self._ring = []
        self._counts = {}
        self._sink = None
        self._muted = set()
        self._lock = threading.Lock()

    def set_sink(self, callback):
        self._sink = callback

    def mute(self, context):
        self._muted.add(context)

    def unmute(self, context):
        self._muted.discard(context)

    def report(self, context, exc, target=""):
        rec = _ErrorRecord(self.name, context, exc, target)
        with self._lock:
            self._ring.append(rec)
            if len(self._ring) > self._max:
                del self._ring[: len(self._ring) - self._max]
            self._counts[context] = self._counts.get(context, 0) + 1
        if self._sink and context not in self._muted:
            try:
                self._sink(rec)
            except Exception:
                pass

    def count(self, context=None):
        if context is None:
            return sum(self._counts.values())
        return self._counts.get(context, 0)

    def recent(self, n=10):
        with self._lock:
            return list(self._ring[-n:])

    def clear(self):
        with self._lock:
            self._ring.clear()
            self._counts.clear()


class VaultIOErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("vault_io", max_records)

    def safe_read(self, path, default=""):
        try:
            p = os.fspath(path) if isinstance(path, Path) else path
            size = os.path.getsize(p)
            if size < _CHUNK_THRESHOLD:
                with open(p, "r", encoding="utf-8",
                          errors="surrogateescape") as f:
                    return f.read()
            chunks = []
            with open(p, "r", encoding="utf-8",
                      errors="surrogateescape") as f:
                while True:
                    buf = f.read(_READ_CHUNK)
                    if not buf:
                        break
                    chunks.append(buf)
            return "".join(chunks)
        except FileNotFoundError as e:
            self.report("read_missing", e, str(path))
            return default
        except PermissionError as e:
            self.report("read_permission", e, str(path))
            return default
        except (OSError, UnicodeDecodeError, ValueError) as e:
            self.report("read_other", e, str(path))
            return default

    def safe_write(self, path, content):
        tmp = None
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".chert-tmp")
            with open(tmp, "w", encoding="utf-8",
                      errors="surrogateescape") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
            return True
        except (OSError, UnicodeEncodeError, ValueError) as e:
            self.report("write", e, str(path))
            if tmp is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
            return False

    def safe_mkdir(self, path):
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except (OSError, ValueError) as e:
            self.report("mkdir", e, str(path))
            return False

    def safe_rename(self, old, new):
        try:
            Path(new).parent.mkdir(parents=True, exist_ok=True)
            os.replace(str(old), str(new))
            return True
        except (OSError, ValueError) as e:
            self.report("rename", e, f"{old} -> {new}")
            return False

    def safe_delete(self, path):
        try:
            os.unlink(str(path))
            return True
        except FileNotFoundError:
            return True
        except OSError as e:
            self.report("delete", e, str(path))
            return False


class VaultPathErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("vault_path", max_records)

    def safe_relative_to(self, path, root):
        try:
            return str(Path(path).relative_to(root)).replace("\\", "/")
        except (ValueError, OSError) as e:
            self.report("relative", e, f"{path} ~ {root}")
            return str(path).replace("\\", "/")

    def long_path_safe(self, path):
        if os.name != "nt":
            return str(path)
        s = str(path)
        if len(s) < 240 or s.startswith(_WIN_LONG_PATH_PREFIX):
            return s
        if s.startswith("\\\\"):
            return _WIN_LONG_PATH_PREFIX + "UNC" + s[1:]
        return _WIN_LONG_PATH_PREFIX + os.path.abspath(s)

    def safe_resolve(self, path):
        try:
            return Path(self.long_path_safe(path)).resolve()
        except (OSError, RuntimeError, ValueError) as e:
            self.report("resolve", e, str(path))
            return Path(path)


class VaultWatcherErrorHandler(_BaseHandler):
    __slots__ = ("_poll_paths",)

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("vault_watcher", max_records)
        self._poll_paths: list[str] = []

    def safe_add_path(self, watcher, path):
        try:
            if watcher.addPath(str(path)):
                return True
            self._poll_paths.append(str(path))
            self.report("watcher_full",
                        RuntimeError("addPath returned False"), str(path))
            return False
        except (RuntimeError, OSError) as e:
            self._poll_paths.append(str(path))
            self.report("watcher_error", e, str(path))
            return False

    def safe_remove_paths(self, watcher, paths):
        try:
            if paths:
                watcher.removePaths(list(paths))
            return True
        except RuntimeError as e:
            self.report("watcher_remove", e)
            return False

    @property
    def polling_paths(self):
        return list(self._poll_paths)

    def clear_polling(self):
        self._poll_paths.clear()


class VaultScanErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("vault_scan", max_records)

    def safe_walk(self, root, prune_prefixes=(".", "__pycache__")):
        found: list[Path] = []
        try:
            for base, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs
                           if not any(d.startswith(p)
                                      for p in prune_prefixes)]
                base_p = Path(base)
                for f in files:
                    try:
                        if f.lower().endswith(MD_EXT):
                            found.append(base_p / f)
                    except (OSError, ValueError) as e:
                        self.report("entry", e, f)
        except (OSError, PermissionError) as e:
            self.report("walk", e, str(root))
        return found

    def safe_list_dirs(self, root, prune_prefixes=(".", "__pycache__")):
        dirs_found: list[Path] = []
        try:
            for base, dirs, _ in os.walk(root):
                dirs[:] = [d for d in dirs
                           if not any(d.startswith(p)
                                      for p in prune_prefixes)]
                dirs_found.append(Path(base))
        except OSError as e:
            self.report("walk_dirs", e, str(root))
        return dirs_found


class SQLiteErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("sqlite", max_records)

    def safe_connect(self, db_path, isolation_level=None):
        try:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path),
                                   isolation_level=isolation_level,
                                   check_same_thread=False,
                                   timeout=5.0)
            conn.row_factory = sqlite3.Row
            for pragma in (
                "journal_mode=WAL",
                "synchronous=NORMAL",
                "temp_store=MEMORY",
                "mmap_size=67108864",
                "foreign_keys=ON",
            ):
                with contextlib.suppress(sqlite3.OperationalError):
                    conn.execute(f"PRAGMA {pragma}")
            return conn
        except (sqlite3.Error, OSError) as e:
            self.report("connect", e, str(db_path))
            return None

    def safe_execute(self, conn, sql, params=()):
        if conn is None:
            return None
        try:
            return conn.execute(sql, params)
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "locked" in msg or "busy" in msg:
                self.report("execute_locked", e, sql[:80])
            else:
                self.report("execute", e, sql[:80])
            return None
        except sqlite3.Error as e:
            self.report("execute_other", e, sql[:80])
            return None

    @contextlib.contextmanager
    def transaction(self, conn):
        if conn is None:
            yield None
            return
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except sqlite3.Error as e:
            with contextlib.suppress(sqlite3.Error):
                conn.execute("ROLLBACK")
            self.report("transaction", e)
            yield None


class SearchErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("search", max_records)

    def safe_match(self, conn, sql, params, default=None):
        if conn is None:
            return default if default is not None else []
        try:
            cur = conn.execute(sql, params)
            return cur.fetchall()
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "syntax" in msg or "malformed" in msg:
                self.report("match_syntax", e, str(params)[:80])
            else:
                self.report("match", e, str(params)[:80])
            return default if default is not None else []

    def sanitize_query(self, query):
        try:
            tokens = re.findall(r"\w+", query)
            return " ".join(f'"{t}"' for t in tokens) if tokens else ""
        except (TypeError, ValueError) as e:
            self.report("sanitize", e, str(query)[:80])
            return ""


class ConfigErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("config", max_records)

    def safe_load(self, path, default=None):
        if default is None:
            default = {}
        try:
            with open(str(path), "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except (OSError, json.JSONDecodeError, ValueError) as e:
            self.report("load", e, str(path))
            return default

    def safe_save(self, path, data):
        tmp = None
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
            return True
        except (OSError, TypeError, ValueError) as e:
            self.report("save", e, str(path))
            if tmp is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
            return False


class SignalErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("signal", max_records)

    def safe_emit(self, signal, *args):
        try:
            signal.emit(*args)
            return True
        except (RuntimeError, TypeError) as e:
            self.report("emit", e)
            return False

    def safe_connect(self, signal, slot, context="connect"):
        try:
            signal.connect(slot)
            return True
        except (TypeError, RuntimeError) as e:
            self.report(context, e)
            return False

    def safe_disconnect(self, signal, slot=None):
        try:
            if slot is None:
                signal.disconnect()
            else:
                signal.disconnect(slot)
            return True
        except (TypeError, RuntimeError) as e:
            self.report("disconnect", e)
            return False


class ResourceErrorHandler(_BaseHandler):
    __slots__ = ()

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("resource", max_records)

    def check_memory(self, threshold_bytes: int = 512 * 1024 * 1024) -> bool:
        try:
            import psutil
            avail = psutil.virtual_memory().available
            if avail < threshold_bytes:
                self.report("low_memory",
                            RuntimeError(f"only {avail} bytes free"))
                return False
            return True
        except ImportError:
            return True
        except Exception as e:
            self.report("memory_check", e)
            return True

    def safe_call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except MemoryError as e:
            self.report("memory", e, getattr(fn, "__name__", "callable"))
            return None
        except OSError as e:
            if e.errno in (errno.EMFILE, errno.ENFILE, errno.ENOMEM, errno.ENOSPC):
                self.report("os_limit", e, getattr(fn, "__name__", "callable"))
                return None
            raise


class MigrationErrorHandler(_BaseHandler):
    __slots__ = ("_raised",)

    def __init__(self, max_records=_DEFAULT_MAX_RECORDS):
        super().__init__("migration", max_records)
        self._raised = False

    def ensure_schema(self, conn, db_name, target_version=SCHEMA_VERSION):
        if conn is None:
            return False
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(db TEXT PRIMARY KEY, version INTEGER NOT NULL)"
            )
            row = conn.execute(
                "SELECT version FROM schema_version WHERE db = ?", (db_name,)
            ).fetchone()
            current = row["version"] if row else 0
            if current > target_version:
                self.report("future_schema",
                            RuntimeError(f"{db_name} v{current} > v{target_version}"))
                return False
            if current == target_version:
                return True
            self.report("migrate",
                        RuntimeError(f"{db_name} {current} -> {target_version}"))
            conn.execute(
                "INSERT INTO schema_version (db, version) VALUES (?, ?) "
                "ON CONFLICT(db) DO UPDATE SET version = excluded.version",
                (db_name, target_version),
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            if not self._raised:
                self._raised = True
                self.report("ensure", e, db_name)
            return False


class ManagerErrorRouter:
    __slots__ = ("io", "path", "watcher", "scan", "sqlite",
                 "search", "config", "signal", "resource", "migration")

    def __init__(self):
        self.io = VaultIOErrorHandler()
        self.path = VaultPathErrorHandler()
        self.watcher = VaultWatcherErrorHandler()
        self.scan = VaultScanErrorHandler()
        self.sqlite = SQLiteErrorHandler()
        self.search = SearchErrorHandler()
        self.config = ConfigErrorHandler()
        self.signal = SignalErrorHandler()
        self.resource = ResourceErrorHandler()
        self.migration = MigrationErrorHandler()

    def all_handlers(self):
        return (self.io, self.path, self.watcher, self.scan, self.sqlite,
                self.search, self.config, self.signal, self.resource,
                self.migration)

    def set_sink(self, callback):
        for h in self.all_handlers():
            h.set_sink(callback)

    def total_count(self):
        return sum(h.count() for h in self.all_handlers())

    def summary(self):
        return {h.name: h.count() for h in self.all_handlers()}


_MANAGER_ROUTER = ManagerErrorRouter()


def manager_router():
    return _MANAGER_ROUTER


# ══════════════════════════════════════════════════════════════════════════
# Lazy loaders
# ══════════════════════════════════════════════════════════════════════════

class LazySQLiteConnection:
    __slots__ = ("db_path", "_tls", "_all", "_lock", "_errors")

    def __init__(self, db_path, errors: SQLiteErrorHandler):
        self.db_path = str(db_path)
        self._tls = threading.local()
        self._all = []
        self._lock = threading.Lock()
        self._errors = errors

    def get(self):
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = self._errors.safe_connect(self.db_path)
            if conn is not None:
                self._tls.conn = conn
                with self._lock:
                    self._all.append(conn)
        return conn

    def close_all(self):
        with self._lock:
            for c in self._all:
                with contextlib.suppress(Exception):
                    c.close()
            self._all.clear()
        self._tls = threading.local()


class LazyValue:
    __slots__ = ("_factory", "_value", "_initialized", "_lock")

    def __init__(self, factory):
        self._factory = factory
        self._value = None
        self._initialized = False
        self._lock = threading.Lock()

    def get(self):
        if self._initialized:
            return self._value
        with self._lock:
            if not self._initialized:
                self._value = self._factory()
                self._initialized = True
        return self._value

    def reset(self):
        with self._lock:
            self._value = None
            self._initialized = False


# ══════════════════════════════════════════════════════════════════════════
# Path utilities
# ══════════════════════════════════════════════════════════════════════════

@functools.lru_cache(maxsize=4096)
def _normalize_relpath(path_str: str) -> str:
    return sys.intern(path_str.replace("\\", "/"))


@functools.lru_cache(maxsize=2048)
def _normalize_abs(path_str: str) -> str:
    return os.fspath(Path(path_str))


# ══════════════════════════════════════════════════════════════════════════
# VaultManager
# ══════════════════════════════════════════════════════════════════════════

class VaultManager(QObject):
    file_changed = pyqtSignal(str)
    vault_reloaded = pyqtSignal()

    def __init__(self, vault_path):
        super().__init__()
        self._errors = _MANAGER_ROUTER
        self.vault_path = self._errors.path.safe_resolve(vault_path)
        self.watcher = None
        self._known = set()
        self._watch_dirs = set()
        self._scanned = False
        self._watching = False
        self._pending_events = []
        self._poll_index = 0

        self._watch_coalesce_timer = QTimer()
        self._watch_coalesce_timer.setSingleShot(True)
        self._watch_coalesce_timer.setInterval(_WATCH_COALESCE_MS)
        self._errors.signal.safe_connect(
            self._watch_coalesce_timer.timeout, self._flush_events,
            context="coalesce_timeout",
        )

        self._rescan_timer = QTimer()
        self._rescan_timer.setSingleShot(True)
        self._rescan_timer.setInterval(400)
        self._errors.signal.safe_connect(
            self._rescan_timer.timeout, self._do_rescan,
            context="rescan_timeout",
        )

        self._poll_timer = QTimer()
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._errors.signal.safe_connect(
            self._poll_timer.timeout, self._poll_step,
            context="poll_timeout",
        )

    def list_notes(self):
        if not self._scanned:
            self._scan()
        return sorted(self._known)

    def watch(self):
        if self._watching:
            return
        if self.watcher is None:
            self.watcher = QFileSystemWatcher()
            self._errors.signal.safe_connect(
                self.watcher.directoryChanged, self._on_dir_changed,
                context="dir_changed",
            )
        self._refresh_watches()
        self._watching = True
        if self._errors.watcher.polling_paths:
            self._poll_timer.start()

    def rel_path(self, abs_path):
        rel = self._errors.path.safe_relative_to(abs_path, self.vault_path)
        return _normalize_relpath(rel)

    def abs_path(self, rel):
        return self.vault_path / rel.replace("/", os.sep)

    def read(self, rel):
        return self._errors.io.safe_read(self.abs_path(rel), default="")

    def write(self, rel, content):
        return self._errors.io.safe_write(self.abs_path(rel), content)

    def create(self, rel):
        p = self.abs_path(rel)
        if p.exists():
            return False
        return self._errors.io.safe_write(p, "")

    def delete(self, rel):
        return self._errors.io.safe_delete(self.abs_path(rel))

    def rename(self, old_rel, new_rel):
        return self._errors.io.safe_rename(
            self.abs_path(old_rel), self.abs_path(new_rel),
        )

    def _scan(self):
        found = self._errors.scan.safe_walk(self.vault_path)
        self._known = {str(p) for p in found}
        self._scanned = True

    def _refresh_watches(self):
        if self.watcher is None:
            return
        dirs = self._errors.scan.safe_list_dirs(self.vault_path)
        new_set = {str(d) for d in dirs}
        to_add = new_set - self._watch_dirs
        to_remove = self._watch_dirs - new_set
        self._errors.watcher.safe_remove_paths(self.watcher, to_remove)
        for d in to_add:
            self._errors.watcher.safe_add_path(self.watcher, d)
        self._watch_dirs = new_set

    def _on_dir_changed(self, path):
        self._pending_events.append(path)
        if not self._watch_coalesce_timer.isActive():
            self._watch_coalesce_timer.start()
        self._rescan_timer.start()

    def _flush_events(self):
        events = self._pending_events
        self._pending_events = []
        for path in events:
            self._errors.signal.safe_emit(self.file_changed, path)

    def _do_rescan(self):
        old = set(self._known)
        self._scan()
        new = set(self._known)
        if old != new:
            self._refresh_watches()
            self._errors.signal.safe_emit(self.vault_reloaded)

    def _poll_step(self):
        try:
            old = set(self._known)
            self._scan()
            if old != set(self._known):
                self._rescan_timer.start()
                self._poll_timer.setInterval(_POLL_INTERVAL_MS)
            else:
                next_interval = min(self._poll_timer.interval() * 2,
                                    _POLL_MAX_MS)
                self._poll_timer.setInterval(next_interval)
        except Exception as e:
            self._errors.scan.report("poll", e)


# ══════════════════════════════════════════════════════════════════════════
# BacklinkIndex
# ══════════════════════════════════════════════════════════════════════════

class BacklinkIndex:
    __slots__ = ("db_path", "_pool", "_errors", "_migration")

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self._errors = _MANAGER_ROUTER
        self._pool = LazySQLiteConnection(self.db_path, self._errors.sqlite)
        self._migration = LazyValue(self._ensure_schema)

    def _ensure_schema(self):
        conn = self._pool.get()
        if conn is None:
            return False
        self._errors.migration.ensure_schema(conn, "backlinks")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS links (
                source  TEXT NOT NULL,
                target  TEXT NOT NULL,
                alias   TEXT,
                context TEXT,
                PRIMARY KEY (source, target, alias)
            );
            CREATE INDEX IF NOT EXISTS idx_links_target ON links(target);
            CREATE INDEX IF NOT EXISTS idx_links_source ON links(source);
        """)
        conn.commit()
        return True

    def index_file(self, source, content):
        self._migration.get()
        conn = self._pool.get()
        if conn is None:
            return
        try:
            conn.execute("DELETE FROM links WHERE source = ?", (source,))
            rows = []
            for m in WIKILINK_RE.finditer(content):
                target = sys.intern(m.group(1).strip())
                alias = sys.intern((m.group(2) or target).strip())
                start = max(0, m.start() - 90)
                end = min(len(content), m.end() + 90)
                ctx = content[start:end].replace("\n", " ").strip()
                rows.append((source, target, alias, ctx))
            if rows:
                conn.executemany(
                    "INSERT OR IGNORE INTO links "
                    "(source, target, alias, context) VALUES (?, ?, ?, ?)",
                    rows,
                )
            conn.commit()
        except sqlite3.Error as e:
            self._errors.sqlite.report("index_file", e, source)

    def remove_file(self, source):
        conn = self._pool.get()
        if conn is None:
            return
        try:
            conn.execute("DELETE FROM links WHERE source = ?", (source,))
            conn.commit()
        except sqlite3.Error as e:
            self._errors.sqlite.report("remove_file", e, source)

    def backlinks(self, target_rel):
        self._migration.get()
        conn = self._pool.get()
        if conn is None:
            return []
        stem = sys.intern(Path(target_rel).stem)
        cur = self._errors.sqlite.safe_execute(
            conn,
            "SELECT source, alias, context FROM links "
            "WHERE target = ? OR target = ?",
            (target_rel, stem),
        )
        if cur is None:
            return []
        return [{"source": r[0], "alias": r[1], "context": r[2]}
                for r in cur.fetchall()]

    def outgoing(self, source_rel):
        conn = self._pool.get()
        if conn is None:
            return []
        cur = self._errors.sqlite.safe_execute(
            conn,
            "SELECT DISTINCT target FROM links WHERE source = ?",
            (source_rel,),
        )
        if cur is None:
            return []
        return [r[0] for r in cur.fetchall()]

    def all_edges(self):
        conn = self._pool.get()
        if conn is None:
            return []
        cur = self._errors.sqlite.safe_execute(
            conn, "SELECT DISTINCT source, target FROM links",
        )
        if cur is None:
            return []
        return [(r[0], r[1]) for r in cur.fetchall()]

    def close(self):
        self._pool.close_all()

    close_all = close


# ══════════════════════════════════════════════════════════════════════════
# SearchIndex
# ══════════════════════════════════════════════════════════════════════════

class SearchIndex:
    __slots__ = ("db_path", "_pool", "_errors", "_migration", "_fts")

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self._errors = _MANAGER_ROUTER
        self._pool = LazySQLiteConnection(self.db_path, self._errors.sqlite)
        self._fts = True
        self._migration = LazyValue(self._ensure_schema)

    def _ensure_schema(self):
        conn = self._pool.get()
        if conn is None:
            return False
        self._errors.migration.ensure_schema(conn, "search")
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts
                USING fts5(path UNINDEXED, title, body, tokenize='unicode61')
            """)
            self._fts = True
        except sqlite3.OperationalError:
            self._fts = False
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes_simple (
                    path TEXT PRIMARY KEY, title TEXT, body TEXT
                )
            """)
        conn.commit()
        return True

    def index(self, rel, title, body):
        self._migration.get()
        conn = self._pool.get()
        if conn is None:
            return
        try:
            if self._fts:
                conn.execute("DELETE FROM notes_fts WHERE path = ?", (rel,))
                conn.execute(
                    "INSERT INTO notes_fts (path, title, body) VALUES (?, ?, ?)",
                    (rel, title, body),
                )
            else:
                conn.execute(
                    "INSERT OR REPLACE INTO notes_simple "
                    "(path, title, body) VALUES (?, ?, ?)",
                    (rel, title, body),
                )
            conn.commit()
        except sqlite3.Error as e:
            self._errors.sqlite.report("index_search", e, rel)

    def remove(self, rel):
        conn = self._pool.get()
        if conn is None:
            return
        try:
            table = "notes_fts" if self._fts else "notes_simple"
            conn.execute(f"DELETE FROM {table} WHERE path = ?", (rel,))
            conn.commit()
        except sqlite3.Error as e:
            self._errors.sqlite.report("remove_search", e, rel)

    def search(self, query, limit=40):
        self._migration.get()
        conn = self._pool.get()
        if conn is None:
            return []
        q = query.strip()
        if not q:
            return []
        if self._fts:
            safe = self._errors.search.sanitize_query(q)
            if not safe:
                return []
            rows = self._errors.search.safe_match(conn, """
                SELECT path, title,
                       snippet(notes_fts, 2, '<b>', '</b>', '…', 20),
                       bm25(notes_fts)
                FROM notes_fts
                WHERE notes_fts MATCH ?
                ORDER BY bm25(notes_fts) LIMIT ?
            """, (safe, limit))
            return [{"path": r[0], "title": r[1],
                     "snippet": r[2], "rank": r[3]} for r in rows]
        else:
            like = f"%{q}%"
            rows = self._errors.search.safe_match(conn, """
                SELECT path, title, body FROM notes_simple
                WHERE body LIKE ? OR title LIKE ? LIMIT ?
            """, (like, like, limit))
            return [{"path": r[0], "title": r[1],
                     "snippet": r[2][:200], "rank": 0} for r in rows]

    def close(self):
        self._pool.close_all()

    close_all = close


# ══════════════════════════════════════════════════════════════════════════
# TagIndex
# ══════════════════════════════════════════════════════════════════════════

class TagIndex:
    __slots__ = ("db_path", "_pool", "_errors", "_migration")

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self._errors = _MANAGER_ROUTER
        self._pool = LazySQLiteConnection(self.db_path, self._errors.sqlite)
        self._migration = LazyValue(self._ensure_schema)

    def _ensure_schema(self):
        conn = self._pool.get()
        if conn is None:
            return False
        self._errors.migration.ensure_schema(conn, "tags")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tags (
                path TEXT NOT NULL,
                tag  TEXT NOT NULL,
                PRIMARY KEY (path, tag)
            );
            CREATE INDEX IF NOT EXISTS idx_tag ON tags(tag);
        """)
        conn.commit()
        return True

    def index_file(self, source, content):
        self._migration.get()
        conn = self._pool.get()
        if conn is None:
            return
        try:
            conn.execute("DELETE FROM tags WHERE path = ?", (source,))
            cleaned = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
            cleaned = re.sub(r"`[^`]*`", "", cleaned)
            tags = {sys.intern(t.lower()) for t in TAG_RE.findall(cleaned)}
            fm = FRONTMATTER_RE.match(content)
            if fm:
                body = fm.group(1)
                in_tags = False
                for line in body.splitlines():
                    s = line.strip()
                    if s.startswith("tags:"):
                        rest = s[5:].strip()
                        if rest.startswith("[") and rest.endswith("]"):
                            for t in rest[1:-1].split(","):
                                tags.add(sys.intern(
                                    t.strip().strip("\"'").lstrip("#").lower()))
                        elif rest:
                            tags.add(sys.intern(rest.lstrip("#").lower()))
                        else:
                            in_tags = True
                    elif in_tags and s.startswith("-"):
                        tags.add(sys.intern(
                            s[1:].strip().strip("\"'").lstrip("#").lower()))
                    elif in_tags and s and not s.startswith("-"):
                        in_tags = False
            tags.discard("")
            if tags:
                conn.executemany(
                    "INSERT OR IGNORE INTO tags (path, tag) VALUES (?, ?)",
                    [(source, t) for t in tags],
                )
            conn.commit()
        except sqlite3.Error as e:
            self._errors.sqlite.report("index_tags", e, source)

    def all_tags(self):
        self._migration.get()
        conn = self._pool.get()
        if conn is None:
            return []
        cur = self._errors.sqlite.safe_execute(conn, """
            SELECT tag, COUNT(*) AS n FROM tags
            GROUP BY tag ORDER BY n DESC, tag
        """)
        if cur is None:
            return []
        return cur.fetchall()

    def files_for_tag(self, tag):
        conn = self._pool.get()
        if conn is None:
            return []
        cur = self._errors.sqlite.safe_execute(
            conn, "SELECT path FROM tags WHERE tag = ?", (tag.lower(),),
        )
        if cur is None:
            return []
        return [r[0] for r in cur.fetchall()]

    def close(self):
        self._pool.close_all()

    close_all = close


# ══════════════════════════════════════════════════════════════════════════
# ChertSettings
# ══════════════════════════════════════════════════════════════════════════

DEFAULT_SETTINGS = {
    "theme": "dark",
    "editor_font": "Consolas",
    "editor_font_size": 13,
    "preview_font_size": 15,
    "line_wrap": True,
    "tab_width": 4,
    "graph_max_nodes": 500,
}


class ChertSettings:
    __slots__ = ("vault", "data", "path", "_errors", "_dirty")

    def __init__(self, vault=None):
        self.vault = vault
        self._errors = _MANAGER_ROUTER
        self.data = dict(DEFAULT_SETTINGS)
        self.path = None
        self._dirty = False
        if vault:
            self.path = vault_settings_dir(vault) / "settings.json"
            self.load()

    def load(self):
        if not self.path:
            return
        loaded = self._errors.config.safe_load(self.path, {})
        if loaded:
            self.data.update(loaded)
        self._dirty = False

    def save(self, force=False):
        if not self.path:
            return
        if not force and not self._dirty:
            return
        self._errors.config.safe_save(self.path, self.data)
        self._dirty = False

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        if self.data.get(key) == value:
            return
        self.data[key] = value
        self._dirty = True

    def flush(self):
        self.save(force=False)

    def __del__(self):
        with contextlib.suppress(Exception):
            self.save(force=False)


_config_cache = None
_config_lock = threading.Lock()


def vault_settings_dir(vault):
    d = Path(vault) / CHERT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def app_config_dir():
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA",
                                   Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    d = base / "Chert"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_app_config():
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    with _config_lock:
        if _config_cache is not None:
            return _config_cache
        p = app_config_dir() / "config.json"
        loaded = _MANAGER_ROUTER.config.safe_load(p, {"recent_vaults": []})
        if "recent_vaults" not in loaded:
            loaded["recent_vaults"] = []
        _config_cache = loaded
        return _config_cache


def save_app_config(cfg):
    global _config_cache
    with _config_lock:
        _config_cache = dict(cfg)
        p = app_config_dir() / "config.json"
        _MANAGER_ROUTER.config.safe_save(p, _config_cache)


__all__ = [
    "Qt", "QObject", "QTimer", "QPointF", "QPoint", "QRectF", "QRect",
    "QSize", "QFileSystemWatcher", "pyqtSignal", "QUrl", "QModelIndex",
    "QThread", "QColor", "QFont", "QSyntaxHighlighter", "QTextCharFormat",
    "QTextCursor", "QPainter", "QPen", "QBrush", "QKeySequence", "QPixmap",
    "QIcon", "QImage", "QImageReader", "QMovie", "QTransform", "QPolygonF",
    "QPainterPath", "QTextDocument", "QDesktopServices", "QFontDatabase",
    "QPalette", "QLinearGradient", "QApplication", "QMainWindow", "QWidget",
    "QVBoxLayout", "QHBoxLayout", "QSplitter", "QTabWidget", "QTreeView",
    "QPlainTextEdit", "QDockWidget", "QListWidget", "QListWidgetItem",
    "QFileSystemModel", "QGraphicsScene", "QGraphicsView", "QGraphicsItem",
    "QGraphicsLineItem", "QGraphicsEllipseItem", "QGraphicsSimpleTextItem",
    "QGraphicsPixmapItem", "QToolBar", "QLineEdit", "QLabel", "QStatusBar",
    "QMessageBox", "QInputDialog", "QMenu", "QDialog", "QDialogButtonBox",
    "QFormLayout", "QPushButton", "QFileDialog", "QTextEdit", "QComboBox",
    "QCheckBox", "QSizePolicy", "QFrame", "QTabBar", "QSlider", "QAction",
    "QWebEngineView", "HAS_WEBENGINE",
    "CHERT_DIR", "MD_EXT", "WIKILINK_RE", "TAG_RE", "HEADING_RE",
    "FRONTMATTER_RE", "SCHEMA_VERSION",
    "VaultManager", "BacklinkIndex", "SearchIndex", "TagIndex",
    "ChertSettings",
    "vault_settings_dir", "app_config_dir",
    "load_app_config", "save_app_config", "DEFAULT_SETTINGS",
    "diagnose_environment",
    "_BaseHandler", "_ErrorRecord", "ManagerErrorRouter",
    "VaultIOErrorHandler", "VaultPathErrorHandler", "VaultWatcherErrorHandler",
    "VaultScanErrorHandler", "SQLiteErrorHandler", "SearchErrorHandler",
    "ConfigErrorHandler", "SignalErrorHandler", "ResourceErrorHandler",
    "MigrationErrorHandler", "manager_router",
    "LazySQLiteConnection", "LazyValue",
]
```

---

## `Markdown_Chert.py`

```python
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
```

---

## `Live_Preview.py`

```python
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
```

---

## `Graph_Chert.py`

The BSP fix is in — `setBspTreeDepth(8)` removed.

```python
"""
Graph_Chert.py — Force-directed note graph.

Barnes-Hut quadtree, Qt scene tuning, image/GIF nodes, Obsidian-style
filters, 24 graph construction methods via GraphBuilder.

BSP note: QGraphicsScene.setItemIndexMethod(NoIndex) is used because the
scene has items that move every frame. setBspTreeDepth is only valid when
the scene uses BspTreeIndex — the two are mutually exclusive.
"""

import math
import random
import time
import traceback
from collections import defaultdict, deque
from pathlib import Path

from Chert_Managers import (
    Qt, QTimer, QPointF, QRectF, QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QGraphicsPixmapItem, QLabel, QPushButton, QSlider, QCheckBox,
    QComboBox, QLineEdit, QMenu, QColor, QFont, QPen, QBrush, QPainter,
    QPixmap, QImage, QImageReader, QMovie, QSize, QPoint,
    QPolygonF, QFrame, pyqtSignal,
)


CATEGORY_GRAPH = "graph"
CATEGORY_IMAGE = "image"
CATEGORY_LAYOUT = "layout"
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
        self._max = max_records
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
            del self._ring[:len(self._ring) - self._max]
        self._counts[context] = self._counts.get(context, 0) + 1
        if self._on_error and context not in self._muted:
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


class GraphErrorHandler(_BaseHandler):
    def __init__(self, max_records=64):
        super().__init__(CATEGORY_GRAPH, max_records)

    def safe_add_node(self, view, node_id, label, degree=0):
        try:
            return view.add_node(node_id, label, degree)
        except (RuntimeError, ValueError, KeyError) as e:
            self.report("add_node", e, traceback.format_exc())
            return None

    def safe_add_edge(self, view, source_id, target_id):
        try:
            view.add_edge(source_id, target_id)
            return True
        except (RuntimeError, ValueError, KeyError) as e:
            self.report("add_edge", e, traceback.format_exc())
            return False


class ImageErrorHandler(_BaseHandler):
    def __init__(self, max_records=64):
        super().__init__(CATEGORY_IMAGE, max_records)

    def safe_load_pixmap(self, path, max_size=64):
        try:
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            if max_size > 0:
                reader.setScaledSize(QSize(max_size, max_size))
            img = reader.read()
            if img.isNull():
                raise ValueError(f"QImageReader returned null for {path}")
            return QPixmap.fromImage(img)
        except Exception as e:
            self.report("load_pixmap", e, traceback.format_exc())
            return None

    def safe_movie(self, path):
        try:
            movie = QMovie(str(path))
            if not movie.isValid():
                raise ValueError(f"Invalid GIF: {path}")
            return movie
        except Exception as e:
            self.report("load_movie", e, traceback.format_exc())
            return None

    @staticmethod
    def supported_formats():
        try:
            return sorted(
                bytes(f).decode("ascii", "replace")
                for f in QImageReader.supportedImageFormats()
            )
        except Exception:
            return ["png", "jpg", "jpeg", "bmp", "gif", "webp"]


class LayoutErrorHandler(_BaseHandler):
    def __init__(self, max_records=64):
        super().__init__(CATEGORY_LAYOUT, max_records)

    def safe_tick(self, view):
        try:
            view._tick_internal()
        except (ArithmeticError, ValueError, OverflowError,
                RecursionError, MemoryError) as e:
            self.report("tick", e, traceback.format_exc())


class GraphUIErrorHandler(_BaseHandler):
    def __init__(self, max_records=64):
        super().__init__(CATEGORY_UI, max_records)

    def safe_connect(self, signal, slot, context="connect"):
        try:
            signal.connect(slot)
            return True
        except (TypeError, RuntimeError) as e:
            self.report(context, e, traceback.format_exc())
            return False

    def safe_slider(self, slider, value, context="slider"):
        try:
            slider.setValue(int(value))
            return True
        except (RuntimeError, TypeError, ValueError) as e:
            self.report(context, e, traceback.format_exc())
            return False


class ErrorRouter:
    __slots__ = ("graph", "image", "layout", "ui")

    def __init__(self):
        self.graph = GraphErrorHandler()
        self.image = ImageErrorHandler()
        self.layout = LayoutErrorHandler()
        self.ui = GraphUIErrorHandler()

    def set_sink(self, callback):
        for h in self.all_handlers():
            h.set_sink(callback)

    def all_handlers(self):
        return (self.graph, self.image, self.layout, self.ui)

    def total_count(self):
        return sum(h.count() for h in self.all_handlers())

    def summary(self):
        return {h.name: h.count() for h in self.all_handlers()}


_DEFAULT_ROUTER = ErrorRouter()


def default_router():
    return _DEFAULT_ROUTER


# ══════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════

class RelationType:
    LINK = "link"
    MENTION = "mention"
    BACKLINK = "backlink"
    RELATION = "relation"
    EMBED = "embed"
    TAG = "tag"

    COLORS = {
        LINK: QColor(90, 130, 200, 180),
        MENTION: QColor(200, 140, 90, 180),
        BACKLINK: QColor(130, 200, 130, 180),
        RELATION: QColor(200, 200, 90, 180),
        EMBED: QColor(180, 90, 200, 180),
        TAG: QColor(90, 200, 200, 180),
    }

    @classmethod
    def color(cls, rel_type):
        return cls.COLORS.get(rel_type, cls.COLORS[cls.LINK])


class GraphConfig:
    __slots__ = (
        "repulsion", "spring_length", "spring_k", "damping",
        "centering", "max_velocity", "iterations_per_tick",
        "barnes_hut", "barnes_hut_theta", "barnes_hut_threshold",
        "node_base_size", "node_max_size", "link_base_width",
        "link_max_width", "text_fade_threshold", "show_arrows",
        "show_labels", "lod_enabled", "lod_threshold",
        "animate_timelapse", "timelapse_speed",
    )

    def __init__(self):
        self.repulsion = 12000.0
        self.spring_length = 140.0
        self.spring_k = 0.05
        self.damping = 0.82
        self.centering = 0.004
        self.max_velocity = 14.0
        self.iterations_per_tick = 1
        self.barnes_hut = True
        self.barnes_hut_theta = 0.9
        self.barnes_hut_threshold = 50
        self.node_base_size = 6.0
        self.node_max_size = 24.0
        self.link_base_width = 1.2
        self.link_max_width = 3.5
        self.text_fade_threshold = 0.55
        self.show_arrows = False
        self.show_labels = True
        self.lod_enabled = True
        self.lod_threshold = 0.4
        self.animate_timelapse = False
        self.timelapse_speed = 2.0


class GraphFilter:
    __slots__ = (
        "search_query", "show_tags", "show_attachments",
        "show_orphans", "existing_only", "min_degree",
        "max_degree", "date_from", "date_to", "properties",
    )

    def __init__(self):
        self.search_query = ""
        self.show_tags = True
        self.show_attachments = True
        self.show_orphans = True
        self.existing_only = True
        self.min_degree = 0
        self.max_degree = 10_000
        self.date_from = None
        self.date_to = None
        self.properties = {}

    def matches(self, node_id, label, degree, file_path=None,
                tags=None, is_attachment=False, created=None):
        if is_attachment and not self.show_attachments:
            return False
        if degree == 0 and not self.show_orphans:
            return False
        if self.search_query:
            q = self.search_query.lower()
            if q not in label.lower() and q not in node_id.lower():
                return False
        if self.min_degree > degree or self.max_degree < degree:
            return False
        if created is not None:
            if self.date_from and created < self.date_from:
                return False
            if self.date_to and created > self.date_to:
                return False
        return True


class NodeGroup:
    __slots__ = ("name", "query", "color", "match_fn", "node_ids")

    def __init__(self, name, query, color, match_fn=None):
        self.name = name
        self.query = query
        self.color = QColor(color) if isinstance(color, str) else color
        self.match_fn = match_fn
        self.node_ids = set()

    def matches(self, node_id, label, tags=None, properties=None):
        if self.match_fn:
            try:
                return self.match_fn(node_id, label, tags or [], properties or {})
            except Exception:
                return False
        q = self.query.lower()
        if q in label.lower() or q in node_id.lower():
            return True
        if tags and any(q in t.lower() for t in tags):
            return True
        if properties:
            for v in properties.values():
                if q in str(v).lower():
                    return True
        return False


# ══════════════════════════════════════════════════════════════════════════
# Barnes-Hut quadtree
# ══════════════════════════════════════════════════════════════════════════

class _QuadNode:
    __slots__ = ("x", "y", "size", "mass", "cx", "cy",
                 "children", "body", "is_leaf")

    def __init__(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size
        self.mass = 0.0
        self.cx = 0.0
        self.cy = 0.0
        self.children = None
        self.body = None
        self.is_leaf = True


class BarnesHutTree:
    __slots__ = ("root", "theta", "size")

    def __init__(self, theta=0.9):
        self.theta = theta
        self.root = None
        self.size = 0.0

    def build(self, nodes):
        if not nodes:
            return
        self.size = 0
        min_x = min(n.x() for n in nodes)
        min_y = min(n.y() for n in nodes)
        max_x = max(n.x() for n in nodes)
        max_y = max(n.y() for n in nodes)
        w = max(max_x - min_x, max_y - min_y, 1.0)
        self.size = w
        self.root = _QuadNode(min_x, min_y, w)
        for n in nodes:
            self._insert(self.root, n)

    def _insert(self, node, body):
        if node.is_leaf and node.body is None:
            node.body = body
            node.mass = 1.0
            node.cx = body.x()
            node.cy = body.y()
            return
        if node.is_leaf:
            node.is_leaf = False
            old = node.body
            node.body = None
            self._subdivide(node)
            self._insert_child(node, old)
        self._insert_child(node, body)

    def _subdivide(self, node):
        h = node.size / 2
        node.children = [
            _QuadNode(node.x, node.y, h),
            _QuadNode(node.x + h, node.y, h),
            _QuadNode(node.x, node.y + h, h),
            _QuadNode(node.x + h, node.y + h, h),
        ]

    def _insert_child(self, node, body):
        qx = 1 if body.x() >= node.x + node.size / 2 else 0
        qy = 1 if body.y() >= node.y + node.size / 2 else 0
        idx = qy * 2 + qx
        self._insert(node.children[idx], body)
        total = node.mass + 1.0
        node.cx = (node.cx * node.mass + body.x()) / total
        node.cy = (node.cy * node.mass + body.y()) / total
        node.mass = total

    def force_on(self, body, node=None):
        if node is None:
            node = self.root
        if node is None or node.mass == 0:
            return 0.0, 0.0
        dx = body.x() - node.cx
        dy = body.y() - node.cy
        d2 = dx * dx + dy * dy
        if d2 < 0.5:
            dx = random.uniform(-1.0, 1.0)
            dy = random.uniform(-1.0, 1.0)
            d2 = 1.0
        d = math.sqrt(d2)

        if node.is_leaf or (node.size / d) < self.theta:
            if node.body is body:
                return 0.0, 0.0
            f = node.mass / d2
            return (dx / d) * f, (dy / d) * f

        fx = fy = 0.0
        for child in node.children:
            cfx, cfy = self.force_on(body, child)
            fx += cfx
            fy += cfy
        return fx, fy


# ══════════════════════════════════════════════════════════════════════════
# Graph node
# ══════════════════════════════════════════════════════════════════════════

class GraphNode(QGraphicsItem):
    def __init__(self, node_id, label, size=8.0, group_color=None,
                 pixmap=None, is_attachment=False):
        super().__init__()
        self.node_id = node_id
        self.label = label
        self.radius = float(size)
        self.velocity = [0.0, 0.0]
        self.pinned = False
        self.group_color = group_color
        self.is_attachment = is_attachment
        self._pixmap = pixmap
        self._pixmap_item = None
        self._hovered = False
        self._selected = False
        self._degree = 0
        self._created = None
        self._tags = []
        self._rel_type = None

        self.setPos(random.uniform(-220, 220), random.uniform(-220, 220))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        self._cached_rect = QRectF(
            -self.radius - 4, -self.radius - 4,
            self.radius * 2 + 8, self.radius * 2 + 8,
        )

    def boundingRect(self):
        return self._cached_rect

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        if pixmap and not pixmap.isNull():
            target = max(self.radius * 2, 16)
            scaled = pixmap.scaled(
                int(target), int(target),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if self._pixmap_item is None:
                self._pixmap_item = QGraphicsPixmapItem(scaled, self)
                self._pixmap_item.setPos(-scaled.width() / 2,
                                         -scaled.height() / 2)
                self._pixmap_item.setZValue(1)
            else:
                self._pixmap_item.setPixmap(scaled)
        self.prepareGeometryChange()
        self._cached_rect = QRectF(
            -self.radius - 4, -self.radius - 4,
            self.radius * 2 + 8, self.radius * 2 + 8,
        )
        self.update()

    def paint(self, painter, option, widget=None):
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.group_color:
            fill = self.group_color
            border = fill.darker(130)
        elif self.isSelected():
            fill = QColor("#ffd700")
            border = QColor("#ffed4e")
        elif self._hovered:
            fill = QColor("#9a7fd1")
            border = QColor("#c586c0")
        else:
            fill = QColor("#6f42c1")
            border = QColor("#4a2d8a")

        if self.is_attachment:
            fill = fill.lighter(110)

        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 2))
        painter.drawEllipse(QPointF(0, 0), self.radius, self.radius)

        if self._pixmap_item and lod > 0.5:
            self._pixmap_item.setVisible(True)
        elif self._pixmap_item:
            self._pixmap_item.setVisible(False)

        if (self._hovered or self.isSelected()) and lod > 0.3:
            painter.setFont(QFont("Segoe UI", 9))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self.label) + 12
            th = fm.height() + 6
            rect = QRectF(-tw / 2, self.radius + 4, tw, th)
            painter.setBrush(QBrush(QColor(30, 30, 30, 235)))
            painter.setPen(QPen(QColor("#555")))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QPen(QColor("#e0e0e0")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            scene = self.scene()
            if scene is not None:
                for item in scene.items():
                    if isinstance(item, GraphEdge):
                        item.update_position()
        return super().itemChange(change, value)


class GraphEdge(QGraphicsLineItem):
    def __init__(self, source, target, rel_type=RelationType.LINK,
                 width=1.2, show_arrows=False):
        super().__init__()
        self.source = source
        self.target = target
        self.rel_type = rel_type
        self._width = width
        self._show_arrows = show_arrows
        color = RelationType.color(rel_type)
        self.setPen(QPen(color, width))
        self.setZValue(-1)
        self.update_position()

    def update_position(self):
        self.prepareGeometryChange()
        self.setLine(
            self.source.x(), self.source.y(),
            self.target.x(), self.target.y(),
        )

    def set_show_arrows(self, show):
        self._show_arrows = show
        self.update()

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self._show_arrows:
            line = self.line()
            if line.length() < 20:
                return
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(self.pen().color(), 1.5))
            angle = math.atan2(line.dy(), line.dx())
            size = 8
            tx = line.x2() - self.target.radius * math.cos(angle)
            ty = line.y2() - self.target.radius * math.sin(angle)
            p1 = QPointF(
                tx - size * math.cos(angle - 0.4),
                ty - size * math.sin(angle - 0.4),
            )
            p2 = QPointF(
                tx - size * math.cos(angle + 0.4),
                ty - size * math.sin(angle + 0.4),
            )
            painter.drawPolygon(QPolygonF([QPointF(tx, ty), p1, p2]))


# ══════════════════════════════════════════════════════════════════════════
# Force graph view
# ══════════════════════════════════════════════════════════════════════════

class ForceGraphView(QGraphicsView):
    node_clicked = pyqtSignal(str)
    node_hovered = pyqtSignal(str)
    edge_clicked = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-4000, -4000, 8000, 8000)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#181818")))
        self.setStyleSheet("border: none;")
        self.setAcceptDrops(True)

        # NoIndex is correct for a scene with continuously moving items.
        # Do NOT call setBspTreeDepth — it is only valid with BspTreeIndex.
        self.scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True
        )

        self.config = GraphConfig()
        self.filter = GraphFilter()
        self.groups = []
        self._errors = _DEFAULT_ROUTER

        self.nodes = {}
        self.edges = []
        self._adjacency = defaultdict(set)

        self._bh_tree = BarnesHutTree(self.config.barnes_hut_theta)

        self._timelapse_queue = []
        self._timelapse_timer = QTimer(self)
        self._timelapse_timer.timeout.connect(self._timelapse_step)
        self._timelapse_timer.setInterval(120)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.setInterval(33)
        self.timer.start()

    def clear_graph(self):
        for item in list(self.scene.items()):
            self.scene.removeItem(item)
        self.nodes.clear()
        self.edges.clear()
        self._adjacency.clear()

    def add_node(self, node_id, label, degree=0, **kwargs):
        if node_id in self.nodes:
            return self.nodes[node_id]
        size = self.config.node_base_size + min(degree, 20) * 0.6
        size = min(size, self.config.node_max_size)
        node = GraphNode(
            node_id, label, size=size,
            group_color=kwargs.get("group_color"),
            pixmap=kwargs.get("pixmap"),
            is_attachment=kwargs.get("is_attachment", False),
        )
        node._degree = degree
        node._created = kwargs.get("created")
        node._tags = kwargs.get("tags", [])
        self.scene.addItem(node)
        self.nodes[node_id] = node
        return node

    def add_edge(self, source_id, target_id, rel_type=RelationType.LINK):
        s = self.nodes.get(source_id)
        t = self.nodes.get(target_id)
        if not s or not t:
            return
        width = self.config.link_base_width
        edge = GraphEdge(
            s, t, rel_type=rel_type, width=width,
            show_arrows=self.config.show_arrows,
        )
        self.scene.addItem(edge)
        self.edges.append(edge)
        self._adjacency[source_id].add(target_id)
        self._adjacency[target_id].add(source_id)

    def build(self, note_paths, edges):
        self.clear_graph()
        if not note_paths:
            return
        path_set = set(note_paths)
        stem_to_path = {}
        for p in note_paths:
            stem_to_path[Path(p).stem.lower()] = p
            stem_to_path[p.lower()] = p

        degree = defaultdict(int)
        normalized = []
        for src, tgt in edges:
            s = src if src in path_set else stem_to_path.get(src.lower(), src)
            t = tgt if tgt in path_set else stem_to_path.get(tgt.lower(), tgt)
            if s not in path_set or t not in path_set or s == t:
                continue
            degree[s] += 1
            degree[t] += 1
            normalized.append((s, t))

        for p in note_paths:
            self.add_node(p, Path(p).stem, degree.get(p, 0))
        for s, t in normalized:
            self.add_edge(s, t)

    def _tick(self):
        self._errors.layout.safe_tick(self)

    def _tick_internal(self):
        node_list = list(self.nodes.values())
        n = len(node_list)
        if n == 0:
            return

        use_bh = self.config.barnes_hut and n >= self.config.barnes_hut_threshold
        if use_bh:
            self._bh_tree.theta = self.config.barnes_hut_theta
            self._bh_tree.build(node_list)

        for _ in range(self.config.iterations_per_tick):
            for i, a in enumerate(node_list):
                if a.pinned:
                    continue
                ax, ay = a.x(), a.y()
                if use_bh:
                    fx, fy = self._bh_tree.force_on(a)
                    fx *= self.config.repulsion / max(self._bh_tree.size, 1.0)
                    fy *= self.config.repulsion / max(self._bh_tree.size, 1.0)
                else:
                    fx = fy = 0.0
                    for j, b in enumerate(node_list):
                        if i == j:
                            continue
                        dx = ax - b.x()
                        dy = ay - b.y()
                        d2 = dx * dx + dy * dy
                        if d2 < 0.5:
                            dx = random.uniform(-1.0, 1.0)
                            dy = random.uniform(-1.0, 1.0)
                            d2 = 1.0
                        inv = self.config.repulsion / d2
                        inv_d = inv / math.sqrt(d2)
                        fx += dx * inv_d
                        fy += dy * inv_d

                fx -= ax * self.config.centering
                fy -= ay * self.config.centering

                a.velocity[0] = (a.velocity[0] + fx) * self.config.damping
                a.velocity[1] = (a.velocity[1] + fy) * self.config.damping

            for edge in self.edges:
                s, t = edge.source, edge.target
                dx = t.x() - s.x()
                dy = t.y() - s.y()
                d = math.sqrt(dx * dx + dy * dy) or 1.0
                force = (d - self.config.spring_length) * self.config.spring_k
                ux = dx / d
                uy = dy / d
                if not s.pinned:
                    s.velocity[0] += ux * force
                    s.velocity[1] += uy * force
                if not t.pinned:
                    t.velocity[0] -= ux * force
                    t.velocity[1] -= uy * force

            for a in node_list:
                if a.pinned:
                    continue
                vx, vy = a.velocity
                sp = math.sqrt(vx * vx + vy * vy)
                if sp > self.config.max_velocity:
                    vx = vx / sp * self.config.max_velocity
                    vy = vy / sp * self.config.max_velocity
                a.setPos(a.x() + vx, a.y() + vy)

        for edge in self.edges:
            edge.update_position()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.position().toPoint())
        if isinstance(item, GraphNode):
            self.node_clicked.emit(item.node_id)
        elif isinstance(item, GraphEdge):
            self.edge_clicked.emit(item.source.node_id, item.target.node_id)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                p = Path(url.toLocalFile())
                if p.suffix.lower().lstrip(".") in ImageErrorHandler.supported_formats():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            ext = p.suffix.lower().lstrip(".")
            if ext not in ImageErrorHandler.supported_formats():
                continue
            pos = self.mapToScene(event.position().toPoint())
            self._add_image_node(p, pos)
        event.acceptProposedAction()

    def _add_image_node(self, path, pos):
        pixmap = self._errors.image.safe_load_pixmap(path, max_size=64)
        if pixmap is None:
            return
        node_id = f"__img__{path.stem}_{int(time.time() * 1000) % 100000}"
        node = self.add_node(
            node_id, path.stem, degree=0,
            pixmap=pixmap, is_attachment=True,
        )
        if node:
            node.setPos(pos)

    def start_timelapse(self, node_ids):
        self._timelapse_queue = list(node_ids)
        self._timelapse_timer.start()

    def stop_timelapse(self):
        self._timelapse_timer.stop()
        self._timelapse_queue.clear()

    def _timelapse_step(self):
        if not self._timelapse_queue:
            self._timelapse_timer.stop()
            return
        nid = self._timelapse_queue.pop(0)
        node = self.nodes.get(nid)
        if node:
            node.setOpacity(1.0)


# ══════════════════════════════════════════════════════════════════════════
# Graph builder
# ══════════════════════════════════════════════════════════════════════════

class GraphBuilder:
    @staticmethod
    def full_vault(vault, backlinks):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        edges = []
        for src, tgt in backlinks.all_edges():
            resolved = GraphBuilder._resolve(tgt, notes)
            if resolved:
                edges.append((src, resolved))
        return notes, edges

    @staticmethod
    def local_graph(vault, backlinks, note_rel, depth=1):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        visited = {note_rel}
        frontier = {note_rel}
        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                for src, tgt in backlinks.all_edges():
                    if src == n:
                        r = GraphBuilder._resolve(tgt, notes)
                        if r and r not in visited:
                            next_frontier.add(r)
                    elif tgt == n:
                        if src not in visited:
                            next_frontier.add(src)
            visited |= next_frontier
            frontier = next_frontier
        paths = [p for p in notes if p in visited]
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in visited and GraphBuilder._resolve(t, notes) in visited]
        return paths, edges

    @staticmethod
    def by_tag(vault, tag_index, tag):
        files = tag_index.files_for_tag(tag)
        paths = [f for f in files if vault.abs_path(f).exists()]
        return paths, []

    @staticmethod
    def by_tags_all(vault, tag_index, tags):
        if not tags:
            return [], []
        sets = [set(tag_index.files_for_tag(t)) for t in tags]
        common = set.intersection(*sets) if sets else set()
        paths = [f for f in common if vault.abs_path(f).exists()]
        return paths, []

    @staticmethod
    def by_folder(vault, folder_rel):
        folder = vault.vault_path / folder_rel
        paths = [vault.rel_path(p) for p in folder.rglob("*.md")]
        return paths, []

    @staticmethod
    def orphans(vault, backlinks):
        all_notes = {vault.rel_path(p) for p in vault.list_notes()}
        linked = set()
        for s, t in backlinks.all_edges():
            linked.add(s)
            r = GraphBuilder._resolve(t, all_notes)
            if r:
                linked.add(r)
        paths = [p for p in all_notes if p not in linked]
        return paths, []

    @staticmethod
    def most_connected(vault, backlinks, top_n=30):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        degree = defaultdict(int)
        for s, t in backlinks.all_edges():
            degree[s] += 1
            r = GraphBuilder._resolve(t, notes)
            if r:
                degree[r] += 1
        top = sorted(degree.items(), key=lambda kv: -kv[1])[:top_n]
        top_set = {n for n, _ in top}
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in top_set and GraphBuilder._resolve(t, notes) in top_set]
        return list(top_set), edges

    @staticmethod
    def pagerank(vault, backlinks, top_n=30, damping=0.85, iters=20):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        if not notes:
            return [], []
        n = len(notes)
        rank = {p: 1.0 / n for p in notes}
        adj = defaultdict(list)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                adj[s].append(r)
        for _ in range(iters):
            new = {p: (1 - damping) / n for p in notes}
            for p in notes:
                out = adj.get(p, [])
                if not out:
                    continue
                share = rank[p] * damping / len(out)
                for q in out:
                    new[q] += share
            rank = new
        top = sorted(rank.items(), key=lambda kv: -kv[1])[:top_n]
        top_set = {n for n, _ in top}
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in top_set and GraphBuilder._resolve(t, notes) in top_set]
        return list(top_set), edges

    @staticmethod
    def by_search(vault, search_index, query):
        results = search_index.search(query, limit=100)
        paths = [r["path"] for r in results]
        return paths, []

    @staticmethod
    def by_date_range(vault, from_ts, to_ts):
        paths = []
        for p in vault.list_notes():
            try:
                mtime = p.stat().st_mtime
                if from_ts <= mtime <= to_ts:
                    paths.append(vault.rel_path(p))
            except OSError:
                continue
        return paths, []

    @staticmethod
    def recently_modified(vault, top_n=30):
        items = []
        for p in vault.list_notes():
            try:
                items.append((p.stat().st_mtime, vault.rel_path(p)))
            except OSError:
                continue
        items.sort(reverse=True)
        return [r for _, r in items[:top_n]], []

    @staticmethod
    def unresolved(vault, backlinks):
        notes = {vault.rel_path(p) for p in vault.list_notes()}
        stubs = {}
        edges = []
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if not r:
                stub_id = f"__stub__{t}"
                stubs[stub_id] = t
                edges.append((s, stub_id))
        return list(stubs.keys()) + list(notes), edges

    @staticmethod
    def attachments_only(vault, backlinks):
        attachment_exts = set(ImageErrorHandler.supported_formats())
        atts = {}
        for p in vault.vault_path.rglob("*"):
            if p.is_file() and p.suffix.lower().lstrip(".") in attachment_exts:
                atts[vault.rel_path(p)] = p
        return list(atts.keys()), []

    @staticmethod
    def random_sample(vault, backlinks, size=50):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        sample = set(random.sample(notes, min(size, len(notes))))
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in sample and GraphBuilder._resolve(t, notes) in sample]
        return list(sample), edges

    @staticmethod
    def shortest_path(vault, backlinks, start, end):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        adj = defaultdict(list)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                adj[s].append(r)
                adj[r].append(s)
        if start not in adj or end not in adj:
            return [start, end], []
        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == end:
                break
            for nb in adj[cur]:
                if nb not in prev:
                    prev[nb] = cur
                    q.append(nb)
        if end not in prev:
            return [start, end], []
        path = []
        cur = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        edges = [(path[i], path[i + 1]) for i in range(len(path) - 1)]
        return path, edges

    @staticmethod
    def communities(vault, backlinks, top_n=50):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        labels = {n: i for i, n in enumerate(notes)}
        adj = defaultdict(list)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                adj[s].append(r)
                adj[r].append(s)
        for _ in range(10):
            changed = False
            for n in notes:
                if not adj[n]:
                    continue
                counts = defaultdict(int)
                for nb in adj[n]:
                    counts[labels[nb]] += 1
                if counts:
                    best = max(counts, key=counts.get)
                    if labels[n] != best:
                        labels[n] = best
                        changed = True
            if not changed:
                break
        groups = defaultdict(list)
        for n, lbl in labels.items():
            groups[lbl].append(n)
        top_groups = sorted(groups.values(), key=len, reverse=True)[:top_n]
        flat = [n for g in top_groups for n in g]
        flat_set = set(flat)
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in flat_set and GraphBuilder._resolve(t, notes) in flat_set]
        return flat, edges

    @staticmethod
    def similar_to(vault, backlinks, note_rel, top_n=20):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        targets = set()
        for s, t in backlinks.all_edges():
            if s == note_rel:
                r = GraphBuilder._resolve(t, notes)
                if r:
                    targets.add(r)
        scores = defaultdict(int)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r and r in targets and s != note_rel:
                scores[s] += 1
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:top_n]
        result = {note_rel} | {n for n, _ in top}
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in result and GraphBuilder._resolve(t, notes) in result]
        return list(result), edges

    @staticmethod
    def by_property(vault, backlinks, key, value=None):
        paths = []
        for p in vault.list_notes():
            try:
                content = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if content.startswith("---"):
                end = content.find("\n---", 3)
                if end > 0:
                    fm = content[3:end]
                    for line in fm.splitlines():
                        if ":" in line:
                            k, _, v = line.partition(":")
                            if k.strip() == key:
                                if value is None or value.lower() in v.lower():
                                    paths.append(vault.rel_path(p))
                                    break
        return paths, []

    @staticmethod
    def by_word_count(vault, min_words=500):
        paths = []
        for p in vault.list_notes():
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if len(text.split()) >= min_words:
                paths.append(vault.rel_path(p))
        return paths, []

    @staticmethod
    def by_creation(vault, top_n=50):
        items = []
        for p in vault.list_notes():
            try:
                st = p.stat()
                items.append((min(st.st_ctime, st.st_mtime),
                              vault.rel_path(p)))
            except OSError:
                continue
        items.sort()
        return [r for _, r in items[:top_n]], []

    @staticmethod
    def bidirectional(vault, backlinks):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        edge_set = set()
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                edge_set.add((s, r))
        mutual = []
        for s, t in edge_set:
            if (t, s) in edge_set and s < t:
                mutual.append((s, t))
        nodes = set()
        for s, t in mutual:
            nodes.add(s)
            nodes.add(t)
        return list(nodes), mutual

    @staticmethod
    def by_tag_cooccurrence(vault, tag_index, min_shared=2):
        tag_files = defaultdict(set)
        for tag, _count in tag_index.all_tags():
            for f in tag_index.files_for_tag(tag):
                tag_files[tag].add(f)
        edges = []
        files = set()
        tags = list(tag_files.keys())
        for i, t1 in enumerate(tags):
            for t2 in tags[i + 1:]:
                shared = tag_files[t1] & tag_files[t2]
                if len(shared) >= min_shared:
                    fl = list(shared)
                    files |= shared
                    for j in range(len(fl)):
                        for k in range(j + 1, len(fl)):
                            edges.append((fl[j], fl[k]))
        return list(files), edges

    @staticmethod
    def by_link_distance(vault, backlinks, seeds, max_distance=2):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        adj = defaultdict(set)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                adj[s].add(r)
                adj[r].add(s)
        visited = set(seeds)
        frontier = set(seeds)
        for _ in range(max_distance):
            nf = set()
            for n in frontier:
                nf |= adj[n] - visited
            visited |= nf
            frontier = nf
        edges = []
        for s in visited:
            for t in adj[s]:
                if t in visited and s < t:
                    edges.append((s, t))
        return list(visited), edges

    @staticmethod
    def custom(vault, predicate, backlinks=None):
        paths = []
        for p in vault.list_notes():
            rel = vault.rel_path(p)
            try:
                if predicate(rel, p):
                    paths.append(rel)
            except Exception:
                continue
        edges = []
        if backlinks:
            notes_set = set(paths)
            for s, t in backlinks.all_edges():
                r = GraphBuilder._resolve(t, paths)
                if s in notes_set and r in notes_set:
                    edges.append((s, r))
        return paths, edges

    @staticmethod
    def _resolve(target, known_paths):
        target = target.strip()
        stem = Path(target).stem.lower()
        for p in known_paths:
            if p == target or p == target + ".md":
                return p
            if Path(p).stem.lower() == stem:
                return p
        return None


# ══════════════════════════════════════════════════════════════════════════
# Graph widget (used in full-screen dialog)
# ══════════════════════════════════════════════════════════════════════════

def _button_style():
    return (
        "QPushButton { background: #333; color: #ddd; border: none; "
        "padding: 4px 14px; border-radius: 4px; font-size: 12px; }"
        "QPushButton:hover { background: #444; }"
    )


def _combo_style():
    return (
        "QComboBox { background: #333; color: #ddd; border: 1px solid #555; "
        "padding: 3px 8px; border-radius: 4px; font-size: 11px; }"
        "QComboBox::drop-down { border: none; }"
    )


def _slider_style():
    return (
        "QSlider::groove:horizontal { background: #444; height: 4px; "
        "border-radius: 2px; }"
        "QSlider::handle:horizontal { background: #6f42c1; width: 12px; "
        "margin: -5px 0; border-radius: 6px; }"
    )


def _line_style():
    return (
        "QLineEdit { background: #333; color: #ddd; border: 1px solid #555; "
        "padding: 4px 8px; border-radius: 4px; font-size: 11px; }"
    )


def _check_style():
    return "QCheckBox { color: #ccc; font-size: 11px; }"


class GraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._errors = _DEFAULT_ROUTER
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_toolbar(layout)
        self.view = ForceGraphView(self)
        layout.addWidget(self.view, 1)

    def _build_toolbar(self, layout):
        bar = QWidget()
        bar.setStyleSheet("background: #252526; border-bottom: 1px solid #333;")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(10, 6, 10, 6)
        bar_layout.setSpacing(8)

        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Global", "Local", "Tags", "Orphans",
            "Most Connected", "PageRank", "Communities",
        ])
        self.type_combo.setStyleSheet(_combo_style())
        bar_layout.addWidget(QLabel("Type:"))
        bar_layout.addWidget(self.type_combo)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter…")
        self.search_box.setStyleSheet(_line_style())
        self.search_box.setFixedWidth(150)
        bar_layout.addWidget(self.search_box)

        self.orphans_cb = QCheckBox("Orphans")
        self.orphans_cb.setChecked(True)
        self.orphans_cb.setStyleSheet(_check_style())
        bar_layout.addWidget(self.orphans_cb)

        self.arrows_cb = QCheckBox("Arrows")
        self.arrows_cb.setStyleSheet(_check_style())
        bar_layout.addWidget(self.arrows_cb)

        bar_layout.addWidget(QLabel("Repel:"))
        self.repel_slider = QSlider(Qt.Orientation.Horizontal)
        self.repel_slider.setRange(1, 100)
        self.repel_slider.setValue(50)
        self.repel_slider.setFixedWidth(70)
        self.repel_slider.setStyleSheet(_slider_style())
        bar_layout.addWidget(self.repel_slider)

        bar_layout.addWidget(QLabel("Link:"))
        self.link_slider = QSlider(Qt.Orientation.Horizontal)
        self.link_slider.setRange(1, 100)
        self.link_slider.setValue(50)
        self.link_slider.setFixedWidth(70)
        self.link_slider.setStyleSheet(_slider_style())
        bar_layout.addWidget(self.link_slider)

        bar_layout.addStretch()

        self.info_label = QLabel("0 nodes, 0 edges")
        self.info_label.setStyleSheet("color: #999; font-size: 11px;")
        bar_layout.addWidget(self.info_label)

        fit_btn = QPushButton("Fit")
        fit_btn.setStyleSheet(_button_style())
        fit_btn.clicked.connect(self.fit)
        bar_layout.addWidget(fit_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet(_button_style())
        reset_btn.clicked.connect(self._reset)
        bar_layout.addWidget(reset_btn)

        layout.addWidget(bar)

        self._errors.ui.safe_connect(
            self.search_box.textChanged, self._on_search,
            context="search_changed",
        )
        self._errors.ui.safe_connect(
            self.orphans_cb.stateChanged, self._on_orphans,
            context="orphans_toggled",
        )
        self._errors.ui.safe_connect(
            self.arrows_cb.stateChanged, self._on_arrows,
            context="arrows_toggled",
        )
        self._errors.ui.safe_connect(
            self.repel_slider.valueChanged, self._on_repel,
            context="repel_changed",
        )
        self._errors.ui.safe_connect(
            self.link_slider.valueChanged, self._on_link,
            context="link_changed",
        )

    def load_graph(self, note_paths, edges, rel_types=None):
        self.view.build(note_paths, edges)
        if rel_types:
            for i, (s, t) in enumerate(edges):
                if i < len(self.view.edges):
                    self.view.edges[i].rel_type = rel_types[i]
                    self.view.edges[i].setPen(
                        QPen(RelationType.color(rel_types[i]),
                             self.view.config.link_base_width)
                    )
        self._update_info()

    def fit(self):
        if self.view.nodes:
            rect = self.view.scene.itemsBoundingRect()
            if rect.width() > 0 and rect.height() > 0:
                self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _reset(self):
        self.view.resetTransform()
        self.fit()

    def _update_info(self):
        n = len(self.view.nodes)
        e = len(self.view.edges)
        self.info_label.setText(f"{n} nodes, {e} edges")

    def _on_search(self, text):
        self.view.filter.search_query = text
        self._apply_filter()

    def _on_orphans(self, state):
        self.view.filter.show_orphans = bool(state)
        self._apply_filter()

    def _on_arrows(self, state):
        self.view.config.show_arrows = bool(state)
        for edge in self.view.edges:
            edge.set_show_arrows(bool(state))

    def _on_repel(self, value):
        self.view.config.repulsion = 2000.0 + (value / 100.0) * 28000.0

    def _on_link(self, value):
        self.view.config.spring_length = 40.0 + (value / 100.0) * 260.0

    def _apply_filter(self):
        f = self.view.filter
        for node in self.view.nodes.values():
            visible = f.matches(
                node.node_id, node.label, node._degree,
                tags=node._tags,
            )
            node.setVisible(visible)
        for edge in self.view.edges:
            edge.setVisible(
                edge.source.isVisible() and edge.target.isVisible()
            )
        self._update_info()


__all__ = [
    "GraphNode", "GraphEdge", "ForceGraphView", "GraphWidget",
    "GraphBuilder", "GraphConfig", "GraphFilter", "NodeGroup",
    "RelationType", "BarnesHutTree", "ErrorRouter",
    "GraphErrorHandler", "ImageErrorHandler", "LayoutErrorHandler",
    "GraphUIErrorHandler", "default_router",
]
```

---

## Verify

```powershell
python -c "import Markdown_Chert, Live_Preview, Graph_Chert, Theme_Chert, Panels_Chert, Dialogs_Chert, UI_Chert; print('all ok')"
python Chert.py
```

**What should change vs the screenshot:**
- No more `QGraphicsScene::setBspTreeDepth` warning.
- The graph dock in the right sidebar now works without the BSP complaint.

**File checklist — every file in the project:**

```
Chert.py             ✓ thin entry point
Chert_Managers.py    ✓ this paste
Markdown_Chert.py    ✓ this paste
Live_Preview.py      ✓ this paste
Graph_Chert.py       ✓ this paste (BSP fixed)
Theme_Chert.py       ✓ from last paste
Panels_Chert.py      ✓ from last paste
Dialogs_Chert.py     ✓ from last paste
UI_Chert.py          ✓ from last paste
requirements.txt     ✓
.gitignore           ✓
```

That's the complete set. Nothing missing.