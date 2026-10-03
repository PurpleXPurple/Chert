# Obsidian: Complete Architecture, Code Analysis, and Python/PyQt6 Implementation Guide

---

## Overview

Obsidian is a cross-platform knowledge management application built on Electron (desktop) and Capacitor (mobile), structured around a plugin-based architecture with a core engine, a rendering pipeline using CodeMirror 6, and an extensible UI framework. It stores notes as Markdown-formatted plain text files in a local vault folder, giving users full ownership and portability of their data. The application has grown to host over 4,000 community plugins since the API release in 2020, with a deliberate architectural philosophy of minimizing dependencies to reduce supply chain attack risk.

---

## Key Concepts

- **Vault**: A folder on the local file system containing all notes as Markdown files. Obsidian creates a `.obsidian` configuration folder in the vault root for settings, themes, and plugins.
- **CodeMirror 6**: The underlying text editor, providing Live Preview (WYSIWYG-style rendering with syntax fading).
- **MetadataCache**: A cached index of parsed metadata for every file in the vault—links, embeds, tags, headings, frontmatter, and block references.
- **Plugin API**: TypeScript definitions that give plugins access to the vault, workspace, metadata, and UI.
- **Graph View**: A D3.js force-directed visualization running in a Web Worker, rendering to canvas with WebGL acceleration.
- **JSON Canvas**: An open file format (`.canvas`) for infinite canvas data, with nodes and edges stored as JSON.

---

## Architecture Deep Dive

### 1. Electron Application Structure

Obsidian's desktop application runs on Electron with a main process (Node.js, full OS access) and a renderer process (Chromium, UI). The main process manages window creation and native menus; the renderer handles the DOM-based UI. Communication occurs over IPC.

**Key architectural components:**

| Component | Role | Implementation |
|-----------|------|----------------|
| **App** | Global singleton owning all modules | `app.vault`, `app.workspace`, `app.metadataCache` |
| **Vault** | File system operations | Abstracted by `DataAdapter` (FileSystemAdapter on desktop, CapacitorAdapter on mobile) |
| **Workspace** | UI pane and tab management | Handles leaves, splits, and active file tracking |
| **MetadataCache** | Parsed file metadata index | Provides `getFileCache()`, `getBacklinksForFile()` |
| **Editor** | CodeMirror abstraction | Bridges CM5 (legacy) and CM6 |

The mobile app uses Capacitor, sharing most code with desktop except for platform-specific file access and PDF export.

### 2. Editor: CodeMirror 6 Architecture

Obsidian's editor uses CodeMirror 6, a modular editor framework with a high-performance parsing engine. Live Preview mode hides Markdown syntax when the cursor is not on the line, showing rendered content inline.

**CodeMirror 6 extension model:**

- **State fields**: Store state that persists across editor transactions.
- **Decorations**: Control how content is styled; provided directly via state fields or indirectly through view plugins.
- **View plugins**: Manage rendering and interaction with Markdown.

A third-party project (`codemirror-live-markdown`) recreates Obsidian-style Live Preview as a modular plugin collection. The key challenge: Obsidian's AST is not public, so third-party implementations must approximate the decoration logic.

### 3. Plugin System

Obsidian plugins are TypeScript modules extending the `Plugin` base class, which itself extends `Component` for automatic lifecycle management. The plugin lifecycle has `onload()` (initialization) and `onunload()` (cleanup).

**Plugin structure:**

```
my-plugin/
├── manifest.json      # id, name, version, minAppVersion, description
├── main.js            # Compiled entry point
├── styles.css         # Optional styles
└── src/
    └── main.ts        # Source
```

**Manifest properties:**

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | Yes | Unique plugin ID |
| `name` | string | Yes | Display name |
| `version` | string | Yes | Semver format |
| `minAppVersion` | string | Yes | Minimum Obsidian version |
| `description` | string | Yes | Plugin description |
| `author` | string | Yes | Author name |
| `isDesktopOnly` | boolean | No | Platform restriction |

