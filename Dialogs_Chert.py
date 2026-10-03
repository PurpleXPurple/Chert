"""
Dialogs_Chert.py — Command palette, quick switcher, settings, about.
"""

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QCheckBox, QComboBox,
    QFormLayout, QSpinBox, QDialogButtonBox, QWidget, QTabWidget,
    QScrollArea, QMessageBox, QFrame,
)


# ══════════════════════════════════════════════════════════════════════════
# Command palette
# ══════════════════════════════════════════════════════════════════════════

class CommandPalette(QDialog):
    """Ctrl+P — flat list of registered commands, fuzzy filtered."""

    command_triggered = pyqtSignal(str)

    def __init__(self, commands: list, parent=None):
        # commands: list of (id, name, shortcut) tuples
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setModal(True)
        self.setFixedSize(560, 400)

        self._commands = commands
        self._filtered = list(commands)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command…")
        self.input.textChanged.connect(self._filter)
        self.input.returnPressed.connect(self._execute_current)
        layout.addWidget(self.input)

        self.list = QListWidget()
        self.list.itemActivated.connect(self._execute_item)
        self.list.itemDoubleClicked.connect(self._execute_item)
        layout.addWidget(self.list, 1)

        self._populate()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Down:
            self._move(1)
            return
        if key == Qt.Key.Key_Up:
            self._move(-1)
            return
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def _populate(self):
        self.list.clear()
        for cid, name, shortcut in self._filtered:
            label = f"{name}    {shortcut}" if shortcut else name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cid)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _filter(self, text):
        q = text.lower().strip()
        if not q:
            self._filtered = list(self._commands)
        else:
            self._filtered = [
                c for c in self._commands
                if q in c[1].lower() or q in c[0].lower()
            ]
        self._populate()

    def _move(self, delta):
        row = self.list.currentRow() + delta
        if 0 <= row < self.list.count():
            self.list.setCurrentRow(row)

    def _execute_current(self):
        item = self.list.currentItem()
        if item:
            self._execute_item(item)

    def _execute_item(self, item):
        cid = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        self.command_triggered.emit(cid)


# ══════════════════════════════════════════════════════════════════════════
# Quick switcher
# ══════════════════════════════════════════════════════════════════════════

class QuickSwitcher(QDialog):
    """Ctrl+O — fuzzy note opener."""

    note_selected = pyqtSignal(str)

    def __init__(self, vault, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setModal(True)
        self.setFixedSize(560, 400)
        self.vault = vault

        self._notes = sorted(vault.rel_path(p) for p in vault.list_notes())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Open note by name…")
        self.input.textChanged.connect(self._filter)
        self.input.returnPressed.connect(self._open_current)
        layout.addWidget(self.input)

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(self._open_item)
        layout.addWidget(self.list, 1)

        self._populate(self._notes)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Down:
            self.list.setCurrentRow(min(self.list.currentRow() + 1,
                                        self.list.count() - 1))
            return
        if key == Qt.Key.Key_Up:
            self.list.setCurrentRow(max(self.list.currentRow() - 1, 0))
            return
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def _populate(self, notes):
        self.list.clear()
        for rel in notes[:200]:
            item = QListWidgetItem(rel)
            item.setData(Qt.ItemDataRole.UserRole, rel)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _filter(self, text):
        q = text.lower().strip()
        if not q:
            self._populate(self._notes)
            return
        matches = [n for n in self._notes if q in n.lower()]
        self._populate(matches)

    def _open_current(self):
        item = self.list.currentItem()
        if item:
            self._open_item(item)

    def _open_item(self, item):
        rel = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        self.note_selected.emit(rel)


# ══════════════════════════════════════════════════════════════════════════
# Settings
# ══════════════════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    settings_changed = pyqtSignal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._editor_tab(), "Editor")
        tabs.addTab(self._appearance_tab(), "Appearance")
        layout.addWidget(tabs, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._apply
        )
        layout.addWidget(buttons)

    def _editor_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self.font_edit = QLineEdit(self.settings.get("editor_font", "Consolas"))
        form.addRow("Editor font:", self.font_edit)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 32)
        self.font_size_spin.setValue(self.settings.get("editor_font_size", 13))
        form.addRow("Font size:", self.font_size_spin)

        self.tab_width_spin = QSpinBox()
        self.tab_width_spin.setRange(2, 8)
        self.tab_width_spin.setValue(self.settings.get("tab_width", 4))
        form.addRow("Tab width:", self.tab_width_spin)

        self.wrap_cb = QCheckBox()
        self.wrap_cb.setChecked(self.settings.get("line_wrap", True))
        form.addRow("Wrap lines:", self.wrap_cb)

        return w

    def _appearance_tab(self):
        w = QWidget()
        form = QFormLayout(w)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.settings.get("theme", "dark"))
        form.addRow("Theme:", self.theme_combo)

        self.preview_size_spin = QSpinBox()
        self.preview_size_spin.setRange(10, 28)
        self.preview_size_spin.setValue(self.settings.get("preview_font_size", 15))
        form.addRow("Preview size:", self.preview_size_spin)

        return w

    def _collect(self):
        self.settings.set("editor_font", self.font_edit.text().strip() or "Consolas")
        self.settings.set("editor_font_size", self.font_size_spin.value())
        self.settings.set("tab_width", self.tab_width_spin.value())
        self.settings.set("line_wrap", self.wrap_cb.isChecked())
        self.settings.set("theme", self.theme_combo.currentText())
        self.settings.set("preview_font_size", self.preview_size_spin.value())

    def _apply(self):
        self._collect()
        self.settings_changed.emit()

    def _accept(self):
        self._apply()
        self.accept()


# ══════════════════════════════════════════════════════════════════════════
# About
# ══════════════════════════════════════════════════════════════════════════

def show_about(parent, env: dict):
    QMessageBox.about(
        parent,
        "About Chert",
        f"<h3>Chert v{env.get('version', '1.0')}</h3>"
        f"<p>A local-first Markdown knowledge base.</p>"
        f"<p>PyQt6 · Python {env.get('python', '?')} · "
        f"{'QtWebEngine' if env.get('webengine') else 'QTextEdit fallback'}</p>",
    )