"""
Chert.py — Main application window and entry point.

v0.3: pre-flight dependency check so a missing Qt binding gives a clear
message instead of a cryptic ImportError.
"""

import sys
import subprocess
from pathlib import Path

# ── Pre-flight: check for Qt bindings BEFORE importing them ─────────────
def _preflight() -> bool:
    import importlib.util

    has_pyqt6 = importlib.util.find_spec("PyQt6") is not None
    has_pyqt5 = importlib.util.find_spec("PyQt5") is not None

    if has_pyqt6 or has_pyqt5:
        return True

    print("", file=sys.stderr)
    print("Chert cannot start: no Qt binding found.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Install one of the following:", file=sys.stderr)
    print("  python -m pip install PyQt6 PyQt6-WebEngine"
          "   # 64-bit recommended", file=sys.stderr)
    print("  python -m pip install PyQt5 PyQt5-WebEngine"
          "   # 32-bit fallback", file=sys.stderr)
    print("", file=sys.stderr)
    print("Or install from the pinned requirements file:", file=sys.stderr)
    print("  python -m pip install -r requirements.txt",
          file=sys.stderr)
    print("", file=sys.stderr)
    print("Note: 'PyQt6.QtWebEngineWidgets' is NOT a pip package name.",
          file=sys.stderr)
    print("The correct WebEngine package is 'PyQt6-WebEngine'.",
          file=sys.stderr)
    print("", file=sys.stderr)
    return False


if not _preflight():
    sys.exit(1)


# ── Imports (Qt is now guaranteed to be present) ────────────────────────
from Chert_Managers import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QTreeView, QDockWidget, QListWidget, QListWidgetItem,
    QFileSystemModel, QToolBar, QLineEdit, QLabel, QStatusBar,
    QMessageBox, QInputDialog, QMenu, QFileDialog, QDialog,
    QDialogButtonBox, QPushButton, QAction, QKeySequence, Qt, QModelIndex,
    QTimer, QDesktopServices, QUrl, QColor, QPalette, QFrame,
    VaultManager, BacklinkIndex, SearchIndex, TagIndex, ChertSettings,
    vault_settings_dir, load_app_config, save_app_config,
    MD_EXT, PYQT6, HAS_WEBENGINE, diagnose_environment,
)
from Live_Preview import LivePreviewPane
from Graph_Chert import GraphWidget


APP_NAME = "Chert"
APP_VERSION = "0.3.0"


# ── Vault picker ────────────────────────────────────────────────────────
class VaultPickerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open Vault")
        self.setMinimumWidth(520)
        self.selected: Path | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Recent vaults:"))

        self.recent_list = QListWidget()
        cfg = load_app_config()
        for r in cfg.get("recent_vaults", []):
            if Path(r).is_dir():
                self.recent_list.addItem(r)
        self.recent_list.itemDoubleClicked.connect(self._open_recent)
        layout.addWidget(self.recent_list)

        btns = QHBoxLayout()
        new_btn = QPushButton("Create New Vault…")
        new_btn.clicked.connect(self._create_new)
        btns.addWidget(new_btn)

        open_btn = QPushButton("Open Existing Folder…")
        open_btn.clicked.connect(self._open_folder)
        btns.addWidget(open_btn)
        layout.addLayout(btns)

        cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        cancel.rejected.connect(self.reject)
        layout.addWidget(cancel)

    def _open_recent(self, item):
        self.selected = Path(item.text())
        self.accept()

    def _create_new(self):
        path = QFileDialog.getExistingDirectory(self, "Choose folder for new vault")
        if path:
            self.selected = Path(path)
            self.accept()

    def _open_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Choose vault folder")
        if path:
            self.selected = Path(path)
            self.accept()


