"""
Chert_Managers.py — Qt compatibility, vault, indexes, settings.

v1.0 — PyQt6-only. No PyQt5 fallback, no enum shim.

Fixes over v0.3:
  • QFileSystemModel moved to QtGui (Qt6). Was wrongly in QtWidgets.
  • Dropped PyQt5 import path and all enum shims.
  • diagnose_environment() no longer mentions PyQt5.
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

# ── PyQt6 imports ────────────────────────────────────────────────────────
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

# ── WebEngine (optional, separate package) ───────────────────────────────
HAS_WEBENGINE = False
QWebEngineView = None
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    pass


# ══════════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════
# Environment diagnostics
# ══════════════════════════════════════════════════════════════════════════

def diagnose_environment() -> dict:
    """Return a dict describing the runtime Qt environment."""
    return {
        "python_version": sys.version,
        "python_bits": 64 if sys.maxsize > 2**32 else 32,
        "platform": sys.platform,
        "binding": "PyQt6",
        "webengine": HAS_WEBENGINE,
        "install_hint": "python -m pip install PyQt6 PyQt6-WebEngine",
    }


# ══════════════════════════════════════════════════════════════════════════
# Error handling — 10 handlers
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

    def __repr__(self):
        return f"<{self.category}/{self.context} {self.exc_type}: {self.exc_msg}>"


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
        self._all: list[sqlite3.Connection] = []
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
    """Owns the vault path, watches directories, exposes note enumeration.

    No __slots__ — QObject subclasses need __dict__ for signal bookkeeping.
    """

    file_changed = pyqtSignal(str)
    vault_reloaded = pyqtSignal()

    def __init__(self, vault_path):
        super().__init__()
        self._errors = _MANAGER_ROUTER
        self.vault_path = self._errors.path.safe_resolve(vault_path)
        self.watcher = None
        self._known: set[str] = set()
        self._watch_dirs: set[str] = set()
        self._scanned = False
        self._watching = False
        self._pending_events: list[str] = []
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

    def list_notes(self) -> list[str]:
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

    def rel_path(self, abs_path) -> str:
        rel = self._errors.path.safe_relative_to(abs_path, self.vault_path)
        return _normalize_relpath(rel)

    def abs_path(self, rel) -> Path:
        return self.vault_path / rel.replace("/", os.sep)

    def read(self, rel) -> str:
        return self._errors.io.safe_read(self.abs_path(rel), default="")

    def write(self, rel, content) -> bool:
        return self._errors.io.safe_write(self.abs_path(rel), content)

    def create(self, rel) -> bool:
        p = self.abs_path(rel)
        if p.exists():
            return False
        return self._errors.io.safe_write(p, "")

    def delete(self, rel) -> bool:
        return self._errors.io.safe_delete(self.abs_path(rel))

    def rename(self, old_rel, new_rel) -> bool:
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

    def _on_dir_changed(self, path: str):
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

    def index_file(self, source: str, content: str):
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

    def remove_file(self, source: str):
        conn = self._pool.get()
        if conn is None:
            return
        try:
            conn.execute("DELETE FROM links WHERE source = ?", (source,))
            conn.commit()
        except sqlite3.Error as e:
            self._errors.sqlite.report("remove_file", e, source)

    def backlinks(self, target_rel: str) -> list[dict]:
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

    def outgoing(self, source_rel: str) -> list[str]:
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

    def all_edges(self) -> list[tuple[str, str]]:
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

    def index(self, rel: str, title: str, body: str):
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

    def remove(self, rel: str):
        conn = self._pool.get()
        if conn is None:
            return
        try:
            table = "notes_fts" if self._fts else "notes_simple"
            conn.execute(f"DELETE FROM {table} WHERE path = ?", (rel,))
            conn.commit()
        except sqlite3.Error as e:
            self._errors.sqlite.report("remove_search", e, rel)

    def search(self, query: str, limit: int = 40) -> list[dict]:
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

    def index_file(self, source: str, content: str):
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

    def all_tags(self) -> list[tuple[str, int]]:
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

    def files_for_tag(self, tag: str) -> list[str]:
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
        self.path: Optional[Path] = None
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

    def save(self, force: bool = False):
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


# ══════════════════════════════════════════════════════════════════════════
# App config
# ══════════════════════════════════════════════════════════════════════════

_config_cache: Optional[dict] = None
_config_lock = threading.Lock()


def vault_settings_dir(vault) -> Path:
    d = Path(vault) / CHERT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def app_config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA",
                                   Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".config"
    d = base / "Chert"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_app_config() -> dict:
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


def save_app_config(cfg: dict) -> None:
    global _config_cache
    with _config_lock:
        _config_cache = dict(cfg)
        p = app_config_dir() / "config.json"
        _MANAGER_ROUTER.config.safe_save(p, _config_cache)


# ══════════════════════════════════════════════════════════════════════════
# Public surface
# ══════════════════════════════════════════════════════════════════════════

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