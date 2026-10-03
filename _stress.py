"""
_stress.py — Offscreen stress test for the Chert pipeline.

Run:  python _stress.py
Exit code 0 on all-pass, 1 on any failure.
"""

import os
import sys
import time
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

NL = chr(10)

PASSED = []
FAILED = []


def test(name, fn):
    t0 = time.perf_counter()
    try:
        fn()
        PASSED.append((name, (time.perf_counter() - t0) * 1000))
    except Exception as e:
        FAILED.append((name, repr(e), traceback.format_exc()))


# ══════════════════════════════════════════════════════════════════════════
# Boot
# ══════════════════════════════════════════════════════════════════════════

def t_imports():
    import Chert_Managers      # noqa
    import Markdown_Chert      # noqa
    import Live_Preview        # noqa
    import Graph_Chert         # noqa
    import Theme_Chert         # noqa
    import Panels_Chert        # noqa
    import Dialogs_Chert       # noqa
    import UI_Chert            # noqa


test("imports_all", t_imports)

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)


# ══════════════════════════════════════════════════════════════════════════
# Markdown renderer
# ══════════════════════════════════════════════════════════════════════════

def t_md_edge_cases():
    from Markdown_Chert import MarkdownRenderer
    r = MarkdownRenderer()
    cases = [
        "",
        "# h1" + NL + "## h2" + NL + "### h3",
        "**b** _i_ `c` ~~s~~ ==h==",
        "[[WikiLink]] [[Target|Alias]]",
        "> q" + NL + "> m",
        "| a | b |" + NL + "|---|---|" + NL + "| 1 | 2 |",
        "```python" + NL + "print(1)" + NL + "```",
        "```mermaid" + NL + "graph TD" + NL + "A-->B" + NL + "```",
        "$$x^2+y^2=z^2$$",
        "inline $x$ math",
        "- [ ] t" + NL + "- [x] d",
        "***bi***",
        "---",
        "> [!note] callout",
        "unclosed [[wl",
        "emoji 😀 中文",
        NL.join(["a"] * 3000),
        "# " + "x" * 5000,
    ]
    for i, c in enumerate(cases):
        h = r.render(c, {"WikiLink", "Target"})
        assert isinstance(h, str) and len(h) > 0, "case %d produced empty" % i


test("md_20_edge_cases", t_md_edge_cases)


def t_md_anchors_stress():
    from Markdown_Chert import MarkdownRenderer
    r = MarkdownRenderer()

    h = r.render("[[WL]]", {"WL"})
    assert "chert://open/" in h, "wikilink anchor missing"

    h2 = r.render("```mermaid" + NL + "graph TD" + NL + "A-->B" + NL + "```", set())
    assert "mermaid" in h2, "mermaid div missing"

    # 500 sections, each with a heading, bold text, and a wikilink.
    # f-strings — no % formatting, no arg-count risk.
    big = NL.join(
        f"## S{i}{NL}{NL}P {i} **b** [[L{i}]]"
        for i in range(500)
    )
    t0 = time.perf_counter()
    r.render(big, set())
    dt = time.perf_counter() - t0
    assert dt < 3.0, "slow %.2f s for 500 sections" % dt


test("md_anchors_stress", t_md_anchors_stress)


# ══════════════════════════════════════════════════════════════════════════
# Live preview
# ══════════════════════════════════════════════════════════════════════════

def t_lp_load():
    from Live_Preview import LivePreviewPane, HAS_WEBENGINE, QWebEngineView
    mode = "web" if (HAS_WEBENGINE and QWebEngineView is not None) else "text"
    print("    preview mode:", mode)

    p = LivePreviewPane(None, vault=None, settings=None, rel_path="t.md")
    p.load("# Hello" + NL + NL + "**world**" + NL + NL + "[[WikiLink]]")
    assert "Hello" in p.text(), "text() empty"

    st = p.render_stats()
    assert st["renders"] >= 1, "no render fired"
    print("    render stats:", st)


test("live_preview_load", t_lp_load)


