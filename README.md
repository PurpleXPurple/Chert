# Chert

> **Archived.** Chert is no longer under active development. The code, the
> research, the stress tests, and the design notes are all staying here. I
> might come back to it. I might not. Nothing is being deleted.

A local-first Markdown knowledge base for Windows, built on PyQt6.
Vault folders, wikilinks, backlinks, tags, full-text search, and a
force-directed graph — the Obsidian feature set, in Python.

---

## What it actually is

You point Chert at a folder. That folder is now a vault. Every `.md`
file in it is a note. Notes link to each other with `[[wikilinks]]`.
Everything is indexed into SQLite so backlinks, tags, and search are
O(1) instead of "scan every file on every keystroke."

The editor is a two-pane split: source on the left, live preview on the
right. The preview runs in QWebEngine so you get KaTeX math and Mermaid
diagrams rendered for real, not approximated.

The graph view is a hand-rolled Barnes-Hut quadtree. It handles 300+
nodes at interactive framerates. It has PageRank, community detection,
shortest path, orphan detection, bidirectional-edge detection, tag
co-occurrence, and about 18 other graph construction methods in
`GraphBuilder`.

The rest is Obsidian-shaped: a ribbon on the far left, a collapsible
files/search/tags sidebar, a backlinks/outline/local-graph sidebar,
tabs, a command palette on Ctrl+P, a quick switcher on Ctrl+O, dark
and light themes.

It works. I stopped working on it. Both of those are true.

---

## Status

- **Last active version:** 1.1.0
- **State:** archived, dormant, not abandoned
- **Support:** none, while archived
- **Security patches:** none, while archived
- **Fork-friendly:** yes, if you want to take it somewhere, go
- **Re-entry:** possible. The research doc (`Research.md`) is the
  re-entry point. It walks through Obsidian's architecture and maps
  every component to its PyQt6 equivalent. If I pick this up again,
  that file is where I start.

---

## Features

**Vault**
- Any folder is a vault. `python Chert.py /path/to/vault`.
- Recursive scan for `.md` files, dotfolders pruned.
- `QFileSystemWatcher` per directory, with polling fallback when the
  watcher is full (macOS/Linux limits).
