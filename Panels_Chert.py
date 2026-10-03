"""
Panels_Chert.py — Content panels for the two sidebars.

FileExplorerPanel  — tree of vault notes, inline rename, context menu
SearchPanel        — vault-wide FTS with query input
TagsPanel          — tag list with counts
BacklinksPanel     — linked + unlinked mentions of current note
OutlinePanel       — heading tree of current note
LocalGraphPanel    — miniature force graph of the current note
"""

import re
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QMenu, QInputDialog, QMessageBox, QFrame, QSizePolicy,
)

from Chert_Managers import MD_EXT
from Markdown_Chert import extract_headings
from Graph_Chert import ForceGraphView, GraphBuilder


# ══════════════════════════════════════════════════════════════════════════
# File explorer
# ══════════════════════════════════════════════════════════════════════════

class FileExplorerPanel(QWidget):
    """Tree of vault notes with inline rename and context menu."""

    note_opened = pyqtSignal(str)
    note_created = pyqtSignal(str)
    folder_created = pyqtSignal(str)

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.vault = vault
        self._items_by_path = {}
        self._built = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with new-note / new-folder buttons
        header = QWidget()
        header.setFixedHeight(30)
        h = QHBoxLayout(header)
        h.setContentsMargins(8, 2, 8, 2)
        h.setSpacing(4)

        title = QLabel("FILES")
        title.setStyleSheet("font-size: 10px; letter-spacing: 1px; opacity: .7;")
        h.addWidget(title)
        h.addStretch()

        new_btn = QPushButton("⊕")
        new_btn.setFixedSize(22, 22)
        new_btn.setToolTip("New note (Ctrl+N)")
        new_btn.clicked.connect(self._new_note)
        h.addWidget(new_btn)

        folder_btn = QPushButton("▣")
        folder_btn.setFixedSize(22, 22)
        folder_btn.setToolTip("New folder")
        folder_btn.clicked.connect(self._new_folder)
        h.addWidget(folder_btn)

        layout.addWidget(header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.setAnimated(True)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.tree, 1)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._built:
            self.rebuild()
            self._built = True

    def rebuild(self):
        self.tree.clear()
        self._items_by_path.clear()

        notes = sorted(self.vault.rel_path(p) for p in self.vault.list_notes())
        root_items = {}
        folders = {}

        for rel in notes:
            parts = rel.split("/")
            parent_item = None
            path_so_far = ""
            for i, part in enumerate(parts[:-1]):
                path_so_far = f"{path_so_far}/{part}" if path_so_far else part
                if path_so_far in folders:
                    parent_item = folders[path_so_far]
                else:
                    item = QTreeWidgetItem([part])
                    item.setData(0, Qt.ItemDataRole.UserRole, ("folder", path_so_far))
                    if parent_item is None:
                        self.tree.addTopLevelItem(item)
                    else:
                        parent_item.addChild(item)
                    folders[path_so_far] = item
                    parent_item = item

            leaf = QTreeWidgetItem([parts[-1]])
            leaf.setData(0, Qt.ItemDataRole.UserRole, ("file", rel))
            if parent_item is None:
                self.tree.addTopLevelItem(leaf)
            else:
                parent_item.addChild(leaf)
            self._items_by_path[rel] = leaf

        self.tree.expandAll()

    def _on_double_click(self, item, _col):
        kind, path = item.data(0, Qt.ItemDataRole.UserRole) or (None, None)
        if kind == "file":
            self.note_opened.emit(path)

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            menu = QMenu(self)
            menu.addAction("New Note", self._new_note)
            menu.addAction("New Folder", self._new_folder)
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return

        kind, path = item.data(0, Qt.ItemDataRole.UserRole) or (None, None)
        menu = QMenu(self)
        if kind == "file":
            menu.addAction("Open", lambda: self.note_opened.emit(path))
            menu.addSeparator()
            menu.addAction("Rename…", lambda: self._rename(path))
            menu.addAction("Delete", lambda: self._delete(path))
            menu.addSeparator()
            menu.addAction("Reveal in Explorer",
                           lambda: self._reveal(path))
        elif kind == "folder":
            menu.addAction("New Note Here", self._new_note)
            menu.addAction("Rename Folder…", lambda: self._rename_folder(path))
            menu.addAction("Delete Folder", lambda: self._delete_folder(path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _new_note(self):
        name, ok = QInputDialog.getText(self, "New Note", "Note name:")
        if not ok or not name.strip():
            return
        rel = name.strip()
        if not rel.lower().endswith(MD_EXT):
            rel += MD_EXT
        if self.vault.create(rel):
            self.rebuild()
            self.note_created.emit(rel)

    def _new_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        rel = name.strip()
        try:
            (self.vault.vault_path / rel).mkdir(parents=True, exist_ok=False)
            self.rebuild()
            self.folder_created.emit(rel)
        except OSError as e:
            QMessageBox.warning(self, "Chert", f"Failed: {e}")

    def _rename(self, rel):
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=Path(rel).name
        )
        if not ok or not new_name.strip():
            return
        new_rel = str(Path(rel).parent / new_name.strip()).replace("\\", "/")
        if new_rel == rel:
            return
        if self.vault.rename(rel, new_rel):
            self.rebuild()

    def _rename_folder(self, folder_rel):
        new_name, ok = QInputDialog.getText(
            self, "Rename Folder", "New name:", text=Path(folder_rel).name
        )
        if not ok or not new_name.strip():
            return
        old_p = self.vault.vault_path / folder_rel
        new_p = old_p.parent / new_name.strip()
        try:
            old_p.rename(new_p)
            self.rebuild()
        except OSError as e:
            QMessageBox.warning(self, "Chert", f"Failed: {e}")

    def _delete(self, rel):
        r = QMessageBox.question(
            self, "Delete",
            f"Delete '{rel}'? This cannot be undone.",
        )
        if r == QMessageBox.StandardButton.Yes:
            if self.vault.delete(rel):
                self.rebuild()

    def _delete_folder(self, folder_rel):
        r = QMessageBox.question(
            self, "Delete Folder",
            f"Delete folder '{folder_rel}' and all its contents?",
        )
        if r == QMessageBox.StandardButton.Yes:
            import shutil
            p = self.vault.vault_path / folder_rel
            try:
                shutil.rmtree(p)
                self.rebuild()
            except OSError as e:
                QMessageBox.warning(self, "Chert", f"Failed: {e}")

    def _reveal(self, rel):
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        p = self.vault.abs_path(rel)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p.parent)))

    def highlight_note(self, rel):
        item = self._items_by_path.get(rel)
        if item:
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)


