"""
Chert.py — Entry point. Delegates to UI_Chert.MainWindow.
"""

import sys
from pathlib import Path


def _preflight() -> bool:
    import importlib.util
    if importlib.util.find_spec("PyQt6") is not None:
        return True
    print("", file=sys.stderr)
    print("Chert cannot start: PyQt6 is not installed.", file=sys.stderr)
    print("Install with:", file=sys.stderr)
    print("  python -m pip install PyQt6 PyQt6-WebEngine", file=sys.stderr)
    print("", file=sys.stderr)
    return False


if not _preflight():
    sys.exit(1)

from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

from Chert_Managers import load_app_config, vault_settings_dir
from Theme_Chert import get_theme, stylesheet
from UI_Chert import MainWindow


def _pick_vault() -> Path | None:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QListWidget, QPushButton,
        QHBoxLayout, QDialogButtonBox, QLabel,
    )
    from PyQt6.QtWidgets import QFileDialog

    dlg = QDialog()
    dlg.setWindowTitle("Open Vault")
    dlg.setMinimumWidth(520)
    v = QVBoxLayout(dlg)
    v.addWidget(QLabel("Recent vaults:"))

    lst = QListWidget()
    cfg = load_app_config()
    for r in cfg.get("recent_vaults", []):
        if Path(r).is_dir():
            lst.addItem(r)
    v.addWidget(lst)

    chosen = {"path": None}

    def open_recent(item):
        chosen["path"] = Path(item.text())
        dlg.accept()

    lst.itemDoubleClicked.connect(open_recent)

    row = QHBoxLayout()
    new_b = QPushButton("New Vault…")
    open_b = QPushButton("Open Folder…")
    row.addWidget(new_b)
    row.addWidget(open_b)
    v.addLayout(row)

    def pick_folder():
        p = QFileDialog.getExistingDirectory(dlg, "Choose folder")
        if p:
            chosen["path"] = Path(p)
            dlg.accept()

    new_b.clicked.connect(pick_folder)
    open_b.clicked.connect(pick_folder)

    cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    cancel.rejected.connect(dlg.reject)
    v.addWidget(cancel)

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return chosen["path"]


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Chert")
    app.setApplicationVersion("1.1.0")
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#1e1e1e"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#1e1e1e"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#d4d4d4"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#d4d4d4"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#2d2d30"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#d4d4d4"))
    app.setPalette(pal)

    # Resolve vault
    vault = None
    if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        vault = Path(sys.argv[1])
    else:
        cfg = load_app_config()
        recents = [r for r in cfg.get("recent_vaults", []) if Path(r).is_dir()]
        if recents:
            vault = Path(recents[0])
        else:
            vault = _pick_vault()

    if not vault:
        sys.exit(0)

    win = MainWindow(vault)
    theme = get_theme(win.settings.get("theme", "dark"))
    app.setStyleSheet(stylesheet(theme))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()