- Long-path handling on Windows (`\\?\` prefix added automatically).

**Indexes (SQLite)**
- `backlinks.db` — every `[[wikilink]]` with alias and surrounding
  context. Two indexes: by source, by target.
- `search.db` — FTS5 virtual table with `unicode61` tokenizer. Falls
  back to `LIKE` if FTS5 isn't compiled into the Python's SQLite.
- `tags.db` — inline `#tags` and frontmatter `tags:` both indexed.
  Code fences and inline code are stripped before scanning so `#foo`
  inside a code block doesn't count.
- `schema_version` table per DB, so migrations are non-destructive.

**Editor**
- `QPlainTextEdit` + custom `QSyntaxHighlighter`.
- List continuation on Enter (ordered, unordered, task lists).
- Tab-stop distance set from font metrics, not a hardcoded pixel value.

**Live preview**
- QWebEngine when available, `QTextEdit` fallback when not.
- KaTeX (0.16.9) for math, `$$...$$` and `$...$` and `\[...\]` and
  `\(...\)`.
- Mermaid (10.9.0) for diagrams, `securityLevel:'strict'`.
- Custom `chert://open/<target>` scheme for wikilink clicks.
- `acceptNavigationRequest` interception on a `QWebEnginePage`
  subclass. Monkey-patching a C++ virtual does not work; the
  subclass is the only correct path.
- Hash-based re-render skip. Rapid edits don't re-render if the text
  hash and the known-notes set haven't changed.
- Debounce scales with document size: 70ms floor, 220ms ceiling.
- Known-notes cache with a 1.5s TTL so wikilink resolution doesn't
  hit the vault on every keystroke.

**Graph**
- Barnes-Hut quadtree, `theta = 0.9`, kicks in at 50 nodes.
- `QGraphicsScene.ItemIndexMethod.NoIndex` (moving items, no BSP).
- LOD-aware node labels.
- Image and GIF nodes via drag-and-drop.
- 24 graph construction methods including PageRank, label-propagation
  communities, BFS shortest path, orphans, bidirectional edges,
  tag co-occurrence, and unresolved-wikilink stubs.

**Shell**
- Ribbon, two collapsible sidebars, tabs, status bar with word count
  and cursor position.
- Command palette, quick switcher, settings dialog.
- Dark and light themes, single QSS string applied to the
  `QApplication`.

---

## Requirements

Windows. PyQt6. Python 3.8+.

```
PyQt6>=6.5,<7
PyQt6-WebEngine>=6.5,<7
```

Install:

```powershell
python -m pip install PyQt6 PyQt6-WebEngine
```

The `requirements.txt` mentions a PyQt5 fallback. Ignore it. The
codebase is PyQt6-only — the docstring in `Chert_Managers.py` says so
out loud. The PyQt5 lines are a leftover from a plan I didn't finish.

---

## Running

```powershell
python Chert.py
```

With a vault path:

```powershell
python Chert.py C:\Users\you\Documents\MyVault
```

Without a path, Chert shows a vault picker with recent vaults and a
folder browser.

---

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+N` | New note |
| `Ctrl+O` | Quick switcher |
| `Ctrl+P` | Command palette |
| `Ctrl+S` | Save |
| `Ctrl+W` | Close tab |
| `Ctrl+Shift+F` | Search in vault |
| `Ctrl+G` | Graph view |
| `Ctrl+\` | Toggle left sidebar |
| `Ctrl+Shift+\` | Toggle right sidebar |

---

## Testing

```powershell
python _stress.py
```

15 tests, headless (`QT_QPA_PLATFORM=offscreen`), exit code 0 or 1.

What it covers:

- All modules import.
- Markdown renderer survives 20 edge cases: unclosed wikilinks,
  5000-char headings, 3000-line joins, emoji, RTL text, empty input.
- 500 markdown sections render in under 3 seconds.
- Live preview loads, unicode survives, empty input survives.
- Preview HTML actually reaches the view (`toHtml()` round-trip on
  WebEngine, synchronous on the `QTextEdit` fallback).
- Hidden edits trigger re-render.
- 100 rapid edits don't blow past the hash-skip.
- 3-node triangle, 60-node chain, 300-node stress all within budget.
- Full vault pipeline: write, scan, backlink, search, tag.
- Both themes produce > 500-char stylesheets.
- MainWindow constructs offscreen.
- Panels construct offscreen.

If `_stress.py` passes, the code is intact. If it fails, that's the
first thing to fix on re-entry.

---

## Layout

```
Chert/
├── Chert.py                entry point, vault picker, app setup
├── Chert_Managers.py       Qt re-exports, error routers, vault, indexes
├── Markdown_Chert.py       renderer, ctypes FastBuffer, syntax highlighter
├── Live_Preview.py         editor + preview + split pane
├── Graph_Chert.py          force graph, Barnes-Hut, GraphBuilder
├── Panels_Chert.py         file tree, search, tags, backlinks, outline, local graph
├── Dialogs_Chert.py        command palette, quick switcher, settings, about
├── Theme_Chert.py          dark/light themes, QSS
├── UI_Chert.py             ribbon, sidebars, editor area, main window
├── _stress.py              headless test suite
├── requirements.txt
├── Research.md             Obsidian architecture + PyQt6 mapping
├── Audit.md
└── Vault/
    └── Audit.md
```

---

## Design notes (the stuff worth remembering)

**Everything is wrapped.** `Chert_Managers.py` exposes a
`ManagerErrorRouter` with ten sub-handlers — io, path, watcher, scan,
sqlite, search, config, signal, resource, migration. Every filesystem
and database call goes through a `safe_*` method. The handlers keep a
64-record ring buffer, count per context, and have `mute`/`unmute`.
This is defensive architecture from someone who got burned by a
silent failure and decided never again.

**The renderer uses null-byte placeholders.** Fenced code blocks are
stashed as `\x00CODE{n}\x00` before escaping, then re-substituted
after. Inline code uses `\x01{n}\x01`. This is the trick that lets
the whole markdown body be `html.escape`'d in one pass while still
letting code blocks survive untouched.

**FastBuffer runs on `memmove`.** `Markdown_Chert.py` loads `libc`
or `msvcrt` via ctypes and does the string concatenation through
`memmove` instead of Python string `+=`. Thread-local `BufferPool`
so it's safe. This is a real optimization, not a toy one.

**The known-notes cache is time-boxed.** `LivePreviewPane` caches
the vault's note list for 1.5 seconds. Wikilink resolution otherwise
costs a directory walk on every keystroke.

**`_cheap_hash`.** For documents over 512 chars, hashes only the
first 128, the middle 128, and the last 128 bytes plus the length.
Skips re-rendering on unchanged text without paying for a full hash.

**No BSP tree on the graph scene.** The comment in `Graph_Chert.py`
is a war wound. `QGraphicsScene.ItemIndexMethod.NoIndex` is correct
for moving items. `setBspTreeDepth` is only valid with the default
`BspTreeIndex`, and calling it after `NoIndex` throws a Qt warning.
Someone learned that the hard way.

---

## Why it's archived

Personal call. Not a failure. Not a dead end. I hit the point where
the next feature would have required rebuilding more than I wanted
to rebuild in one sitting, and I'd rather leave it in a state that
works than push it into a state that half-works.

Everything stays. Nothing is being deleted or hidden. If I come back,
I start with `Research.md` and `_stress.py`.

---

## License

See `LICENSE`. Short version: if this ever ships as a binary, it's
GPLv3, because PyQt6 is GPLv3-or-commercial and I don't have a
commercial license. If you want to fork and ship it yourself, either
comply with GPLv3 or buy a PyQt6 commercial license. Details in the
license file.

---

*Started as a first project. Still is. Archived [DATE].*
```

### `BUILD.md`

```markdown
# Building Chert from scratch

A re-entry guide. If you're reading this in six months and want to
know what to do first, start here.

---

## 0. Assumptions

- Windows (the code is Windows-first — long path prefixes, APPDATA
  for config, a Windows-only note in `requirements.txt`).
- Python 3.8 or newer.
- 64-bit Python. The `requirements.txt` says 32-bit works with
  PyQt5. It doesn't. That comment is a lie I told myself.
- You have a vault folder somewhere. Any folder full of `.md` files.
  Or an empty folder — Chert will take it.

---

## 1. Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## 2. Dependencies

```powershell
python -m pip install "PyQt6>=6.5,<7" "PyQt6-WebEngine>=6.5,<7"
```

`PyQt6-WebEngine` is optional in theory — the code falls back to
`QTextEdit` if it's missing — but the preview is half the point, so
install it.

## 3. Verify the environment

```powershell
python -c "import PyQt6; from PyQt6.QtWebEngineWidgets import QWebEngineView; print('ok')"
```

If that prints `ok`, you're set. If it throws, the WebEngine wheel
probably didn't match your Python version. Check that.

## 4. Get the source

All ten files. The order they exist in doesn't matter for imports —
Python resolves them at runtime — but here's the layering if you're
reading:

```
Layer 0   Chert_Managers.py     (imports Qt, defines everything else needs)
Layer 1   Markdown_Chert.py     (depends on Managers for Qt + regexes)
Layer 1   Theme_Chert.py        (depends only on QtGui)
Layer 2   Live_Preview.py       (depends on Managers + Markdown)
Layer 2   Graph_Chert.py        (depends on Managers)
Layer 3   Panels_Chert.py       (depends on Managers + Markdown + Graph)
Layer 3   Dialogs_Chert.py      (depends on Qt only)
Layer 4   UI_Chert.py           (depends on everything above)
Layer 5   Chert.py              (entry point, imports UI_Chert)
Layer -1  _stress.py            (imports everything, tests everything)
```

If a build breaks, go bottom-up. Fix `Chert_Managers.py` first.

## 5. Run

```powershell
python Chert.py
```

Or with a vault:

```powershell
python Chert.py C:\path\to\vault
```

## 6. Verify

```powershell
python _stress.py
```

You should see something like:

```
==============================================================
  PASS  imports_all                        ~200ms
  PASS  md_20_edge_cases                   ~50ms
  PASS  md_anchors_stress                  ~1500ms
  PASS  live_preview_load                  ~80ms
  ...
==============================================================
15 passed, 0 failed
```

If any fail, the failure output tells you which test and gives a
traceback. Usually it's a missing WebEngine, a stale `.chert/`
folder in a tempdir, or an offscreen-Qt font issue (safe to ignore).

## 7. Build order if you're rebuilding from scratch

If you're not just cloning — if you're actually reconstructing this
from nothing — build in this order. Each module is testable on its
own before you add the next.

### 7.1 `Chert_Managers.py`

The foundation. Everything imports Qt through this file so nothing
else has to care about PyQt5 vs PyQt6 (nothing does — it's PyQt6 only,
but the re-export is still the clean pattern).

Three things to build here, in order:

1. **Error handlers.** `_ErrorRecord`, `_BaseHandler`, then the ten
   subclasses. Ring buffer, per-context counts, thread-safe report.
   Mute/unmute. This is 400 lines of defensive plumbing and it's
   worth every line.

2. **VaultManager.** Path resolution, recursive scan with dotfolder
   pruning, `QFileSystemWatcher` with polling fallback. Everything
   that touches disk goes through the error handlers.

3. **Indexes.** `BacklinkIndex`, `SearchIndex`, `TagIndex`. Each one
   holds a `LazySQLiteConnection` (thread-local conns, WAL mode,
   `mmap_size=64MB`) and a `LazyValue` for schema init. Migrations
   tracked in a `schema_version` table.

4. **ChertSettings.** Per-vault settings JSON in `.chert/settings.json`.

### 7.2 `Markdown_Chert.py`

Two pieces:

1. **FastBuffer.** ctypes-based string accumulator. Falls back to
   `bytearray` if `memmove` can't be loaded.

2. **MarkdownRenderer.** Fenced-code stash/replace, HTML escape once,
   line-by-line block state machine (ul/ol/quote/table), inline
   transform pass (images, links, wikilinks, tags, bold, italic,
   strike, highlight, code).

Plus `MarkdownHighlighter` — a `QSyntaxHighlighter` with a fence-state
machine (block state 1 = inside fence) and a list of precompiled
regex rules.

Test it before moving on: `_stress.py` cases 1 and 2.

### 7.3 `Live_Preview.py`

Three classes:

1. **MarkdownEditor** — `QPlainTextEdit` subclass with list
   continuation on Enter.

2. **MarkdownPreview** — WebEngine when available, `QTextEdit`
   otherwise. The WebEngine path needs `ChertWebPage` as a
   `QWebEnginePage` subclass so `acceptNavigationRequest` actually
   intercepts. Don't try to monkey-patch it. It won't work. The
   comment in the source explains why.

3. **LivePreviewPane** — `QSplitter`, editor on the left, preview
   on the right, debounce timer, cheap hash skip, known-notes TTL.

### 7.4 `Graph_Chert.py`

The biggest module. Build order:

1. `BarnesHutTree` — quadtree with `_QuadNode` leaf/branch
   distinction and recursive `force_on`.

2. `GraphNode` (QGraphicsItem) and `GraphEdge` (QGraphicsLineItem).

3. `ForceGraphView` — the main canvas. `QGraphicsScene` with
   `NoIndex`. Timer-driven ticks at 33ms.

4. `GraphBuilder` — 24 static methods. Full vault, local, tags,
   orphans, most-connected, PageRank, communities, shortest path,
   similarity, property filter, word count, bidirectional, tag
   co-occurrence, link distance, etc.

5. `GraphWidget` — the toolbar-wrapped version used in the modal.

### 7.5 `Theme_Chert.py`

Two frozen dataclasses (`DARK`, `LIGHT`), a `stylesheet(theme)`
function returning one big f-string QSS blob, and an `Icon` class
of Unicode glyphs.

### 7.6 `Panels_Chert.py`

Six `QWidget` subclasses, each a self-contained panel. They emit
signals, they don't reach into the main window.

### 7.7 `Dialogs_Chert.py`

Command palette, quick switcher, settings dialog, about box. All
standard `QDialog` subclasses.

### 7.8 `UI_Chert.py`

Main window. Ribbon + splitter + two sidebars + editor area + status
bar. Menus. Command registration. Reindexing on startup. This is the
file that wires everything together, so build it last.

### 7.9 `Chert.py`

Thin. Preflight PyQt6 check, vault picker, apply theme, launch.

## 8. Common problems

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: PyQt6` | Dep not installed | `pip install PyQt6 PyQt6-WebEngine` |
| Preview shows raw HTML | WebEngine missing | Install `PyQt6-WebEngine`; fallback is `QTextEdit` |
| `QGraphicsScene::setBspTreeDepth: Depth is not valid` | You re-added `setBspTreeDepth` | Remove it. `NoIndex` and `BSP` are mutually exclusive. |
| Font fallback warnings | Consolas not on this machine | Change `editor_font` in Settings |
| `_stress.py` fails on `live_preview_html_reached_view` | WebEngine didn't return HTML in 5s | Run on real hardware, not in a VM without GPU |
| Search returns nothing | FTS5 not compiled | Fallback kicks in automatically; check `_fts` attribute |
| Backlinks empty after write | Index not rebuilt | `_reindex_vault` runs on window construction; check `.chert/backlinks.db` |

## 9. If you're picking this up after a long time away

1. Read `Research.md`. It's the architecture doc.
2. Run `python _stress.py`. If it passes, nothing rotted.
3. Open `Chert.py`, read down. It's 120 lines.
4. The graph is in `Graph_Chert.py`. The shell is in `UI_Chert.py`.
   Everything else is a service the shell uses.
5. Don't refactor before you run it. It works. It worked when you
   stopped. It still works.

---

*Built as a first project. Archived [DATE].*
```

---

## /Thea

# Chert

## Overview

Chert is a local-first Markdown knowledge base, built in Python with PyQt6, modeled on Obsidian. You point it at a folder, it treats every `.md` file as a note, it indexes wikilinks, tags, and full text into SQLite, and it gives you an Obsidian-shaped UI on top: ribbon, sidebars, tabs, command palette, live preview, graph view. Version 1.1.0 was the last active release. It's archived but not deleted.

The project started as a first project and ended as one. Everything — code, research, tests, notes — is preserved. The re-entry point is [[Research]] and `_stress.py`.

## Key Concepts

- **Vault** — any folder. Chert scans it, watches it, indexes it. Config lives in `.chert/` inside the vault.
- **Wikilink** — `[[Target]]` or `[[Target|Alias]]`. Indexed with surrounding context so backlinks panel can show snippets.
- **Live preview** — source on the left, rendered HTML on the right. QWebEngine drives KaTeX and Mermaid for real.
- **Error router** — every file, DB, and signal operation goes through a `safe_*` method on a handler. Ten handlers per manager module. This is the project's backbone.
- **Barnes-Hut** — the force graph uses a hand-rolled quadtree. `theta = 0.9`. Kicks in at 50 nodes.
- **GraphBuilder** — 24 static methods for building different graph views. PageRank, communities, shortest path, orphans, bidirectional, similarity, tag co-occurrence.
- **Cheap hash** — a fast non-cryptographic hash used to skip re-renders when text hasn't changed.

## Details

### Architecture layering

```
Chert_Managers    → Qt, error handlers, vault, indexes, settings
Markdown_Chert    → renderer, highlighter, FastBuffer
Theme_Chert       → dark/light, QSS, icon glyphs
Live_Preview      → editor, preview, split pane
Graph_Chert       → force graph, Barnes-Hut, GraphBuilder
Panels_Chert      → six side panels
Dialogs_Chert     → palette, switcher, settings, about
UI_Chert          → ribbon, sidebars, editor area, main window
Chert             → entry point
_stress           → headless tests

Every module imports Qt through `Chert_Managers` rather than directly from `PyQt6.QtCore` etc. Even though the code is PyQt6-only. The re-export is a habit from an earlier PyQt5-compat plan that got dropped. It's clean anyway.

### The error-router pattern

`Chert_Managers.py` defines `ManagerErrorRouter` with ten sub-handlers:

- `io` — file reads and writes, atomic via tmp + `os.replace`
- `path` — relative path resolution, Windows long-path prefix
- `watcher` — `QFileSystemWatcher` with polling fallback
- `scan` — recursive walk, dotfolder prune
- `sqlite` — connect, execute, transaction
- `search` — match, sanitize
- `config` — JSON load/save
- `signal` — emit, connect, disconnect
- `resource` — memory, file descriptors
- `migration` — schema versioning

Each handler has a 64-record ring buffer, per-context counts, mute/unmute, thread-safe report. Nothing throws to the event loop. If a file can't be read, `safe_read` reports and returns the default. If SQLite is locked, `safe_execute` reports and returns None. Every call site checks for None. That's the discipline of the codebase.

`Live_Preview`, `Graph_Chert` have their own smaller routers (`ErrorRouter`). Same pattern, fewer handlers.

### The BSP story

`Graph_Chert.py` has a comment:

> NoIndex is correct for a scene with continuously moving items. Do NOT call setBspTreeDepth — it is only valid with BspTreeIndex — the two are mutually exclusive.

This is a war wound. Somebody tried to add `setBspTreeDepth(8)` to speed up the graph. Qt complained. The fix was removing it. The comment stays so nobody re-adds it.

### The WebEngine subclass

`Live_Preview.py` defines `ChertWebPage(QWebEnginePage)`. The comment:

> Why a subclass and not a monkey-patch: acceptNavigationRequest is a C++ virtual method. Assigning a Python attribute named the same thing does not override dispatch. The only way to intercept is to override the method in a subclass.

Also a war wound. The `chert://open/<target>` scheme only works through this subclass. Otherwise clicking a wikilink in preview would try to open a bogus URL.

### The renderer's placeholder trick

Fenced code blocks are stashed as `\x00CODE{n}\x00` before the whole markdown body is `html.escape`'d. After escaping, the block state machine re-substitutes the actual code with its own escape applied. Inline code uses `\x01{n}\x01`. This lets the entire body be escaped once while preserving code literally.

### FastBuffer

`Markdown_Chert.py` loads `libc` or `msvcrt` via ctypes and does string accumulation via `memmove`. Falls back to `bytearray` if the libc lookup fails. Thread-local via `BufferPool`. Not a toy. Real optimization for a hot path.

### `_cheap_hash`

For documents over 512 characters:

```python
hash((n, text[:128], text[n//2-64:n//2+64], text[-128:]))
```

Faster than a full hash, good enough for change detection. Skips the entire render pass when the hash matches the last one and the known-notes set is unchanged.

### The known-notes TTL

`LivePreviewPane._KNOWN_NOTES_TTL = 1.5`. Wikilink resolution needs to know which notes exist. Walking the vault every keystroke is too slow. So the known-notes set is cached for 1.5s.

### Graph construction methods

`GraphBuilder` has 24 methods. The ones worth remembering:

- `full_vault` — everything, all edges
- `local_graph` — N-hop neighborhood of a note
- `pagerank` — 20 iterations, damping 0.85, top N
- `communities` — label propagation, 10 iterations
- `shortest_path` — BFS
- `orphans` — no incoming or outgoing links
- `most_connected` — top N by degree
- `bidirectional` — pairs that link to each other
- `by_tag_cooccurrence` — notes sharing ≥2 tags
- `similar_to` — shares outgoing targets with a note
- `unresolved` — wikilinks pointing at nonexistent notes, shown as stub nodes
- `by_link_distance` — BFS up to max_distance from seeds

## Examples

### Open a vault

```powershell
python Chert.py C:\Users\you\Documents\Vault
```

### Run the test suite

```powershell
python _stress.py
```

### Sketch a graph in the shell

```python
from Graph_Chert import ForceGraphView, GraphBuilder
view = ForceGraphView()
paths, edges = GraphBuilder.local_graph(vault, backlinks, "note.md", depth=2)
view.build(paths, edges)
```

### Add a graph construction method

```python
@staticmethod
def by_first_letter(vault, letter):
    letter = letter.lower()
    paths = [vault.rel_path(p) for p in vault.list_notes()
             if Path(p).stem.lower().startswith(letter)]
    return paths, []
```

Follow the existing pattern: static method, returns `(paths, edges)`. Edges can be empty; the view will still render nodes.

## Connections

- [[Obsidian]] — the app Chert is modeled on
- [[PyQt6]] — the GUI toolkit
- [[SQLite FTS5]] — full-text search backend
- [[Barnes-Hut]] — the O(n log n) n-body algorithm for the graph
- [[CodeMirror 6]] — Obsidian's editor, which Chert does *not* use (Chert uses `QPlainTextEdit`)
- [[KaTeX]] — math rendering
- [[Mermaid]] — diagram rendering
- [[Research]] — the architecture doc in the repo
- [[Audit]] — the audit note in the repo

## Open Questions

1. Is a two-pane split (source + preview) good enough, or does Chert need true inline WYSIWYG (Obsidian's Live Preview mode)?
2. Can `QGraphicsScene` handle 1000+ nodes at 60fps, or does the graph need a `QOpenGLWidget` viewport?
3. Should the index build be incremental (watch events trigger reindex per file) or full (current behavior: reindex the whole vault on startup)?
4. Is the ctypes `FastBuffer` actually faster than a plain `bytearray` on modern CPython? Worth benchmarking.
5. The `requirements.txt` claims a PyQt5 fallback. The code is PyQt6-only. Should the comment be deleted or should the fallback actually be built?
6. Is there a clean path to Linux/macOS, or is the Windows-first assumption baked in (long paths, APPDATA, `msvcrt`)?

## Archive note

Chert is archived. Development is paused. The code, the research, the tests, and these notes are all preserved. If you're reading this later and the project has moved, check the current commit of `Research.md` and `_stress.py` first — those are the source of truth for what works.

There's a real chance this comes back. There's also a real chance it doesn't. Either is fine. The point of archiving instead of deleting is that the option stays open.

---