# ══════════════════════════════════════════════════════════════════════════
# Search
# ══════════════════════════════════════════════════════════════════════════

class SearchPanel(QWidget):
    result_activated = pyqtSignal(str)

    def __init__(self, search_index, parent=None):
        super().__init__(parent)
        self.search = search_index

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        self.query = QLineEdit()
        self.query.setPlaceholderText("Search notes…")
        self.query.textChanged.connect(self._on_query_changed)
        layout.addWidget(self.query)

        self.results = QListWidget()
        self.results.itemActivated.connect(self._activate)
        self.results.itemDoubleClicked.connect(self._activate)
        layout.addWidget(self.results, 1)

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self._run)

    def focus_query(self):
        self.query.setFocus()
        self.query.selectAll()

    def _on_query_changed(self, _text):
        self._debounce.start()

    def _run(self):
        q = self.query.text().strip()
        self.results.clear()
        if not q:
            return
        for r in self.search.search(q, limit=50):
            item = QListWidgetItem(f"{Path(r['path']).stem}\n  {r['snippet'][:120]}")
            item.setData(Qt.ItemDataRole.UserRole, r["path"])
            self.results.addItem(item)

    def _activate(self, item):
        rel = item.data(Qt.ItemDataRole.UserRole)
        if rel:
            self.result_activated.emit(rel)


# ══════════════════════════════════════════════════════════════════════════
# Tags
# ══════════════════════════════════════════════════════════════════════════

