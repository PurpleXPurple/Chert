"""
UI_Chert.py — The Obsidian-like shell.

MainWindow:  ribbon + left sidebar + editor area + right sidebar + status
Ribbon:      vertical icon strip on the far left
SidebarHost: collapsible side panel with tabbed icons
EditorArea:  tabs + split-pane support + per-tab Live Preview
AppStatusBar: word count, line/col, backlink count, mode indicator
"""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QKeySequence, QFont, QPalette, QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QStackedWidget, QTabWidget, QToolBar,
    QStatusBar, QFrame, QSizePolicy, QMessageBox, QFileDialog,
    QDialog, QMenu,
)

from Chert_Managers import (
    VaultManager, BacklinkIndex, SearchIndex, TagIndex, ChertSettings,
    vault_settings_dir, load_app_config, save_app_config,
    MD_EXT, HAS_WEBENGINE, diagnose_environment,
)
from Theme_Chert import get_theme, stylesheet, Icon
from Live_Preview import LivePreviewPane
from Graph_Chert import GraphWidget, ForceGraphView
from Panels_Chert import (
    FileExplorerPanel, SearchPanel, TagsPanel,
    BacklinksPanel, OutlinePanel, LocalGraphPanel,
)
from Dialogs_Chert import (
    CommandPalette, QuickSwitcher, SettingsDialog, show_about,
)


APP_NAME = "Chert"
APP_VERSION = "1.1.0"


# ══════════════════════════════════════════════════════════════════════════
# Ribbon
# ══════════════════════════════════════════════════════════════════════════

class RibbonButton(QPushButton):
    def __init__(self, glyph, tooltip, parent=None):
        super().__init__(glyph, parent)
        self.setFixedSize(36, 36)
        self.setToolTip(tooltip)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class Ribbon(QWidget):
    """Vertical icon strip on the far left, Obsidian-style."""

    command_triggered = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(44)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(2)

        self._add(layout, "files", Icon.FILES, "Files (Ctrl+Shift+E)")
        self._add(layout, "search", Icon.SEARCH, "Search (Ctrl+Shift+F)")
        self._add(layout, "quick_switch", Icon.NEW, "Quick switcher (Ctrl+O)")
        self._add(layout, "graph", Icon.GRAPH, "Graph view (Ctrl+G)")

        layout.addStretch()

        self._add(layout, "palette", Icon.MENU, "Command palette (Ctrl+P)")
        self._add(layout, "theme", Icon.THEME, "Toggle theme")
        self._add(layout, "settings", Icon.SETTINGS, "Settings")

    def _add(self, layout, cid, glyph, tooltip):
        btn = RibbonButton(glyph, tooltip)
        btn.clicked.connect(lambda _, c=cid: self.command_triggered.emit(c))
        layout.addWidget(btn)
        return btn


# ══════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════

class SidebarHost(QWidget):
    """
    Collapsible side panel. Contains a narrow icon tab bar plus a stack of
    content panels. Clicking an icon switches the visible panel.
    """

    def __init__(self, panels: dict, side: str, parent=None):
        # panels: dict[tab_id] = (glyph, tooltip, widget)
        super().__init__(parent)
        self.setMinimumWidth(0)
        self._panels = panels
        self._side = side
        self._tab_ids = list(panels.keys())
        self._active = self._tab_ids[0] if self._tab_ids else None
        self._collapsed = False
        self._expanded_width = 260

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Panel stack
        self.stack = QStackedWidget()
        for tid, (_glyph, _tip, widget) in panels.items():
            self.stack.addWidget(widget)

        # Tab bar (icons in a vertical strip; opposite side from panel)
        self.tabbar = QWidget()
        self.tabbar.setFixedWidth(32)
        tab_layout = QVBoxLayout(self.tabbar)
        tab_layout.setContentsMargins(2, 6, 2, 6)
        tab_layout.setSpacing(2)

        self._tab_buttons = {}
        for tid, (glyph, tip, _w) in panels.items():
            b = QPushButton(glyph)
            b.setFixedSize(28, 28)
            b.setFlat(True)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, t=tid: self.activate(t))
            tab_layout.addWidget(b)
            self._tab_buttons[tid] = b
        tab_layout.addStretch()

        # Assemble: left sidebar has panel then tab bar; right sidebar has
        # tab bar then panel.
        if side == "left":
            outer.addWidget(self.stack, 1)
            outer.addWidget(self.tabbar)
        else:
            outer.addWidget(self.tabbar)
            outer.addWidget(self.stack, 1)

        self.setFixedWidth(self._expanded_width)
        if self._active:
            self._select(self._active)

    def _select(self, tid):
        idx = self._tab_ids.index(tid)
        self.stack.setCurrentIndex(idx)
        for t, b in self._tab_buttons.items():
            b.setStyleSheet(
                "QPushButton { color: palette(text); }"
                if t != tid else
                "QPushButton { color: palette(highlight); }"
            )
        self._active = tid

    def activate(self, tid):
        if self._collapsed:
            self.toggle()
        self._select(tid)

    def toggle(self):
        self._collapsed = not self._collapsed
        self.setFixedWidth(32 if self._collapsed else self._expanded_width)
        if self._collapsed:
            self.stack.hide()
        else:
            self.stack.show()