# ── Main window ─────────────────────────────────────────────────────────
class ChertMainWindow(QMainWindow):
    def __init__(self, vault_path: Path):
        super().__init__()
        self.vault_path = Path(vault_path).resolve()
        self.settings = ChertSettings(self.vault_path)

        self.vault = VaultManager(self.vault_path)
        cfg_dir = vault_settings_dir(self.vault_path)
        self.backlinks = BacklinkIndex(cfg_dir / "backlinks.db")
        self.search = SearchIndex(cfg_dir / "search.db")
        self.tags = TagIndex(cfg_dir / "tags.db")

        cfg = load_app_config()
        recents = [r for r in cfg.get("recent_vaults", []) if Path(r).is_dir()]
        s = str(self.vault_path)
        if s in recents:
            recents.remove(s)
        recents.insert(0, s)
        cfg["recent_vaults"] = recents[:10]
        save_app_config(cfg)

        self._build_ui()
        self._apply_theme()

        self._reindex_vault()
        self._refresh_tags()
        self._refresh_graph()

        self.vault.vault_reloaded.connect(self._on_vault_reloaded)

    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME} — {self.vault_path.name}")
        self.resize(1440, 900)

        self._build_menus()
        self._build_toolbar()

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

        self._build_file_tree()
        self._build_backlinks_dock()
        self._build_tags_dock()
        self._build_graph_dock()

        self.status = QStatusBar()
        self.status.setStyleSheet("background: #007acc; color: white;")
        self.setStatusBar(self.status)
        self._set_status("Ready")

    def _build_menus(self):
        mb = self.menuBar()
        mb.setStyleSheet("""
            QMenuBar { background: #2d2d30; color: #ddd; }
            QMenuBar::item:selected { background: #3e3e42; }
            QMenu { background: #2d2d30; color: #ddd; border: 1px solid #3e3e42; }
            QMenu::item:selected { background: #094771; }
        """)

        fm = mb.addMenu("&File")
        self._act(fm, "New Note", "Ctrl+N", self._new_note)
        self._act(fm, "New Folder", None, self._new_folder)
        fm.addSeparator()
        self._act(fm, "Save", "Ctrl+S", self._save_current)
        fm.addSeparator()
        self._act(fm, "Open Vault (new window)…", "Ctrl+O", self._switch_vault)
        self._act(fm, "Reveal Vault in Explorer", None, self._reveal_vault)
        fm.addSeparator()
        self._act(fm, "Exit", "Ctrl+Q", self.close)

        em = mb.addMenu("&Edit")
        self._act(em, "Undo", "Ctrl+Z",
                  lambda: self._current_editor() and self._current_editor().undo())
        self._act(em, "Redo", "Ctrl+Y",
                  lambda: self._current_editor() and self._current_editor().redo())
        em.addSeparator()
        self._act(em, "Find in Vault…", "Ctrl+Shift+F", self._focus_search)

        vm = mb.addMenu("&View")
        self._act(vm, "Toggle Graph", "Ctrl+G", self._toggle_graph)
        self._act(vm, "Toggle Backlinks", "Ctrl+B", self._toggle_backlinks)
        self._act(vm, "Toggle Tags", "Ctrl+T", self._toggle_tags)
        vm.addSeparator()
        self._act(vm, "Split", None, lambda: self._set_split(0.5))
        self._act(vm, "Preview Only", None, lambda: self._set_split(0.0))
        self._act(vm, "Editor Only", None, lambda: self._set_split(1.0))

        hm = mb.addMenu("&Help")
        self._act(hm, "About Chert", None, self._about)
        self._act(hm, "Environment Diagnostics", None, self._show_diagnostics)

    def _act(self, menu, name, shortcut, slot):
        a = QAction(name, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _build_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setStyleSheet("""
            QToolBar { background: #2d2d30; border: none; spacing: 4px; padding: 4px; }
            QToolButton { background: transparent; color: #ddd;
                          border: none; padding: 5px 12px; }
            QToolButton:hover { background: #3e3e42; border-radius: 4px; }
        """)
        self.addToolBar(tb)

        tb.addAction("New", self._new_note)
        tb.addAction("Save", self._save_current)
        tb.addSeparator()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search notes… (Ctrl+Shift+F)")
        self.search_box.setStyleSheet("""
            QLineEdit { background: #3c3c3c; color: #ddd; border: 1px solid #555;
                        border-radius: 4px; padding: 5px 12px; min-width: 280px; }
            QLineEdit:focus { border: 1px solid #007acc; }
        """)
        self.search_box.returnPressed.connect(self._run_search)
        self.search_box.textChanged.connect(self._on_search_text)
        tb.addWidget(self.search_box)

        tb.addSeparator()
        tb.addAction("Graph", self._toggle_graph)

    def _build_file_tree(self):
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(str(self.vault_path))
        self.file_model.setNameFilters(["*.md", "*.markdown", "*.txt"])
        self.file_model.setNameFilterDisables(False)

        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(str(self.vault_path)))
        for col in range(1, 4):
            self.file_tree.hideColumn(col)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setIndentation(14)
        self.file_tree.setStyleSheet("""
            QTreeView {
                background: #252526; color: #ccc; border: none;
                font-size: 12px; padding: 6px;
            }
            QTreeView::item { padding: 3px 4px; border-radius: 3px; }
            QTreeView::item:hover { background: #2a2d2e; }
            QTreeView::item:selected { background: #094771; color: #fff; }
        """)
        self.file_tree.doubleClicked.connect(self._on_tree_double_click)
        self.file_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._tree_context_menu)

        dock = QDockWidget("Vault", self)
        dock.setStyleSheet(self._dock_style())
        dock.setWidget(self.file_tree)
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        self.files_dock = dock

    def _build_backlinks_dock(self):
        self.backlinks_list = QListWidget()
        self.backlinks_list.setWordWrap(True)
        self.backlinks_list.setStyleSheet("""
            QListWidget { background: #252526; color: #ccc; border: none;
                          font-size: 12px; padding: 4px; }
            QListWidget::item { padding: 6px; border-radius: 3px; }
            QListWidget::item:hover { background: #2a2d2e; }
            QListWidget::item:selected { background: #094771; color: #fff; }
        """)
        self.backlinks_list.itemDoubleClicked.connect(self._open_backlink)

        dock = QDockWidget("Backlinks", self)
        dock.setStyleSheet(self._dock_style())
        dock.setWidget(self.backlinks_list)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.backlinks_dock = dock

    def _build_tags_dock(self):
        self.tags_list = QListWidget()
        self.tags_list.setStyleSheet("""
            QListWidget { background: #252526; color: #4ec9b0; border: none;
                          font-size: 12px; padding: 4px; }
            QListWidget::item { padding: 4px 6px; border-radius: 3px; }
            QListWidget::item:hover { background: #2a2d2e; }
            QListWidget::item:selected { background: #094771; color: #fff; }
        """)
        self.tags_list.itemDoubleClicked.connect(self._filter_by_tag)

        dock = QDockWidget("Tags", self)
        dock.setStyleSheet(self._dock_style())
        dock.setWidget(self.tags_list)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.tags_dock = dock

    def _build_graph_dock(self):
        self.graph_widget = GraphWidget(self)
        self.graph_widget.view.node_clicked.connect(self._on_graph_node_clicked)

        dock = QDockWidget("Graph", self)
        dock.setStyleSheet(self._dock_style())
        dock.setWidget(self.graph_widget)
        dock.setMinimumHeight(240)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.hide()
        self.graph_dock = dock

    def _dock_style(self):
        return """
            QDockWidget { color: #ccc; font-size: 11px; }
            QDockWidget::title {
                background: #2d2d30; padding: 6px 10px;
                border-bottom: 1px solid #1e1e1e;
                text-transform: uppercase; letter-spacing: 0.5px;
            }
        """

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow { background: #1e1e1e; }
            QWidget { color: #ddd; }
            QLabel { color: #ddd; }
            QPushButton { background: #3c3c3c; color: #ddd;
                          border: 1px solid #555; border-radius: 4px;
                          padding: 5px 14px; }
            QPushButton:hover { background: #4a4a4a; }
            QTabWidget::pane { border: none; background: #1e1e1e; }
            QTabBar::tab {
                background: #252526; color: #aaa; padding: 7px 16px;
                border: none; margin-right: 1px; font-size: 12px;
            }
            QTabBar::tab:selected { background: #1e1e1e; color: #fff; }
            QTabBar::tab:hover { background: #2d2d30; }
        """)

    def _reindex_vault(self):
        self._set_status("Indexing vault…")
        QApplication.processEvents()
        count = 0
        for abs_path in self.vault.list_notes():
            rel = self.vault.rel_path(abs_path)
            try:
                content = Path(abs_path).read_text(encoding="utf-8",
                                                   errors="surrogateescape")
            except (OSError, UnicodeDecodeError):
                continue
            self.backlinks.index_file(rel, content)
            self.tags.index_file(rel, content)
            self.search.index(rel, Path(rel).stem, content)
            count += 1
        self._set_status(f"Indexed {count} notes")

    def _on_vault_reloaded(self):
        current = {self.vault.rel_path(p) for p in self.vault.list_notes()}
        for rel in current:
            abs_p = self.vault.abs_path(rel)
            try:
                content = abs_p.read_text(encoding="utf-8",
                                          errors="surrogateescape")
            except (OSError, UnicodeDecodeError):
                continue
            self.backlinks.index_file(rel, content)
            self.tags.index_file(rel, content)
            self.search.index(rel, Path(rel).stem, content)
        self.file_tree.setRootIndex(self.file_model.index(str(self.vault_path)))
        self._refresh_tags()
        self._refresh_graph()

    def _refresh_tags(self):
        self.tags_list.clear()
        for tag, count in self.tags.all_tags():
            item = QListWidgetItem(f"#{tag}  ({count})")
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.tags_list.addItem(item)

    def _refresh_graph(self):
        notes = [self.vault.rel_path(p) for p in self.vault.list_notes()]
        edges: list[tuple[str, str]] = []
        for src, tgt in self.backlinks.all_edges():
            tgt_rel = self._resolve_link(tgt)
            if tgt_rel:
                edges.append((src, tgt_rel))
        self.graph_widget.load_graph(notes, edges)

    def _resolve_link(self, target: str) -> str | None:
        target = target.strip()
        stem = Path(target).stem.lower()
        for abs_path in self.vault.list_notes():
            rel = self.vault.rel_path(abs_path)
            if rel == target or rel == target + MD_EXT:
                return rel
            if Path(rel).stem.lower() == stem:
                return rel
        return None

    def _current_pane(self) -> LivePreviewPane | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, LivePreviewPane) else None

    def _current_editor(self):
        pane = self._current_pane()
        return pane.editor if pane else None

    def _current_rel_path(self):
        pane = self._current_pane()
        return pane.rel_path if pane else None

    def _open_note(self, rel: str):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, LivePreviewPane) and w.rel_path == rel:
                self.tabs.setCurrentIndex(i)
                return

        pane = LivePreviewPane(self, vault=self.vault,
                               settings=self.settings, rel_path=rel)
        pane.load(self.vault.read(rel))
        pane.editor.content_changed.connect(
            lambda text, r=rel: self._on_note_edited(r, text)
        )
        pane.preview.link_clicked.connect(self.open_wikilink)

        idx = self.tabs.addTab(pane, Path(rel).stem)
        self.tabs.setTabToolTip(idx, rel)
        self.tabs.setCurrentIndex(idx)
        self._update_backlinks(rel)
        self._set_status(f"Opened {rel}")

    def _on_note_edited(self, rel: str, text: str):
        self.vault.write(rel, text)
        self.backlinks.index_file(rel, text)
        self.tags.index_file(rel, text)
        self.search.index(rel, Path(rel).stem, text)

    def _close_tab(self, index: int):
        w = self.tabs.widget(index)
        self.tabs.removeTab(index)
        if w is not None:
            w.deleteLater()

    def _on_tab_changed(self, index: int):
        rel = self._current_rel_path()
        if rel:
            self._update_backlinks(rel)
            self.setWindowTitle(
                f"{APP_NAME} — {self.vault_path.name} — {Path(rel).stem}"
            )

    def _on_tree_double_click(self, index: QModelIndex):
        path = self.file_model.filePath(index)
        if Path(path).is_file() and path.lower().endswith(MD_EXT):
            self._open_note(self.vault.rel_path(path))

    def _tree_context_menu(self, pos):
        index = self.file_tree.indexAt(pos)
        menu = QMenu(self)
        menu.addAction("New Note", self._new_note)
        menu.addAction("New Folder", self._new_folder)
        if index.isValid():
            path = self.file_model.filePath(index)
            if path:
                rel = self.vault.rel_path(path)
                menu.addSeparator()
                menu.addAction("Rename…", lambda: self._rename_item(rel))
                menu.addAction("Delete", lambda: self._delete_item(rel))
                menu.addSeparator()
                menu.addAction(
                    "Reveal in Explorer",
                    lambda: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(str(Path(path).parent))
                    ),
                )
        menu.exec(self.file_tree.viewport().mapToGlobal(pos))

    def _new_note(self):
        name, ok = QInputDialog.getText(self, "New Note", "Note name:")
        if not ok or not name.strip():
            return
        rel = name.strip()
        if not rel.lower().endswith(MD_EXT):
            rel += MD_EXT
        if not self.vault.create(rel):
            QMessageBox.warning(self, "Chert", f"'{rel}' already exists.")
            return
        self._open_note(rel)
        self._refresh_graph()

    def _new_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        p = self.vault_path / name.strip()
        try:
            p.mkdir(parents=True, exist_ok=False)
        except OSError as e:
            QMessageBox.warning(self, "Chert", f"Failed: {e}")

    def _rename_item(self, rel: str):
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=Path(rel).name
        )
        if not ok or not new_name.strip():
            return
        new_rel = str(Path(rel).parent / new_name.strip()).replace("\\", "/")
        if new_rel == rel:
            return
        if self.vault.rename(rel, new_rel):
            self._reindex_vault()
            self._refresh_graph()

    def _delete_item(self, rel: str):
        r = QMessageBox.question(
            self, "Delete",
            f"Delete '{rel}'? This cannot be undone.",
        )
        if r == QMessageBox.StandardButton.Yes:
            if self.vault.delete(rel):
                self.backlinks.remove_file(rel)
                self.tags.index_file(rel, "")
                self.search.remove(rel)
                for i in range(self.tabs.count()):
                    w = self.tabs.widget(i)
                    if isinstance(w, LivePreviewPane) and w.rel_path == rel:
                        self._close_tab(i)
                        break
                self._refresh_graph()

    def _save_current(self):
        pane = self._current_pane()
        if not pane or not pane.rel_path:
            return
        self.vault.write(pane.rel_path, pane.text())
        self._set_status(f"Saved {pane.rel_path}")

    def _switch_vault(self):
        dlg = VaultPickerDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected:
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()),
                 str(dlg.selected)],
                creationflags=(0x00000010 if sys.platform == "win32" else 0),
            )

    def _reveal_vault(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.vault_path)))

    def _update_backlinks(self, rel: str):
        self.backlinks_list.clear()
        bl = self.backlinks.backlinks(rel)
        if not bl:
            item = QListWidgetItem("(no backlinks)")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.backlinks_list.addItem(item)
            return
        for b in bl:
            label = b["source"]
            if b["context"]:
                ctx = b["context"][:120]
                label += f"\n   {ctx}…"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, b["source"])
            self.backlinks_list.addItem(item)

    def _open_backlink(self, item):
        src = item.data(Qt.ItemDataRole.UserRole)
        if src:
            self._open_note(src)

    def _filter_by_tag(self, item):
        tag = item.data(Qt.ItemDataRole.UserRole)
        if not tag:
            return
        files = self.tags.files_for_tag(tag)
        self.search_box.setText(f"#{tag}")
        self._set_status(f"#{tag}: {len(files)} notes")

    def _focus_search(self):
        self.search_box.setFocus()
        self.search_box.selectAll()

    def _on_search_text(self, text: str):
        if not text.strip():
            return
        results = self.search.search(text, limit=30)
        self.backlinks_dock.setWindowTitle(f"Search ({len(results)})")
        self.backlinks_list.clear()
        for r in results:
            label = f"{Path(r['path']).stem}\n   {r['snippet'][:140]}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, r["path"])
            self.backlinks_list.addItem(item)
        self.backlinks_dock.show()

    def _run_search(self):
        q = self.search_box.text()
        if not q.strip():
            return
        results = self.search.search(q, limit=50)
        if not results:
            self._set_status("No results")
            return
        self._open_note(results[0]["path"])
        self._set_status(f"{len(results)} results")

    def open_wikilink(self, target: str):
        target = target.strip()
        rel = self._resolve_link(target)
        if rel:
            self._open_note(rel)
            return
        r = QMessageBox.question(
            self, "Create note?",
            f"'{target}' doesn't exist. Create it?",
        )
        if r == QMessageBox.StandardButton.Yes:
            new_rel = target if target.lower().endswith(MD_EXT) else target + MD_EXT
            self.vault.create(new_rel)
            self._open_note(new_rel)
            self._refresh_graph()

    def _toggle_graph(self):
        visible = not self.graph_dock.isVisible()
        self.graph_dock.setVisible(visible)
        if visible:
            QTimer.singleShot(150, self.graph_widget.fit)

    def _toggle_backlinks(self):
        self.backlinks_dock.setVisible(not self.backlinks_dock.isVisible())

    def _toggle_tags(self):
        self.tags_dock.setVisible(not self.tags_dock.isVisible())

    def _set_split(self, ratio: float):
        pane = self._current_pane()
        if not pane:
            return
        total = sum(pane.sizes()) or 1200
        if ratio <= 0.0:
            pane.setSizes([0, total])
        elif ratio >= 1.0:
            pane.setSizes([total, 0])
        else:
            pane.setSizes([int(total * ratio), int(total * (1 - ratio))])

    def _on_graph_node_clicked(self, node_id: str):
        rel = self.vault.rel_path(node_id)
        self._open_note(rel)

    def _set_status(self, msg: str):
        self.status.showMessage(msg, 5000)

    def _about(self):
        engine = "QtWebEngine" if HAS_WEBENGINE else "QTextEdit fallback"
        QMessageBox.about(
            self,
            f"About {APP_NAME}",
            f"<h3>{APP_NAME} v{APP_VERSION}</h3>"
            f"<p>A local-first Markdown knowledge base.</p>"
            f"<p>PyQt{'6' if PYQT6 else '5'} · Python "
            f"{sys.version.split()[0]} · {engine}</p>",
        )

    def _show_diagnostics(self):
        env = diagnose_environment()
        lines = [f"<b>{k}</b>: {v}" for k, v in env.items()]
        QMessageBox.information(
            self, "Environment Diagnostics",
            "<br>".join(lines),
        )

    def closeEvent(self, event):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, LivePreviewPane) and w.rel_path:
                self.vault.write(w.rel_path, w.text())
        self.settings.flush()
        for mgr in (self.backlinks, self.search, self.tags):
            try:
                mgr.close()
            except Exception:
                pass
        super().closeEvent(event)


# ── Entry point ─────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Base, QColor(30, 30, 30))
    pal.setColor(QPalette.ColorRole.Text, QColor(212, 212, 212))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(212, 212, 212))
    pal.setColor(QPalette.ColorRole.Button, QColor(45, 45, 48))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(212, 212, 212))
    app.setPalette(pal)

    vault: Path | None = None
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        vault = Path(sys.argv[1])
    else:
        cfg = load_app_config()
        recents = [r for r in cfg.get("recent_vaults", []) if Path(r).is_dir()]
        if recents:
            vault = Path(recents[0])
        else:
            dlg = VaultPickerDialog()
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected:
                sys.exit(0)
            vault = dlg.selected

    win = ChertMainWindow(vault)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()