Plugins access the vault through `this.app.vault`, the workspace through `this.app.workspace`, and metadata through `this.app.metadataCache`.

### 4. Metadata Cache and Backlink Index

The `MetadataCache` is critical infrastructure. It parses every file and caches:

- **Links**: Internal `[[wikilinks]]` with position information
- **Embeds**: `![[file]]` references
- **Tags**: Inline `#tag` and frontmatter `tags:`
- **Headings**: For outline and navigation
- **Blocks**: `^block-id` references
- **Frontmatter**: YAML metadata

The naive backlink lookup scans every note on every call. The `obsidian-advanced-metadata-cache` plugin replaces this with a persistent reverse index that updates incrementally via MetadataCache events.

**Backlink index structure:**

```json
{
  "source_note.md": [
    { "target": "Target Note", "header": "Section", "line_number": 42 }
  ]
}
```

Reverse index:

```json
{
  "Target Note": [
    { "source": "source_note.md", "context": "...surrounding text..." }
  ]
}
```

### 5. Graph View: D3 Force Simulation

Obsidian's graph simulation runs in a Web Worker (`sim.js`), which is d3-force with a message handler. Every new node starts at `{ x: 0, y: 0 }`—this causes clusters to overlap initially because a force layout has no move that pulls two tangled components through each other. The `graph-spawn` plugin addresses this by seeding node positions before the simulation starts.

**Forces configuration:**

| Force | Effect |
|-------|--------|
| Center force | How compact the graph is |
| Repel force | How strongly nodes push apart |
| Link force | Tension on each link (rubber band model) |

Rendering uses `<canvas>` with WebGL (Pixi.js). CSS cannot affect nodes directly; Obsidian provides CSS variable bridges for colors.

### 6. Data Storage

**Vault structure:**

```
vault/
├── .obsidian/
│   ├── app.json              # Global app settings
│   ├── appearance.json       # Theme settings
│   ├── community-plugins.json # Enabled community plugins
│   ├── core-plugins.json     # Enabled core plugins
│   ├── workspace.json        # Current workspace layout
│   ├── workspaces.json       # Saved workspaces
│   ├── plugins/
│   │   └── my-plugin/
│   │       ├── manifest.json
│   │       ├── main.js
│   │       └── data.json     # Plugin settings
│   └── themes/
├── Note 1.md
├── Note 2.md
└── Folder/
    └── Note 3.md
```

Notes are plain Markdown. Obsidian syncs via Obsidian Sync (proprietary), or community plugins for Git, Syncthing, Dropbox, iCloud, etc..

### 7. Sync Implementation

Obsidian Sync uses file-level debounced syncing, not full CRDT history, to maintain O(1) memory per file. Community CRDT implementations use Yjs:

- **obsidian-crdt-sync**: Yjs CRDT, self-hosted server, SQLite storage
- **IlowObsidianSync**: Loro CRDT for offline-first sync
- **lan-vault-sync**: Yjs CRDT over P2P WebSocket for LAN

---

## Python/PyQt6 Implementation Guide

### Architecture Overview

A PyQt6 implementation of Obsidian-like functionality requires these components:

| Obsidian Component | PyQt6 Equivalent | Notes |
|-------------------|------------------|-------|
| Electron shell | `QApplication` + `QMainWindow` | Native desktop window |
| CodeMirror 6 editor | `QPlainTextEdit` + `QSyntaxHighlighter` | Custom Markdown highlighter |
| Live Preview | `QTextDocument` + custom rendering | Complex; consider two-pane or QWebEngine |
| Vault file system | `pathlib` + `QFileSystemWatcher` | Watch for changes |
| Metadata cache | SQLite + `watchdog` | Persistent index |
| Graph view | `QGraphicsScene` + custom force layout | Or embed D3 in QWebEngine |
| Plugin system | Python entry points or `QPluginLoader` | Module-based loading |
| Search | SQLite FTS5 | Full-text search |
| Backlinks | SQLite + reverse index | Indexed wikilinks |
| Tabs | `QTabWidget` | Multi-document interface |
| Split panes | `QSplitter` | Resizable layouts |
| Dock panels | `QDockWidget` | Sidebars (file tree, backlinks, tags) |