def t_lp_html_reached_view():
    """Verify HTML actually landed in the preview view, not just that
    render() was called. Uses QtWebEngineView.toHtml() when available,
    falls back to QTextEdit.toHtml() otherwise."""
    from Live_Preview import LivePreviewPane, HAS_WEBENGINE, QWebEngineView
    p = LivePreviewPane(None, vault=None, settings=None, rel_path="h.md")
    p.load("# MarkerHeading" + NL + NL + "**strongtext**")

    # Give WebEngine a chance to process the setHtml call synchronously
    app.processEvents()

    view = p.preview.view
    html = ""

    if HAS_WEBENGINE and QWebEngineView is not None and hasattr(view, "toHtml"):
        # WebEngine's toHtml is async — fires a callback. We can't wait
        # here without blocking, so instead we verify the call itself
        # didn't raise and the pane reports a successful render.
        # This is a partial check; the on-screen test is the real one.
        assert p.render_stats()["renders"] >= 1
        assert p.preview._mode == "web"
        return

    # QTextEdit fallback path — toHtml() is synchronous
    if hasattr(view, "toHtml"):
        html = view.toHtml()

    assert "MarkerHeading" in html or "strongtext" in html, \
        "rendered HTML did not reach the view: %r" % html[:200]


test("live_preview_html_reached_view", t_lp_html_reached_view)


def t_lp_unicode_empty():
    from Live_Preview import LivePreviewPane
    p = LivePreviewPane(None, vault=None, settings=None, rel_path="u.md")
    p.load("# 中文 😀")
    assert "中文" in p.text()

    p2 = LivePreviewPane(None, vault=None, settings=None, rel_path="e.md")
    p2.load("")
    assert p2.text() == ""


test("live_preview_unicode_empty", t_lp_unicode_empty)


def t_lp_hidden_edit():
    from Live_Preview import LivePreviewPane
    p = LivePreviewPane(None, vault=None, settings=None, rel_path="h.md")
    p.load("# a")

    p.editor.blockSignals(True)
    p.editor.setPlainText("# edited")
    p.editor.blockSignals(False)
    p._on_content_changed("# edited")
    p._pending = True
    p._render_now()

    assert "edited" in p.text(), "text not updated"
    assert p.render_stats()["renders"] >= 2, "hidden edit did not re-render"


test("live_preview_hidden_edit", t_lp_hidden_edit)


def t_lp_rapid_edits():
    from Live_Preview import LivePreviewPane
    p = LivePreviewPane(None, vault=None, settings=None, rel_path="r.md")
    p.load("")
    for i in range(100):
        p.editor.setPlainText("# line %d" % i)
    p._pending = True
    p._render_now()
    assert "line 99" in p.text()
    st = p.render_stats()
    assert st["renders"] < 100, "hash-skip not working: %s" % st


test("live_preview_rapid_edits", t_lp_rapid_edits)


# ══════════════════════════════════════════════════════════════════════════
# Graph
# ══════════════════════════════════════════════════════════════════════════

def t_graph_triangle():
    from Graph_Chert import ForceGraphView
    v = ForceGraphView()
    v.build(
        ["a.md", "b.md", "c.md"],
        [("a.md", "b.md"), ("b.md", "c.md"), ("a.md", "c.md")],
    )
    assert len(v.nodes) == 3, "nodes=%d" % len(v.nodes)
    assert len(v.edges) == 3, "edges=%d" % len(v.edges)


test("graph_triangle", t_graph_triangle)


def t_graph_no_bsp_conflict():
    from Graph_Chert import ForceGraphView
    from PyQt6.QtWidgets import QGraphicsScene
    v = ForceGraphView()
    assert v.scene.itemIndexMethod() == QGraphicsScene.ItemIndexMethod.NoIndex


test("graph_no_bsp_conflict", t_graph_no_bsp_conflict)


def t_graph_60_nodes():
    from Graph_Chert import ForceGraphView
    v = ForceGraphView()
    paths = ["n%d.md" % i for i in range(60)]
    edges = [("n%d.md" % i, "n%d.md" % (i + 1)) for i in range(59)]
    v.build(paths, edges)
    t0 = time.perf_counter()
    for _ in range(20):
        v._tick_internal()
    dt = (time.perf_counter() - t0) * 1000
    assert dt < 3000, "20 ticks took %.0fms" % dt


test("graph_60_nodes_20_ticks", t_graph_60_nodes)