class TagsPanel(QWidget):
    tag_activated = pyqtSignal(str)

    def __init__(self, tag_index, parent=None):
        super().__init__(parent)
        self.tags = tag_index

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._activate)
        layout.addWidget(self.list)

    def refresh(self):
        self.list.clear()
        for tag, count in self.tags.all_tags():
            item = QListWidgetItem(f"#{tag}   ({count})")
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.list.addItem(item)

    def _activate(self, item):
        tag = item.data(Qt.ItemDataRole.UserRole)
        if tag:
            self.tag_activated.emit(tag)


# ══════════════════════════════════════════════════════════════════════════
# Backlinks
# ══════════════════════════════════════════════════════════════════════════

class BacklinksPanel(QWidget):
    note_activated = pyqtSignal(str)

    def __init__(self, backlinks_index, parent=None):
        super().__init__(parent)
        self.backlinks = backlinks_index

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.section_label = QLabel("LINKED MENTIONS")
        self.section_label.setStyleSheet(
            "font-size: 10px; letter-spacing: 1px; opacity: .7; "
            "padding: 6px 10px;"
        )
        layout.addWidget(self.section_label)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._activate)
        layout.addWidget(self.list, 1)

    def set_note(self, rel):
        self.list.clear()
        if not rel:
            self.section_label.setText("LINKED MENTIONS")
            return
        mentions = self.backlinks.backlinks(rel)
        self.section_label.setText(f"LINKED MENTIONS  ({len(mentions)})")
        for b in mentions:
            label = Path(b["source"]).stem
            if b.get("context"):
                label += f"\n  {b['context'][:100]}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, b["source"])
            self.list.addItem(item)

    def _activate(self, item):
        rel = item.data(Qt.ItemDataRole.UserRole)
        if rel:
            self.note_activated.emit(rel)


# ══════════════════════════════════════════════════════════════════════════
# Outline
# ══════════════════════════════════════════════════════════════════════════

class OutlinePanel(QWidget):
    heading_activated = pyqtSignal(int)  # line number

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.itemClicked.connect(self._activate)
        layout.addWidget(self.tree)

    def set_content(self, text: str):
        self.tree.clear()
        if not text:
            return

        stack = [(self.tree.invisibleRootItem(), 0)]
        for level, title, line in extract_headings(text):
            while stack and stack[-1][1] >= level:
                stack.pop()
            parent = stack[-1][0] if stack else self.tree.invisibleRootItem()

            item = QTreeWidgetItem([title])
            item.setData(0, Qt.ItemDataRole.UserRole, line)
            font = item.font(0)
            font.setBold(level <= 2)
            item.setFont(0, font)

            if parent is self.tree.invisibleRootItem():
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            stack.append((item, level))

        self.tree.expandAll()

    def _activate(self, item, _col):
        line = item.data(0, Qt.ItemDataRole.UserRole)
        if line is not None:
            self.heading_activated.emit(line)


# ══════════════════════════════════════════════════════════════════════════
# Local graph
# ══════════════════════════════════════════════════════════════════════════

class LocalGraphPanel(QWidget):
    node_clicked = pyqtSignal(str)

    def __init__(self, vault, backlinks, parent=None):
        super().__init__(parent)
        self.vault = vault
        self.backlinks = backlinks

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = ForceGraphView(self)
        self.view.node_clicked.connect(self.node_clicked)
        layout.addWidget(self.view)
        # Small view — disable animations to keep it light
        self.view.config.repulsion = 3500.0
        self.view.config.spring_length = 60.0
        self.view.config.node_base_size = 4.0
        self.view.config.node_max_size = 12.0
        self.view.timer.setInterval(50)

    def set_note(self, rel):
        if not rel:
            self.view.clear_graph()
            return
        paths, edges = GraphBuilder.local_graph(
            self.vault, self.backlinks, rel, depth=1
        )
        self.view.build(paths, edges)
        QTimer.singleShot(120, self._fit)

    def _fit(self):
        if self.view.nodes:
            rect = self.view.scene.itemsBoundingRect()
            if rect.width() > 0 and rect.height() > 0:
                self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)