### Core Implementation: Vault and File Management

```python
import sys
from pathlib import Path
from PyQt6.QtCore import QFileSystemWatcher, pyqtSignal, QObject
from PyQt6.QtWidgets import QApplication, QMainWindow, QTreeView, QSplitter, QTabWidget
from PyQt6.QtWidgets import QPlainTextEdit, QDockWidget, QListWidget
from PyQt6.QtGui import QFileSystemModel, QSyntaxHighlighter, QTextCharFormat, QColor

class VaultManager(QObject):
    """Manages vault directory, file watching, and metadata indexing."""
    
    file_changed = pyqtSignal(str)
    file_created = pyqtSignal(str)
    file_deleted = pyqtSignal(str)
    
    def __init__(self, vault_path: Path):
        super().__init__()
        self.vault_path = vault_path
        self.watcher = QFileSystemWatcher()
        self.watcher.addPath(str(vault_path))
        self.watcher.directoryChanged.connect(self._on_directory_changed)
        
        # Index markdown files
        self.md_files = {}
        self._scan_vault()
    
    def _scan_vault(self):
        for md_file in self.vault_path.rglob("*.md"):
            if '.obsidian' in md_file.parts:
                continue
            rel_path = md_file.relative_to(self.vault_path)
            self.md_files[str(rel_path)] = md_file
    
    def _on_directory_changed(self, path: str):
        # Rescan on directory change (simplified)
        self._scan_vault()
        self.file_changed.emit(path)
    
    def read_note(self, rel_path: str) -> str:
        file_path = self.vault_path / rel_path
        return file_path.read_text(encoding='utf-8')
    
    def write_note(self, rel_path: str, content: str):
        file_path = self.vault_path / rel_path
        file_path.write_text(content, encoding='utf-8')
        self.file_changed.emit(rel_path)
```

### Markdown Syntax Highlighter

```python
class MarkdownHighlighter(QSyntaxHighlighter):
    """Real-time Markdown syntax highlighting for QPlainTextEdit."""
    
    def __init__(self, document):
        super().__init__(document)
        self._formats = {}
        self._init_formats()
        self._rules = []
        self._build_rules()
    
    def _init_formats(self):
        # Headers
        for level in range(1, 7):
            fmt = QTextCharFormat()
            fmt.setFontWeight(700 + (7 - level) * 100)
            fmt.setForeground(QColor("#1a1a1a"))
            fmt.setFontPointSize(24 - level * 2)
            self._formats[f'h{level}'] = fmt
        
        # Bold
        bold = QTextCharFormat()
        bold.setFontWeight(700)
        self._formats['bold'] = bold
        
        # Italic
        italic = QTextCharFormat()
        italic.setFontItalic(True)
        self._formats['italic'] = italic
        
        # Code
        code = QTextCharFormat()
        code.setFontFamily("JetBrains Mono")
        code.setBackground(QColor("#f0f0f0"))
        code.setForeground(QColor("#e83e8c"))
        self._formats['code'] = code
        
        # Links
        link = QTextCharFormat()
        link.setForeground(QColor("#0969da"))
        link.setFontUnderline(True)
        self._formats['link'] = link
        
        # Wikilinks
        wikilink = QTextCharFormat()
        wikilink.setForeground(QColor("#6f42c1"))
        wikilink.setFontUnderline(True)
        self._formats['wikilink'] = wikilink
        
        # Tags
        tag = QTextCharFormat()
        tag.setForeground(QColor("#2da44e"))
        self._formats['tag'] = tag
    
    def _build_rules(self):
        import re
        self._rules = [
            (re.compile(r'^#{1,6}\s.*$'), self._formats['h1']),
            (re.compile(r'\*\*(.+?)\*\*'), self._formats['bold']),
            (re.compile(r'\*(.+?)\*'), self._formats['italic']),
            (re.compile(r'`[^`]+`'), self._formats['code']),
            (re.compile(r'\[\[([^\]]+)\]\]'), self._formats['wikilink']),
            (re.compile(r'\[([^\]]+)\]\([^)]+\)'), self._formats['link']),
            (re.compile(r'#[a-zA-Z0-9_/-]+'), self._formats['tag']),
        ]
    
    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)