# ══════════════════════════════════════════════════════════════════════════
# Editor area (tabs + preview panes)
# ══════════════════════════════════════════════════════════════════════════

class EditorArea(QWidget):
    """Tabbed note editor. Each tab is a LivePreviewPane."""

    note_changed = pyqtSignal(str)
    note_saved = pyqtSignal(str, str)
    tab_changed = pyqtSignal(str)

    def __init__(self, vault, settings, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs, 1)

    def open_note(self, rel):
        # If already open, focus it
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, LivePreviewPane) and w.rel_path == rel:
                self.tabs.setCurrentIndex(i)
                return

        pane = LivePreviewPane(
            self, vault=self.vault, settings=self.settings, rel_path=rel,
        )
        pane.load(self.vault.read(rel))
        pane.editor.content_changed.connect(
            lambda text, r=rel: self._on_content_changed(r, text)
        )
        pane.preview.link_clicked.connect(self._on_wikilink)

        idx = self.tabs.addTab(pane, Path(rel).stem)
        self.tabs.setTabToolTip(idx, rel)
        self.tabs.setCurrentIndex(idx)

    def current_rel(self):
        w = self.tabs.currentWidget()
        if isinstance(w, LivePreviewPane):
            return w.rel_path
        return None

    def current_pane(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, LivePreviewPane) else None

    def current_text(self):
        pane = self.current_pane()
        return pane.text() if pane else ""

    def save_current(self):
        pane = self.current_pane()
        if pane and pane.rel_path:
            self.vault.write(pane.rel_path, pane.text())
            self.note_saved.emit(pane.rel_path, pane.text())

    def close_current(self):
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self._close_tab(idx)

    def _close_tab(self, idx):
        w = self.tabs.widget(idx)
        self.tabs.removeTab(idx)
        if w is not None:
            w.deleteLater()

    def _on_tab_changed(self, _idx):
        rel = self.current_rel()
        if rel:
            self.tab_changed.emit(rel)

    def _on_content_changed(self, rel, text):
        self.vault.write(rel, text)
        self.note_changed.emit(rel)

    def _on_wikilink(self, target):
        # Resolve and open, or offer to create.
        rel = self._resolve(target)
        if rel:
            self.open_note(rel)
            return
        r = QMessageBox.question(
            self, "Create note?",
            f"'{target}' doesn't exist. Create it?",
        )
        if r == QMessageBox.StandardButton.Yes:
            new_rel = target if target.lower().endswith(MD_EXT) else target + MD_EXT
            if self.vault.create(new_rel):
                self.open_note(new_rel)

    def _resolve(self, target):
        target = target.strip()
        stem = Path(target).stem.lower()
        for p in self.vault.list_notes():
            rel = self.vault.rel_path(p)
            if rel == target or rel == target + MD_EXT:
                return rel
            if Path(rel).stem.lower() == stem:
                return rel
        return None


# ══════════════════════════════════════════════════════════════════════════
# Status bar
# ══════════════════════════════════════════════════════════════════════════