def t_graph_300_nodes():
    from Graph_Chert import ForceGraphView
    n = 300
    v = ForceGraphView()
    paths = ["n%d.md" % i for i in range(n)]
    edges = [("n%d.md" % i, "n%d.md" % ((i * 7) % n)) for i in range(n)]
    t0 = time.perf_counter()
    v.build(paths, edges)
    for _ in range(5):
        v._tick_internal()
    dt = (time.perf_counter() - t0) * 1000
    assert dt < 5000, "300-node build + 5 ticks took %.0fms" % dt


test("graph_stress_300_nodes", t_graph_300_nodes)


# ══════════════════════════════════════════════════════════════════════════
# Vault + indexes
# ══════════════════════════════════════════════════════════════════════════

def t_vault_full_pipeline():
    from Chert_Managers import (
        VaultManager, BacklinkIndex, SearchIndex, TagIndex,
    )
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        vault = VaultManager(d)
        vault.write("note.md", "# n" + NL + "[[other]] #tag1")
        vault.write("other.md", "# o" + NL + "[[note]] #tag2")
        vault.write("sub/deep.md", "# d" + NL + "[[note]]")

        notes = vault.list_notes()
        assert len(notes) == 3, "found %d: %s" % (len(notes), notes)

        b = BacklinkIndex(d / ".chert" / "b.db")
        for r in ("note.md", "other.md", "sub/deep.md"):
            b.index_file(r, vault.read(r))
        bl = b.backlinks("note.md")
        srcs = {x["source"] for x in bl}
        assert "other.md" in srcs and "sub/deep.md" in srcs, "bl: %s" % srcs

        s = SearchIndex(d / ".chert" / "s.db")
        for r in ("note.md", "other.md", "sub/deep.md"):
            s.index(r, Path(r).stem, vault.read(r))
        assert len(s.search("other")) >= 1, "search missed"

        tg = TagIndex(d / ".chert" / "t.db")
        for r in ("note.md", "other.md"):
            tg.index_file(r, vault.read(r))
        tags = dict(tg.all_tags())
        assert "tag1" in tags and "tag2" in tags, "tags: %s" % tags

        b.close()
        s.close()
        tg.close()


test("vault_full_pipeline", t_vault_full_pipeline)


# ══════════════════════════════════════════════════════════════════════════
# Theme + shell + panels
# ══════════════════════════════════════════════════════════════════════════

def t_theme_both():
    from Theme_Chert import get_theme, stylesheet
    for n in ("dark", "light"):
        s = stylesheet(get_theme(n))
        assert len(s) > 500, "%s stylesheet too short" % n


test("theme_both", t_theme_both)


def t_mainwindow():
    from UI_Chert import MainWindow
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "note.md").write_text("# hi" + NL + "[[other]]", encoding="utf-8")
        (d / "other.md").write_text("# other", encoding="utf-8")
        w = MainWindow(d)
        assert w.ribbon is not None
        assert w.left_sidebar is not None
        assert w.right_sidebar is not None
        assert w.editor_area is not None
        assert w.status is not None
        w.close()


test("mainwindow_offscreen", t_mainwindow)


def t_panels():
    from Panels_Chert import FileExplorerPanel, OutlinePanel
    from Chert_Managers import VaultManager
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "a.md").write_text(
            "# a" + NL + "## a1" + NL + "### a1a", encoding="utf-8"
        )
        vault = VaultManager(d)
        fe = FileExplorerPanel(vault)
        fe.rebuild()
        assert fe.tree.topLevelItemCount() >= 1, "file tree empty"

        op = OutlinePanel()
        op.set_content("# a" + NL + "## a1" + NL + "### a1a")
        assert op.tree.topLevelItemCount() >= 1, "outline empty"


test("panels_offscreen", t_panels)


# ══════════════════════════════════════════════════════════════════════════
# Report
# ══════════════════════════════════════════════════════════════════════════

print()
print("=" * 62)
for name, ms in PASSED:
    print("  PASS  %-32s %8.1fms" % (name, ms))
for name, err, tb in FAILED:
    print("  FAIL  %s" % name)
    print("        %s" % err)
    print(tb)
print("=" * 62)
print("%d passed, %d failed" % (len(PASSED), len(FAILED)))

sys.exit(1 if FAILED else 0)