```

### Backlink Index with SQLite

```python
import sqlite3
import re
from pathlib import Path

class BacklinkIndex:
    """SQLite-backed index for wikilinks and backlinks."""
    
    WIKILINK_PATTERN = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')
    
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                target_file TEXT NOT NULL,
                context TEXT,
                UNIQUE(source_file, target_file)
            )
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_links_target 
            ON links(target_file)
        """)
        self.conn.commit()
    
    def index_file(self, source_path: str, content: str):
        """Re-index a single file's outgoing links."""
        self.conn.execute("DELETE FROM links WHERE source_file = ?", (source_path,))
        
        for match in self.WIKILINK_PATTERN.finditer(content):
            target = match.group(1).strip()
            # Get surrounding context
            start = max(0, match.start() - 60)
            end = min(len(content), match.end() + 60)
            context = content[start:end].replace('\n', ' ')
            
            self.conn.execute(
                "INSERT OR IGNORE INTO links (source_file, target_file, context) VALUES (?, ?, ?)",
                (source_path, target, context)
            )
        
        self.conn.commit()
    
    def get_backlinks(self, target_path: str) -> list[dict]:
        """Get all notes linking to a target."""
        cursor = self.conn.execute(
            "SELECT source_file, context FROM links WHERE target_file = ? OR target_file = ?",
            (target_path, Path(target_path).stem)
        )
        return [{"source": row[0], "context": row[1]} for row in cursor.fetchall()]
    
    def get_outgoing_links(self, source_path: str) -> list[str]:
        """Get all links from a source note."""
        cursor = self.conn.execute(
            "SELECT target_file FROM links WHERE source_file = ?",
            (source_path,)
        )
        return [row[0] for row in cursor.fetchall()]
```

### Full-Text Search with SQLite FTS5

```python
class SearchIndex:
    """SQLite FTS5 full-text search for notes."""
    
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts 
            USING fts5(path, title, content, tokenize='porter')
        """)
        self.conn.commit()
    
    def index_note(self, path: str, title: str, content: str):
        self.conn.execute("DELETE FROM notes_fts WHERE path = ?", (path,))
        self.conn.execute(
            "INSERT INTO notes_fts (path, title, content) VALUES (?, ?, ?)",
            (path, title, content)
        )
        self.conn.commit()
    
    def search(self, query: str, limit: int = 50) -> list[dict]:
        cursor = self.conn.execute(
            """
            SELECT path, title, 
                   snippet(notes_fts, 2, '<mark>', '</mark>', '...', 32) as snippet,
                   bm25(notes_fts) as rank
            FROM notes_fts 
            WHERE notes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit)
        )
        return [
            {"path": row[0], "title": row[1], "snippet": row[2], "rank": row[3]}
            for row in cursor.fetchall()
        ]
```

### Graph View with QGraphicsScene

For a force-directed graph, implement a simple force simulation with Qt's `QTimer`:

```python
import math
from PyQt6.QtCore import QTimer, QPointF, Qt
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsItem
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

