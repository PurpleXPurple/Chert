"""
Theme_Chert.py — Theme definitions and QSS generation.

Two themes: DARK (Obsidian-inspired) and LIGHT. Both produce a single
stylesheet string applied to the QApplication at startup and on theme
switch. Color constants are module-level so panels can reference them
directly without going through QSS for custom painting.
"""

from dataclasses import dataclass
from PyQt6.QtGui import QColor


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str            # window background
    surface: str       # panel background
    surface_alt: str   # hover / secondary surface
    border: str        # dividers, outlines
    text: str          # primary text
    text_muted: str    # secondary text
    accent: str        # interactive accent
    accent_hover: str
    selection: str     # selected list row
    editor_bg: str
    editor_text: str
    preview_bg: str
    preview_text: str
    ribbon_bg: str
    ribbon_fg: str
    ribbon_active: str
    status_bg: str
    status_fg: str
    scrollbar: str

    def qcolor(self, key: str) -> QColor:
        return QColor(getattr(self, key))


DARK = Theme(
    name="dark",
    bg="#1e1e1e",
    surface="#252526",
    surface_alt="#2d2d30",
    border="#333333",
    text="#d4d4d4",
    text_muted="#808080",
    accent="#8b5cf6",
    accent_hover="#a78bfa",
    selection="#094771",
    editor_bg="#1e1e1e",
    editor_text="#d4d4d4",
    preview_bg="#1e1e1e",
    preview_text="#d4d4d4",
    ribbon_bg="#181818",
    ribbon_fg="#9a9a9a",
    ribbon_active="#ffffff",
    status_bg="#007acc",
    status_fg="#ffffff",
    scrollbar="#424242",
)

LIGHT = Theme(
    name="light",
    bg="#ffffff",
    surface="#f8f8f8",
    surface_alt="#eeeeee",
    border="#e0e0e0",
    text="#1a1a1a",
    text_muted="#6b6b6b",
    accent="#7c3aed",
    accent_hover="#6d28d9",
    selection="#d0e4ff",
    editor_bg="#ffffff",
    editor_text="#1a1a1a",
    preview_bg="#ffffff",
    preview_text="#1a1a1a",
    ribbon_bg="#f0f0f0",
    ribbon_fg="#555555",
    ribbon_active="#000000",
    status_bg="#7c3aed",
    status_fg="#ffffff",
    scrollbar="#c0c0c0",
)

THEMES = {"dark": DARK, "light": LIGHT}


def get_theme(name: str) -> Theme:
    return THEMES.get(name, DARK)


def stylesheet(t: Theme) -> str:
    return f"""
* {{ outline: none; }}
QMainWindow, QWidget#RootWidget {{ background: {t.bg}; color: {t.text}; }}
QWidget {{ color: {t.text}; font-family: 'Segoe UI', sans-serif; font-size: 12px; }}
QLabel {{ color: {t.text}; background: transparent; }}

QMenuBar {{ background: {t.surface}; color: {t.text}; padding: 2px; border-bottom: 1px solid {t.border}; }}
QMenuBar::item {{ padding: 4px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {t.surface_alt}; }}
QMenu {{ background: {t.surface}; color: {t.text}; border: 1px solid {t.border}; padding: 4px; }}
QMenu::item {{ padding: 5px 22px 5px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {t.accent}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {t.border}; margin: 4px 8px; }}

QPushButton {{
    background: {t.surface_alt}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 4px;
    padding: 5px 12px; font-size: 12px;
}}
QPushButton:hover {{ background: {t.accent}; color: #ffffff; border-color: {t.accent}; }}
QPushButton:pressed {{ background: {t.accent_hover}; }}

QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {t.surface}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 4px;
    padding: 4px 8px; selection-background-color: {t.accent};
    selection-color: #ffffff;
}}
QLineEdit:focus {{ border-color: {t.accent}; }}

QListWidget, QTreeWidget, QTreeView, QListView {{
    background: {t.surface}; color: {t.text};
    border: none; outline: none; padding: 4px;
}}
QListWidget::item, QTreeWidget::item {{
    padding: 4px 6px; border-radius: 3px;
}}
QListWidget::item:hover, QTreeWidget::item:hover {{ background: {t.surface_alt}; }}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background: {t.selection}; color: #ffffff;
}}

QTabWidget::pane {{ border: none; background: {t.editor_bg}; }}
QTabBar {{ background: {t.surface}; }}
QTabBar::tab {{
    background: {t.surface}; color: {t.text_muted};
    padding: 7px 18px; border: none; margin-right: 1px;
    font-size: 12px;
}}
QTabBar::tab:selected {{ background: {t.editor_bg}; color: {t.text}; }}
QTabBar::tab:hover:!selected {{ background: {t.surface_alt}; }}
QTabBar::close-button {{
    image: none; background: transparent; border-radius: 8px;
    width: 14px; height: 14px;
}}
QTabBar::close-button:hover {{ background: {t.surface_alt}; }}

QSplitter::handle {{ background: {t.border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QSplitter::handle:hover {{ background: {t.accent}; }}

QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t.scrollbar}; border-radius: 5px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {t.text_muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{
    background: {t.scrollbar}; border-radius: 5px; min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}

QToolTip {{
    background: {t.surface_alt}; color: {t.text};
    border: 1px solid {t.border}; padding: 4px 8px;
}}

QDialog {{ background: {t.surface}; }}
QCheckBox {{ color: {t.text}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 3px;
    border: 1px solid {t.border}; background: {t.surface_alt};
}}
QCheckBox::indicator:checked {{
    background: {t.accent}; border-color: {t.accent};
}}

QComboBox {{
    background: {t.surface_alt}; color: {t.text};
    border: 1px solid {t.border}; border-radius: 4px; padding: 4px 8px;
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {t.surface}; color: {t.text};
    border: 1px solid {t.border}; selection-background-color: {t.accent};
}}

QSlider::groove:horizontal {{
    background: {t.surface_alt}; height: 4px; border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {t.accent}; width: 14px; margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{ background: {t.accent_hover}; }}

QStatusBar {{ background: {t.status_bg}; color: {t.status_fg}; }}
QStatusBar::item {{ border: none; }}
"""


# ── Ribbon / panel icon glyphs ─────────────────────────────────────────
class Icon:
    MENU = "☰"
    FILES = "▤"
    SEARCH = "⌕"
    TAGS = "⌗"
    GRAPH = "✦"
    SETTINGS = "⚙"
    NEW = "⊕"
    NEW_FOLDER = "▣"
    CLOSE = "×"
    COLLAPSE_LEFT = "◀"
    COLLAPSE_RIGHT = "▶"
    THEME = "◐"
    OUTLINE = "≡"
    BACKLINKS = "⇄"
    LOCAL_GRAPH = "❋"
    SPLIT_H = "▥"
    SPLIT_V = "▤"
    MODE_SOURCE = "▷"
    MODE_LIVE = "◉"
    MODE_READ = "▣"
    CHEVRON_DOWN = "▾"
    CHEVRON_RIGHT = "▸"
    MORE = "⋯"
    PIN = "⚲"
    STAR = "★"