class AppStatusBar(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words_label = QLabel("0 words")
        self.pos_label = QLabel("Ln 1, Col 1")
        self.backlinks_label = QLabel("0 backlinks")
        self.mode_label = QLabel("Markdown")

        for w in (self.words_label, self.pos_label,
                  self.backlinks_label, self.mode_label):
            w.setStyleSheet("color: #ffffff; padding: 0 10px;")

        self.addPermanentWidget(self.pos_label)
        self.addPermanentWidget(self.words_label)
        self.addPermanentWidget(self.backlinks_label)
        self.addPermanentWidget(self.mode_label)

    def set_words(self, n):
        self.words_label.setText(f"{n:,} words")

    def set_position(self, line, col):
        self.pos_label.setText(f"Ln {line}, Col {col}")

    def set_backlinks(self, n):
        self.backlinks_label.setText(f"{n} backlinks")


# ══════════════════════════════════════════════════════════════════════════
# Main window
# ══════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self, vault_path: Path):
        super().__init__()
        self.vault_path = Path(vault_path).resolve()

        # Managers
        self.settings = ChertSettings(self.vault_path)
        self.vault = VaultManager(self.vault_path)
        cfg_dir = vault_settings_dir(self.vault_path)
        self.backlinks = BacklinkIndex(cfg_dir / "backlinks.db")
        self.search = SearchIndex(cfg_dir / "search.db")
        self.tags = TagIndex(cfg_dir / "tags.db")

        # Theme
        self.theme = get_theme(self.settings.get("theme", "dark"))

        # Recent vaults bookkeeping
        cfg = load_app_config()
        recents = [r for r in cfg.get("recent_vaults", []) if Path(r).is_dir()]
        s = str(self.vault_path)
        if s in recents:
            recents.remove(s)
        recents.insert(0, s)
        cfg["recent_vaults"] = recents[:10]
        save_app_config(cfg)

        self._commands = []
        self._build_ui()
        self._build_menus()
        self._register_commands()
        self._reindex_vault()
        self._refresh_all_panels()
        self.vault.vault_reloaded.connect(self._on_vault_reloaded)

    # ── construction ────────────────────────────────────────────────────
    def _build_ui(self):
        self.setWindowTitle(f"{APP_NAME} — {self.vault_path.name}")
        self.resize(1440, 900)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Ribbon
        self.ribbon = Ribbon(self)
        self.ribbon.command_triggered.connect(self._on_ribbon_command)
        outer.addWidget(self.ribbon)

        # Splitter: [left sidebar] [editor] [right sidebar]
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        outer.addWidget(self.splitter, 1)

        # Left sidebar
        self.files_panel = FileExplorerPanel(self.vault)
        self.files_panel.note_opened.connect(self._open_note)
        self.search_panel = SearchPanel(self.search)
        self.search_panel.result_activated.connect(self._open_note)
        self.tags_panel = TagsPanel(self.tags)
        self.tags_panel.tag_activated.connect(self._on_tag_activated)

        self.left_sidebar = SidebarHost({
            "files": (Icon.FILES, "Files", self.files_panel),
            "search": (Icon.SEARCH, "Search", self.search_panel),
            "tags": (Icon.TAGS, "Tags", self.tags_panel),
        }, side="left")

        # Editor
        self.editor_area = EditorArea(self.vault, self.settings)
        self.editor_area.note_changed.connect(self._on_note_edited)
        self.editor_area.tab_changed.connect(self._on_active_note_changed)

        # Right sidebar
        self.backlinks_panel = BacklinksPanel(self.backlinks)
        self.backlinks_panel.note_activated.connect(self._open_note)
        self.outline_panel = OutlinePanel()
        self.outline_panel.heading_activated.connect(self._on_heading_clicked)
        self.local_graph_panel = LocalGraphPanel(self.vault, self.backlinks)
        self.local_graph_panel.node_clicked.connect(self._open_note)

        self.right_sidebar = SidebarHost({
            "backlinks": (Icon.BACKLINKS, "Backlinks", self.backlinks_panel),
            "outline": (Icon.OUTLINE, "Outline", self.outline_panel),
            "graph": (Icon.LOCAL_GRAPH, "Local graph", self.local_graph_panel),
        }, side="right")

        self.splitter.addWidget(self.left_sidebar)
        self.splitter.addWidget(self.editor_area)
        self.splitter.addWidget(self.right_sidebar)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([260, 900, 280])

        # Status bar
        self.status = AppStatusBar(self)
        self.setStatusBar(self.status)

        # Full-screen graph (hidden modal)
        self.full_graph = None

        # Focus tracking for word count
        self._pos_timer = QTimer(self)
        self._pos_timer.setInterval(400)
        self._pos_timer.timeout.connect(self._update_position)
        self._pos_timer.start()

    def _build_menus(self):
        mb = self.menuBar()

        fm = mb.addMenu("&File")
        self._add_action(fm, "New Note", "Ctrl+N", self._new_note)
        self._add_action(fm, "Open Vault (new window)…", None, self._switch_vault)
        fm.addSeparator()
        self._add_action(fm, "Save", "Ctrl+S", self.editor_area.save_current)
        self._add_action(fm, "Close Tab", "Ctrl+W", self.editor_area.close_current)
        fm.addSeparator()
        self._add_action(fm, "Exit", "Ctrl+Q", self.close)

        em = mb.addMenu("&Edit")
        self._add_action(em, "Undo", "Ctrl+Z",
                         lambda: self._editor_call("undo"))
        self._add_action(em, "Redo", "Ctrl+Y",
                         lambda: self._editor_call("redo"))
        em.addSeparator()
        self._add_action(em, "Search in Vault", "Ctrl+Shift+F",
                         lambda: self._on_ribbon_command("search"))

        vm = mb.addMenu("&View")
        self._add_action(vm, "Toggle Left Sidebar", "Ctrl+\\",
                         self.left_sidebar.toggle)
        self._add_action(vm, "Toggle Right Sidebar", "Ctrl+Shift+\\",
                         self.right_sidebar.toggle)
        vm.addSeparator()
        self._add_action(vm, "Graph View", "Ctrl+G",
                         lambda: self._on_ribbon_command("graph"))
        self._add_action(vm, "Command Palette", "Ctrl+P",
                         lambda: self._on_ribbon_command("palette"))
        self._add_action(vm, "Quick Switcher", "Ctrl+O",
                         lambda: self._on_ribbon_command("quick_switch"))
        vm.addSeparator()
        self._add_action(vm, "Toggle Theme", None,
                         lambda: self._on_ribbon_command("theme"))

        hm = mb.addMenu("&Help")
        self._add_action(hm, "About Chert", None, self._about)
        self._add_action(hm, "Environment Diagnostics", None, self._diagnostics)

    def _add_action(self, menu, name, shortcut, slot):
        a = QAction(name, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        menu.addAction(a)
        return a

    def _register_commands(self):
        self._commands = [
            ("new_note", "New Note", "Ctrl+N"),
            ("open_vault", "Open Vault", "Ctrl+O"),
            ("save", "Save", "Ctrl+S"),
            ("close_tab", "Close Tab", "Ctrl+W"),
            ("quick_switch", "Quick Switcher", "Ctrl+O"),
            ("palette", "Command Palette", "Ctrl+P"),
            ("search", "Search", "Ctrl+Shift+F"),
            ("graph", "Graph View", "Ctrl+G"),
            ("toggle_left", "Toggle Left Sidebar", "Ctrl+\\"),
            ("toggle_right", "Toggle Right Sidebar", "Ctrl+Shift+\\"),
            ("theme", "Toggle Theme", None),
            ("settings", "Open Settings", None),
            ("about", "About Chert", None),
        ]

    # ── ribbon / commands ───────────────────────────────────────────────
    def _on_ribbon_command(self, cid):
        if cid == "files":
            self.left_sidebar.activate("files")
        elif cid == "search":
            self.left_sidebar.activate("search")
            self.search_panel.focus_query()
        elif cid == "tags":
            self.left_sidebar.activate("tags")
        elif cid == "quick_switch":
            self._open_quick_switch()
        elif cid == "graph":
            self._open_full_graph()
        elif cid == "palette":
            self._open_palette()
        elif cid == "theme":
            self._toggle_theme()
        elif cid == "settings":
            self._open_settings()
        elif cid == "new_note":
            self._new_note()
        elif cid == "save":
            self.editor_area.save_current()
        elif cid == "close_tab":
            self.editor_area.close_current()
        elif cid == "open_vault":
            self._switch_vault()
        elif cid == "toggle_left":
            self.left_sidebar.toggle()
        elif cid == "toggle_right":
            self.right_sidebar.toggle()
        elif cid == "about":
            self._about()

    def _open_palette(self):
        dlg = CommandPalette(self._commands, self)
        dlg.command_triggered.connect(self._on_ribbon_command)
        dlg.exec()

    def _open_quick_switch(self):
        dlg = QuickSwitcher(self.vault, self)
        dlg.note_selected.connect(self._open_note)
        dlg.exec()

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        dlg.settings_changed.connect(self._apply_settings)
        dlg.exec()

    def _apply_settings(self):
        self.settings.flush()
        self.theme = get_theme(self.settings.get("theme", "dark"))
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(stylesheet(self.theme))

    def _toggle_theme(self):
        cur = self.settings.get("theme", "dark")
        self.settings.set("theme", "light" if cur == "dark" else "dark")
        self._apply_settings()

    def _open_full_graph(self):
        from Graph_Chert import GraphWidget
        dlg = QDialog(self)
        dlg.setWindowTitle("Graph View")
        dlg.resize(1100, 700)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        gw = GraphWidget(dlg)
        gw.view.node_clicked.connect(self._open_note)
        layout.addWidget(gw)

        notes = [self.vault.rel_path(p) for p in self.vault.list_notes()]
        edges = []
        for src, tgt in self.backlinks.all_edges():
            r = self.editor_area._resolve(tgt)
            if r:
                edges.append((src, r))
        gw.load_graph(notes, edges)
        QTimer.singleShot(200, gw.fit)
        dlg.exec()

    # ── note handling ───────────────────────────────────────────────────
    def _open_note(self, rel):
        if not rel:
            return
        self.editor_area.open_note(rel)
        self.files_panel.highlight_note(rel)
        self._on_active_note_changed(rel)

    def _new_note(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Note", "Note name:")
        if not ok or not name.strip():
            return
        rel = name.strip()
        if not rel.lower().endswith(MD_EXT):
            rel += MD_EXT
        if not self.vault.create(rel):
            QMessageBox.warning(self, "Chert", f"'{rel}' already exists.")
            return
        self.files_panel.rebuild()
        self._open_note(rel)

    def _on_note_edited(self, rel):
        text = self.editor_area.current_text()
        self.backlinks.index_file(rel, text)
        self.tags.index_file(rel, text)
        self.search.index(rel, Path(rel).stem, text)
        self._update_word_count(text)
        self.outline_panel.set_content(text)

    def _on_active_note_changed(self, rel):
        self.setWindowTitle(
            f"{APP_NAME} — {self.vault_path.name} — {Path(rel).stem}"
        )
        self.backlinks_panel.set_note(rel)
        self.local_graph_panel.set_note(rel)
        text = self.editor_area.current_text()
        self.outline_panel.set_content(text)
        self._update_word_count(text)
        self.status.set_backlinks(len(self.backlinks.backlinks(rel)))

    def _on_tag_activated(self, tag):
        self.left_sidebar.activate("search")
        self.search_panel.query.setText(f"#{tag}")

    def _on_heading_clicked(self, line):
        pane = self.editor_area.current_pane()
        if not pane:
            return
        cursor = pane.editor.textCursor()
        block = pane.editor.document().findBlockByLineNumber(line)
        if block.isValid():
            cursor.setPosition(block.position())
            pane.editor.setTextCursor(cursor)
            pane.editor.centerCursor()
            pane.editor.setFocus()

    def _update_word_count(self, text):
        self.status.set_words(len(text.split()) if text else 0)

    def _update_position(self):
        pane = self.editor_area.current_pane()
        if not pane:
            return
        cursor = pane.editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.positionInBlock() + 1
        self.status.set_position(line, col)

    def _editor_call(self, method):
        pane = self.editor_area.current_pane()
        if pane and hasattr(pane.editor, method):
            getattr(pane.editor, method)()

    # ── vault / indexing ────────────────────────────────────────────────
    def _reindex_vault(self):
        self.status.showMessage("Indexing vault…", 3000)
        count = 0
        for abs_path in self.vault.list_notes():
            rel = self.vault.rel_path(abs_path)
            try:
                content = Path(abs_path).read_text(
                    encoding="utf-8", errors="surrogateescape"
                )
            except (OSError, UnicodeDecodeError):
                continue
            self.backlinks.index_file(rel, content)
            self.tags.index_file(rel, content)
            self.search.index(rel, Path(rel).stem, content)
            count += 1
        self.status.showMessage(f"Indexed {count} notes", 3000)

    def _on_vault_reloaded(self):
        self._reindex_vault()
        self._refresh_all_panels()

    def _refresh_all_panels(self):
        self.files_panel.rebuild()
        self.tags_panel.refresh()
        rel = self.editor_area.current_rel()
        if rel:
            self.backlinks_panel.set_note(rel)
            self.local_graph_panel.set_note(rel)

    def _switch_vault(self):
        import sys, subprocess
        path = QFileDialog.getExistingDirectory(self, "Open Vault")
        if not path:
            return
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve().parent / "Chert.py"),
             path],
            creationflags=(0x00000010 if sys.platform == "win32" else 0),
        )

    def _about(self):
        env = diagnose_environment()
        env["version"] = APP_VERSION
        env["python"] = env["python_version"].split()[0]
        show_about(self, env)

    def _diagnostics(self):
        env = diagnose_environment()
        lines = [f"<b>{k}</b>: {v}" for k, v in env.items()]
        QMessageBox.information(self, "Environment Diagnostics",
                                "<br>".join(lines))

    def closeEvent(self, event):
        self.editor_area.save_current()
        self.settings.flush()
        for mgr in (self.backlinks, self.search, self.tags):
            try:
                mgr.close()
            except Exception:
                pass
        super().closeEvent(event)