class GraphNode(QGraphicsItem):
    def __init__(self, node_id: str, label: str):
        super().__init__()
        self.node_id = node_id
        self.label = label
        self.velocity = QPointF(0, 0)
        self.setPos(0, 0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(1)
    
    def boundingRect(self):
        return QRectF(-15, -15, 30, 30)
    
    def paint(self, painter, option, widget):
        painter.setBrush(QBrush(QColor("#6f42c1")))
        painter.setPen(QPen(QColor("#4a2d8a"), 2))
        painter.drawEllipse(-12, -12, 24, 24)
        
        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Inter", 8))
        painter.drawText(QRectF(-12, -12, 24, 24), 
                        Qt.AlignmentFlag.AlignCenter, 
                        self.label[:2].upper())


class ForceGraphView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self.nodes = {}
        self.edges = []
        self.repulsion = 5000
        self.spring_length = 120
        self.damping = 0.85
        
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)  # ~60 FPS
    
    def add_node(self, node_id: str, label: str):
        node = GraphNode(node_id, label)
        self.nodes[node_id] = node
        self.scene.addItem(node)
    
    def add_edge(self, source_id: str, target_id: str):
        self.edges.append((source_id, target_id))
    
    def _tick(self):
        if not self.nodes:
            return
        
        # Repulsion between all nodes
        node_list = list(self.nodes.values())
        for i, a in enumerate(node_list):
            fx, fy = 0.0, 0.0
            for j, b in enumerate(node_list):
                if i == j:
                    continue
                dx = a.x() - b.x()
                dy = a.y() - b.y()
                dist = max(math.sqrt(dx*dx + dy*dy), 1.0)
                force = self.repulsion / (dist * dist)
                fx += (dx / dist) * force
                fy += (dy / dist) * force
            
            # Spring forces for edges
            for source_id, target_id in self.edges:
                if source_id == a.node_id:
                    other = self.nodes.get(target_id)
                elif target_id == a.node_id:
                    other = self.nodes.get(source_id)
                else:
                    continue
                if other:
                    dx = other.x() - a.x()
                    dy = other.y() - a.y()
                    dist = max(math.sqrt(dx*dx + dy*dy), 1.0)
                    force = (dist - self.spring_length) * 0.05
                    fx += (dx / dist) * force
                    fy += (dy / dist) * force
            
            # Apply velocity
            a.velocity.setX((a.velocity.x() + fx) * self.damping)
            a.velocity.setY((a.velocity.y() + fy) * self.damping)
            a.setPos(a.x() + a.velocity.x(), a.y() + a.velocity.y())
```

For large graphs (>1000 nodes), consider:
- Setting `QGraphicsScene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)` for moving items
- Using `QGraphicsView.DontAdjustForAntialiasing` optimization flag
- Pre-computing layout with `networkx` + `pyforceatlas2` (Barnes-Hut optimization)

### Main Window with Split Panes and Docks

```python
class ObsidianLikeWindow(QMainWindow):
    def __init__(self, vault_path: Path):
        super().__init__()
        self.vault = VaultManager(vault_path)
        self.backlinks = BacklinkIndex(vault_path / ".obsidian" / "backlinks.db")
        self.search = SearchIndex(vault_path / ".obsidian" / "search.db")
        
        self.setWindowTitle("Obsidian-Py")
        self.resize(1400, 900)
        
        # Central: tabbed editors
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.setCentralWidget(self.tabs)
        
        # Left dock: file tree
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(str(vault_path))
        self.file_model.setNameFilters(["*.md"])
        self.file_model.setNameFilterDisables(False)
        
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIndex(self.file_model.index(str(vault_path)))
        self.file_tree.setHeaderHidden(True)
        self.file_tree.doubleClicked.connect(self._open_file)
        
        left_dock = QDockWidget("Files", self)
        left_dock.setWidget(self.file_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, left_dock)
        
        # Right dock: backlinks
        self.backlinks_list = QListWidget()
        self.backlinks_list.itemDoubleClicked.connect(self._open_backlink)
        
        right_dock = QDockWidget("Backlinks", self)
        right_dock.setWidget(self.backlinks_list)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, right_dock)
        
        # Right dock 2: tags
        self.tags_list = QListWidget()
        tags_dock = QDockWidget("Tags", self)
        tags_dock.setWidget(self.tags_list)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, tags_dock)
    
    def _open_file(self, index):
        rel_path = self.file_model.filePath(index)
        if not rel_path.endswith('.md'):
            return
        
        # Check if already open
        for i in range(self.tabs.count()):
            if self.tabs.tabToolTip(i) == rel_path:
                self.tabs.setCurrentIndex(i)
                return
        
        content = self.vault.read_note(rel_path)
        
        editor = QPlainTextEdit()
        editor.setPlainText(content)
        editor.setFont(QFont("JetBrains Mono", 12))
        
        highlighter = MarkdownHighlighter(editor.document())
        editor.textChanged.connect(lambda: self._on_edit(rel_path, editor))
        
        # Index on open
        self.backlinks.index_file(rel_path, content)
        self.search.index_note(rel_path, Path(rel_path).stem, content)
        
        tab_index = self.tabs.addTab(editor, Path(rel_path).name)
        self.tabs.setTabToolTip(tab_index, rel_path)
        self.tabs.setCurrentIndex(tab_index)
        
        self._update_backlinks(rel_path)
    
    def _update_backlinks(self, rel_path: str):
        self.backlinks_list.clear()
        for bl in self.backlinks.get_backlinks(rel_path):
            self.backlinks_list.addItem(bl["source"])
    
    def _on_edit(self, rel_path: str, editor: QPlainTextEdit):
        content = editor.toPlainText()
        self.vault.write_note(rel_path, content)
        self.backlinks.index_file(rel_path, content)
        self.search.index_note(rel_path, Path(rel_path).stem, content)
    
    def _close_tab(self, index: int):
        self.tabs.removeTab(index)
    
    def _open_backlink(self, item):
        source = item.text()
        # Find and open the source file
        pass
```

### Markdown Preview with QWebEngine

For richer rendering (Mermaid, KaTeX, syntax-highlighted code), use `QWebEngineView`:

```python
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
import markdown

class MarkdownPreview(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._md = markdown.Markdown(extensions=[
            'extra', 'codehilite', 'toc', 'sane_lists', 'smarty',
            'fenced_code', 'tables', 'footnotes'
        ])
        self.setHtml(self._template())
    
    def _template(self):
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    line-height: 1.7;
                    max-width: 720px;
                    margin: 0 auto;
                    padding: 40px 20px;
                    color: #1a1a1a;
                }
                h1, h2, h3 { font-weight: 600; margin-top: 1.5em; }
                h1 { font-size: 1.8em; }
                h2 { font-size: 1.4em; }
                code {
                    font-family: 'JetBrains Mono', monospace;
                    background: #f6f8fa;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 0.9em;
                }
                pre {
                    background: #f6f8fa;
                    padding: 16px;
                    border-radius: 8px;
                    overflow-x: auto;
                }
                pre code { background: none; padding: 0; }
                blockquote {
                    border-left: 4px solid #6f42c1;
                    margin: 1em 0;
                    padding-left: 16px;
                    color: #555;
                }
                a { color: #0969da; }
                a.wikilink { color: #6f42c1; }
                .tag { color: #2da44e; font-weight: 500; }
            </style>
        </head>
        <body>%s</body>
        </html>
        """
    
    def set_markdown(self, text: str):
        html = self._md.convert(text)
        # Post-process wikilinks
        html = re.sub(
            r'\[\[([^\]]+)\]\]',
            r'<a href="#" class="wikilink" data-link="\1">\1</a>',
            html
        )
        # Post-process tags
        html = re.sub(
            r'(?<!\w)#([a-zA-Z0-9_/-]+)',
            r'<span class="tag">#\1</span>',
            html
        )
        self.setHtml(self._template() % html)
```

### Plugin System with Python Entry Points

For a Python-based plugin architecture, use `importlib` and a manifest convention:

```python
import importlib.util
import json
from pathlib import Path

class PluginLoader:
    def __init__(self, plugin_dir: Path, app_context):
        self.plugin_dir = plugin_dir
        self.app_context = app_context
        self.plugins = {}
    
    def discover(self):
        for manifest_path in self.plugin_dir.glob("*/manifest.json"):
            with open(manifest_path) as f:
                manifest = json.load(f)
            
            plugin_path = manifest_path.parent / manifest.get("main", "main.py")
            if not plugin_path.exists():
                continue
            
            spec = importlib.util.spec_from_file_location(
                manifest["id"], plugin_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            if hasattr(module, "Plugin"):
                self.plugins[manifest["id"]] = {
                    "manifest": manifest,
                    "instance": module.Plugin(self.app_context)
                }
    
    def load_all(self):
        for plugin_id, plugin in self.plugins.items():
            if hasattr(plugin["instance"], "onload"):
                plugin["instance"].onload()
    
    def unload_all(self):
        for plugin_id, plugin in self.plugins.items():
            if hasattr(plugin["instance"], "onunload"):
                plugin["instance"].onunload()
```

### Sync with CRDT (pycrdt)

For collaborative editing, use `pycrdt` (Python bindings for Yjs via Yrs):

```python
from pycrdt import Doc, Text, Map

class CollaborativeVault:
    def __init__(self):
        self.docs = {}  # file_path -> Y.Doc
    
    def get_doc(self, file_path: str) -> Doc:
        if file_path not in self.docs:
            doc = Doc()
            doc["content"] = Text()
            self.docs[file_path] = doc
        return self.docs[file_path]
    
    def apply_update(self, file_path: str, update: bytes):
        doc = self.get_doc(file_path)
        doc.apply_update(update)
    
    def get_update(self, file_path: str) -> bytes:
        doc = self.get_doc(file_path)
        return doc.get_update()
```

A WebSocket server using `websockets` or `FastAPI` can relay updates between clients.

---

## Technical Specifications

### Dependency Comparison

| Concern | Obsidian | Python/PyQt6 Equivalent |
|---------|----------|------------------------|
| Desktop shell | Electron 37.3.0 (MIT) | PyQt6 6.7+ (GPL/commercial) |
| Editor | CodeMirror 6 (MIT) | QPlainTextEdit + custom highlighter |
| Markdown parsing | markdown-it (MIT) | mistletoe or Python-Markdown |
| Graph rendering | D3-force + Pixi.js (MIT) | QGraphicsScene or QWebEngine + D3 |
| Full-text search | Custom index | SQLite FTS5 |
| File watching | Node.js fs.watch | QFileSystemWatcher + watchdog |
| Sync | Proprietary + CRDT plugins | pycrdt (Yjs) + WebSocket |
| Plugin system | TypeScript `require('obsidian')` | Python importlib + entry points |
| Mobile | Capacitor | N/A (PyQt6 is desktop) |

### Performance Considerations

| Operation | Obsidian | PyQt6 Approach |
|-----------|----------|----------------|
| File scan (10k notes) | < 1s | ~2-3s with `rglob` |
| Backlink lookup | O(1) with index | O(1) with SQLite index |
| Full-text search | < 50ms (indexed) | < 100ms (FTS5) |
| Graph render (1k nodes) | 60 FPS (WebGL) | 30-60 FPS (QGraphicsScene) |
| Live preview | Real-time (CM6) | Debounced 150ms (QTextDocument) |

---

## Examples

### Example 1: Opening a Vault

```python
app = QApplication(sys.argv)
vault_path = Path.home() / "Documents" / "MyVault"
window = ObsidianLikeWindow(vault_path)
window.show()
sys.exit(app.exec())
```

### Example 2: Indexing and Searching

```python
# Index all notes
for md_file in vault_path.rglob("*.md"):
    content = md_file.read_text(encoding='utf-8')
    rel_path = str(md_file.relative_to(vault_path))
    backlinks.index_file(rel_path, content)
    search.index_note(rel_path, md_file.stem, content)

# Search
results = search.search("knowledge management")
for r in results:
    print(f"{r['title']} — {r['snippet']}")
```

### Example 3: Extracting Wikilinks

```python
import re

WIKILINK_PATTERN = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')

text = "See [[Note 1]] and [[Note 2|alias]] for details."
for match in WIKILINK_PATTERN.finditer(text):
    target = match.group(1)
    alias = match.group(2) or target
    print(f"Target: {target}, Display: {alias}")
# Output:
# Target: Note 1, Display: Note 1
# Target: Note 2, Display: alias
```

### Example 4: Force Graph Layout

```python
# Add nodes
graph_view.add_node("note1", "Note 1")
graph_view.add_node("note2", "Note 2")
graph_view.add_node("note3", "Note 3")

# Add edges
graph_view.add_edge("note1", "note2")
graph_view.add_edge("note2", "note3")
graph_view.add_edge("note3", "note1")

# Nodes will settle into a triangular layout
```

### Example 5: Plugin Manifest

```json
{
  "id": "word-count",
  "name": "Word Count",
  "version": "1.0.0",
  "minAppVersion": "0.1.0",
  "description": "Displays word count in the status bar",
  "author": "Your Name",
  "main": "main.py"
}
```

```python
# word-count/main.py
class Plugin:
    def __init__(self, app):
        self.app = app
    
    def onload(self):
        self.app.register_status_bar_item("word-count", self.update_count)
    
    def update_count(self):
        editor = self.app.get_active_editor()
        if editor:
            text = editor.toPlainText()
            words = len(text.split())
            return f"{words} words"
        return "No file open"
    
    def onunload(self):
        pass
```

---

## Connections

- **Obsidian Plugin API** → CodeMirror 6 extension API → State fields, decorations, view plugins
- **MetadataCache** → Backlink index → Graph view → D3 force simulation
- **Vault** → File system watcher → MetadataCache → Search index
- **JSON Canvas** → `.canvas` files → Infinite canvas UI → Node/edge model
- **CRDT (Yjs)** → Real-time collaboration → Conflict-free merging → Offline-first sync

---

## Open Questions

1. **Live Preview fidelity**: Can a PyQt6 implementation achieve true WYSIWYG Live Preview (syntax fading on cursor entry) with `QTextDocument`, or is `QWebEngine` with CodeMirror necessary?
2. **Graph performance**: At what node count does `QGraphicsScene` force simulation become unusable, and is OpenGL integration (via `QOpenGLWidget`) sufficient to close the gap with WebGL?
3. **Plugin isolation**: How to safely sandbox Python plugins? Obsidian's Electron model shares memory space; Python's import system does not provide isolation by default.
4. **Mobile parity**: PyQt6 does not target iOS/Android. Is a web-based frontend (e.g., Pyodide + CodeMirror) the only path to mobile?
5. **Sync conflict resolution**: How does Obsidian's file-level debounced sync handle simultaneous edits on the same file? The CRDT approach (Yjs) solves this but requires per-file CRDT documents.
6. **Search relevance**: Obsidian's search uses a custom index; SQLite FTS5 with BM25 is a viable replacement, but recency and frecency weighting (as in `lean-search`) may be needed for comparable UX.
7. **Markdown dialect**: Obsidian Flavored Markdown (OFM) adds wikilinks, embeds, block references, and callouts on top of CommonMark. Which Python parser (mistletoe, markdown-it-py, mistune) best supports custom extensions for these features?

---

## Summary

Obsidian's architecture is a masterclass in pragmatic engineering: Electron for cross-platform reach, CodeMirror 6 for a best-in-class editor, D3-force for graph visualization, and a TypeScript plugin API that has spawned 4,000+ extensions. Its deliberate avoidance of dependencies (Electron, CodeMirror, and moment.js are the only shipped libraries) reflects a security-first philosophy that prioritizes supply chain integrity over rapid feature velocity.

A Python/PyQt6 implementation is feasible for the core feature set—vault management, Markdown editing with syntax highlighting, backlink indexing, full-text search, and force-directed graph visualization. The primary gaps are Live Preview (requires significant custom rendering), mobile support (PyQt6 is desktop-only), and plugin isolation (Python lacks Electron's process model). For projects that need Live Preview fidelity and mobile reach, a hybrid approach—PyQt6 shell with QWebEngine hosting CodeMirror 6—is the most pragmatic path.

The smallest correct move for most Python developers: build the vault layer (`pathlib` + `QFileSystemWatcher`), the backlink index (SQLite + regex wikilink parsing), and the editor (`QPlainTextEdit` + `QSyntaxHighlighter`). These three components deliver 70% of Obsidian's daily value with 20% of the complexity. Add the graph view and search index once the core is stable.