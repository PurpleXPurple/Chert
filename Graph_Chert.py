"""
Graph_Chert.py — Force-directed note graph.

Barnes-Hut quadtree, Qt scene tuning, image/GIF nodes, Obsidian-style
filters/groups, Notion-style relation coloring, 24 graph construction
methods via GraphBuilder.

Public surface:
  GraphNode, GraphEdge, ForceGraphView, GraphWidget
  GraphBuilder, GraphConfig, GraphFilter, NodeGroup, RelationType
"""

import math
import random
import time
import traceback
from collections import defaultdict, deque
from pathlib import Path

from Chert_Managers import (
    Qt, QTimer, QPointF, QRectF, QWidget, QVBoxLayout, QHBoxLayout,
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem,
    QGraphicsPixmapItem, QLabel, QPushButton, QSlider, QCheckBox,
    QComboBox, QLineEdit, QMenu, QColor, QFont, QPen, QBrush, QPainter,
    QPixmap, QImage, QImageReader, QMovie, QSize, QPoint,
    QPolygonF, QFrame, pyqtSignal,
)


# ══════════════════════════════════════════════════════════════════════════
# Error handling — four categories
# ══════════════════════════════════════════════════════════════════════════

CATEGORY_GRAPH = "graph"
CATEGORY_IMAGE = "image"
CATEGORY_LAYOUT = "layout"
CATEGORY_UI = "ui"


class _ErrorRecord:
    __slots__ = ("category", "context", "exc_type", "exc_msg", "trace", "ts")

    def __init__(self, category, context, exc, trace=""):
        self.category = category
        self.context = context
        self.exc_type = type(exc).__name__ if exc else "None"
        self.exc_msg = str(exc) if exc else ""
        self.trace = trace
        self.ts = time.time()


class _BaseHandler:
    __slots__ = ("name", "_ring", "_max", "_counts", "_on_error", "_muted")

    def __init__(self, name, max_records=64):
        self.name = name
        self._max = max_records
        self._ring = []
        self._counts = {}
        self._on_error = None
        self._muted = set()

    def set_sink(self, callback):
        self._on_error = callback

    def mute(self, context):
        self._muted.add(context)

    def unmute(self, context):
        self._muted.discard(context)

    def report(self, context, exc, trace=""):
        rec = _ErrorRecord(self.name, context, exc, trace)
        self._ring.append(rec)
        if len(self._ring) > self._max:
            del self._ring[:len(self._ring) - self._max]
        self._counts[context] = self._counts.get(context, 0) + 1
        if self._on_error and context not in self._muted:
            try:
                self._on_error(rec)
            except Exception:
                pass

    def count(self, context=None):
        if context is None:
            return sum(self._counts.values())
        return self._counts.get(context, 0)

    def recent(self, n=10):
        return self._ring[-n:]

    def clear(self):
        self._ring.clear()
        self._counts.clear()


class GraphErrorHandler(_BaseHandler):
    def __init__(self, max_records=64):
        super().__init__(CATEGORY_GRAPH, max_records)

    def safe_add_node(self, view, node_id, label, degree=0):
        try:
            return view.add_node(node_id, label, degree)
        except (RuntimeError, ValueError, KeyError) as e:
            self.report("add_node", e, traceback.format_exc())
            return None

    def safe_add_edge(self, view, source_id, target_id):
        try:
            view.add_edge(source_id, target_id)
            return True
        except (RuntimeError, ValueError, KeyError) as e:
            self.report("add_edge", e, traceback.format_exc())
            return False


class ImageErrorHandler(_BaseHandler):
    def __init__(self, max_records=64):
        super().__init__(CATEGORY_IMAGE, max_records)

    def safe_load_pixmap(self, path, max_size=64):
        try:
            reader = QImageReader(str(path))
            reader.setAutoTransform(True)
            if max_size > 0:
                reader.setScaledSize(QSize(max_size, max_size))
            img = reader.read()
            if img.isNull():
                raise ValueError(f"QImageReader returned null for {path}")
            return QPixmap.fromImage(img)
        except Exception as e:
            self.report("load_pixmap", e, traceback.format_exc())
            return None

    def safe_movie(self, path):
        try:
            movie = QMovie(str(path))
            if not movie.isValid():
                raise ValueError(f"Invalid GIF: {path}")
            return movie
        except Exception as e:
            self.report("load_movie", e, traceback.format_exc())
            return None

    @staticmethod
    def supported_formats():
        try:
            return sorted(
                bytes(f).decode("ascii", "replace")
                for f in QImageReader.supportedImageFormats()
            )
        except Exception:
            return ["png", "jpg", "jpeg", "bmp", "gif", "webp"]


class LayoutErrorHandler(_BaseHandler):
    def __init__(self, max_records=64):
        super().__init__(CATEGORY_LAYOUT, max_records)

    def safe_tick(self, view):
        try:
            view._tick_internal()
        except (ArithmeticError, ValueError, OverflowError,
                RecursionError, MemoryError) as e:
            self.report("tick", e, traceback.format_exc())


class GraphUIErrorHandler(_BaseHandler):
    def __init__(self, max_records=64):
        super().__init__(CATEGORY_UI, max_records)

    def safe_connect(self, signal, slot, context="connect"):
        try:
            signal.connect(slot)
            return True
        except (TypeError, RuntimeError) as e:
            self.report(context, e, traceback.format_exc())
            return False

    def safe_slider(self, slider, value, context="slider"):
        try:
            slider.setValue(int(value))
            return True
        except (RuntimeError, TypeError, ValueError) as e:
            self.report(context, e, traceback.format_exc())
            return False


class ErrorRouter:
    __slots__ = ("graph", "image", "layout", "ui")

    def __init__(self):
        self.graph = GraphErrorHandler()
        self.image = ImageErrorHandler()
        self.layout = LayoutErrorHandler()
        self.ui = GraphUIErrorHandler()

    def set_sink(self, callback):
        for h in self.all_handlers():
            h.set_sink(callback)

    def all_handlers(self):
        return (self.graph, self.image, self.layout, self.ui)

    def total_count(self):
        return sum(h.count() for h in self.all_handlers())

    def summary(self):
        return {h.name: h.count() for h in self.all_handlers()}


_DEFAULT_ROUTER = ErrorRouter()


def default_router():
    return _DEFAULT_ROUTER


# ══════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════

class RelationType:
    LINK = "link"
    MENTION = "mention"
    BACKLINK = "backlink"
    RELATION = "relation"
    EMBED = "embed"
    TAG = "tag"

    COLORS = {
        LINK: QColor(90, 130, 200, 180),
        MENTION: QColor(200, 140, 90, 180),
        BACKLINK: QColor(130, 200, 130, 180),
        RELATION: QColor(200, 200, 90, 180),
        EMBED: QColor(180, 90, 200, 180),
        TAG: QColor(90, 200, 200, 180),
    }

    @classmethod
    def color(cls, rel_type):
        return cls.COLORS.get(rel_type, cls.COLORS[cls.LINK])


class GraphConfig:
    __slots__ = (
        "repulsion", "spring_length", "spring_k", "damping",
        "centering", "max_velocity", "iterations_per_tick",
        "barnes_hut", "barnes_hut_theta", "barnes_hut_threshold",
        "node_base_size", "node_max_size", "link_base_width",
        "link_max_width", "text_fade_threshold", "show_arrows",
        "show_labels", "lod_enabled", "lod_threshold",
        "animate_timelapse", "timelapse_speed",
    )

    def __init__(self):
        self.repulsion = 12000.0
        self.spring_length = 140.0
        self.spring_k = 0.05
        self.damping = 0.82
        self.centering = 0.004
        self.max_velocity = 14.0
        self.iterations_per_tick = 1
        self.barnes_hut = True
        self.barnes_hut_theta = 0.9
        self.barnes_hut_threshold = 50
        self.node_base_size = 6.0
        self.node_max_size = 24.0
        self.link_base_width = 1.2
        self.link_max_width = 3.5
        self.text_fade_threshold = 0.55
        self.show_arrows = False
        self.show_labels = True
        self.lod_enabled = True
        self.lod_threshold = 0.4
        self.animate_timelapse = False
        self.timelapse_speed = 2.0


class GraphFilter:
    __slots__ = (
        "search_query", "show_tags", "show_attachments",
        "show_orphans", "existing_only", "min_degree",
        "max_degree", "date_from", "date_to", "properties",
    )

    def __init__(self):
        self.search_query = ""
        self.show_tags = True
        self.show_attachments = True
        self.show_orphans = True
        self.existing_only = True
        self.min_degree = 0
        self.max_degree = 10_000
        self.date_from = None
        self.date_to = None
        self.properties = {}

    def matches(self, node_id, label, degree, file_path=None,
                tags=None, is_attachment=False, created=None):
        if is_attachment and not self.show_attachments:
            return False
        if degree == 0 and not self.show_orphans:
            return False
        if self.search_query:
            q = self.search_query.lower()
            if q not in label.lower() and q not in node_id.lower():
                return False
        if self.min_degree > degree or self.max_degree < degree:
            return False
        if created is not None:
            if self.date_from and created < self.date_from:
                return False
            if self.date_to and created > self.date_to:
                return False
        return True


class NodeGroup:
    __slots__ = ("name", "query", "color", "match_fn", "node_ids")

    def __init__(self, name, query, color, match_fn=None):
        self.name = name
        self.query = query
        self.color = QColor(color) if isinstance(color, str) else color
        self.match_fn = match_fn
        self.node_ids = set()

    def matches(self, node_id, label, tags=None, properties=None):
        if self.match_fn:
            try:
                return self.match_fn(node_id, label, tags or [], properties or {})
            except Exception:
                return False
        q = self.query.lower()
        if q in label.lower() or q in node_id.lower():
            return True
        if tags and any(q in t.lower() for t in tags):
            return True
        if properties:
            for v in properties.values():
                if q in str(v).lower():
                    return True
        return False


# ══════════════════════════════════════════════════════════════════════════
# Barnes-Hut quadtree
# ══════════════════════════════════════════════════════════════════════════

class _QuadNode:
    __slots__ = ("x", "y", "size", "mass", "cx", "cy",
                 "children", "body", "is_leaf")

    def __init__(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size
        self.mass = 0.0
        self.cx = 0.0
        self.cy = 0.0
        self.children = None
        self.body = None
        self.is_leaf = True


class BarnesHutTree:
    __slots__ = ("root", "theta", "size")

    def __init__(self, theta=0.9):
        self.theta = theta
        self.root = None
        self.size = 0.0

    def build(self, nodes):
        if not nodes:
            return
        self.size = 0
        min_x = min(n.x() for n in nodes)
        min_y = min(n.y() for n in nodes)
        max_x = max(n.x() for n in nodes)
        max_y = max(n.y() for n in nodes)
        w = max(max_x - min_x, max_y - min_y, 1.0)
        self.size = w
        self.root = _QuadNode(min_x, min_y, w)
        for n in nodes:
            self._insert(self.root, n)

    def _insert(self, node, body):
        if node.is_leaf and node.body is None:
            node.body = body
            node.mass = 1.0
            node.cx = body.x()
            node.cy = body.y()
            return
        if node.is_leaf:
            node.is_leaf = False
            old = node.body
            node.body = None
            self._subdivide(node)
            self._insert_child(node, old)
        self._insert_child(node, body)

    def _subdivide(self, node):
        h = node.size / 2
        node.children = [
            _QuadNode(node.x, node.y, h),
            _QuadNode(node.x + h, node.y, h),
            _QuadNode(node.x, node.y + h, h),
            _QuadNode(node.x + h, node.y + h, h),
        ]

    def _insert_child(self, node, body):
        qx = 1 if body.x() >= node.x + node.size / 2 else 0
        qy = 1 if body.y() >= node.y + node.size / 2 else 0
        idx = qy * 2 + qx
        self._insert(node.children[idx], body)
        total = node.mass + 1.0
        node.cx = (node.cx * node.mass + body.x()) / total
        node.cy = (node.cy * node.mass + body.y()) / total
        node.mass = total

    def force_on(self, body, node=None):
        if node is None:
            node = self.root
        if node is None or node.mass == 0:
            return 0.0, 0.0
        dx = body.x() - node.cx
        dy = body.y() - node.cy
        d2 = dx * dx + dy * dy
        if d2 < 0.5:
            dx = random.uniform(-1.0, 1.0)
            dy = random.uniform(-1.0, 1.0)
            d2 = 1.0
        d = math.sqrt(d2)

        if node.is_leaf or (node.size / d) < self.theta:
            if node.body is body:
                return 0.0, 0.0
            f = node.mass / d2
            return (dx / d) * f, (dy / d) * f

        fx = fy = 0.0
        for child in node.children:
            cfx, cfy = self.force_on(body, child)
            fx += cfx
            fy += cfy
        return fx, fy


# ══════════════════════════════════════════════════════════════════════════
# Graph node
# ══════════════════════════════════════════════════════════════════════════

class GraphNode(QGraphicsItem):
    def __init__(self, node_id, label, size=8.0, group_color=None,
                 pixmap=None, is_attachment=False):
        super().__init__()
        self.node_id = node_id
        self.label = label
        self.radius = float(size)
        self.velocity = [0.0, 0.0]
        self.pinned = False
        self.group_color = group_color
        self.is_attachment = is_attachment
        self._pixmap = pixmap
        self._pixmap_item = None
        self._hovered = False
        self._selected = False
        self._degree = 0
        self._created = None
        self._tags = []
        self._rel_type = None

        self.setPos(random.uniform(-220, 220), random.uniform(-220, 220))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

        self._cached_rect = QRectF(
            -self.radius - 4, -self.radius - 4,
            self.radius * 2 + 8, self.radius * 2 + 8,
        )

    def boundingRect(self):
        return self._cached_rect

    def set_pixmap(self, pixmap):
        self._pixmap = pixmap
        if pixmap and not pixmap.isNull():
            target = max(self.radius * 2, 16)
            scaled = pixmap.scaled(
                int(target), int(target),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            if self._pixmap_item is None:
                self._pixmap_item = QGraphicsPixmapItem(scaled, self)
                self._pixmap_item.setPos(-scaled.width() / 2,
                                         -scaled.height() / 2)
                self._pixmap_item.setZValue(1)
            else:
                self._pixmap_item.setPixmap(scaled)
        self.prepareGeometryChange()
        self._cached_rect = QRectF(
            -self.radius - 4, -self.radius - 4,
            self.radius * 2 + 8, self.radius * 2 + 8,
        )
        self.update()

    def paint(self, painter, option, widget=None):
        lod = option.levelOfDetailFromTransform(painter.worldTransform())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.group_color:
            fill = self.group_color
            border = fill.darker(130)
        elif self.isSelected():
            fill = QColor("#ffd700")
            border = QColor("#ffed4e")
        elif self._hovered:
            fill = QColor("#9a7fd1")
            border = QColor("#c586c0")
        else:
            fill = QColor("#6f42c1")
            border = QColor("#4a2d8a")

        if self.is_attachment:
            fill = fill.lighter(110)

        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 2))
        painter.drawEllipse(QPointF(0, 0), self.radius, self.radius)

        if self._pixmap_item and lod > 0.5:
            self._pixmap_item.setVisible(True)
        elif self._pixmap_item:
            self._pixmap_item.setVisible(False)

        if (self._hovered or self.isSelected()) and lod > 0.3:
            painter.setFont(QFont("Segoe UI", 9))
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(self.label) + 12
            th = fm.height() + 6
            rect = QRectF(-tw / 2, self.radius + 4, tw, th)
            painter.setBrush(QBrush(QColor(30, 30, 30, 235)))
            painter.setPen(QPen(QColor("#555")))
            painter.drawRoundedRect(rect, 4, 4)
            painter.setPen(QPen(QColor("#e0e0e0")))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.label)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            scene = self.scene()
            if scene is not None:
                for item in scene.items():
                    if isinstance(item, GraphEdge):
                        item.update_position()
        return super().itemChange(change, value)


# ══════════════════════════════════════════════════════════════════════════
# Graph edge
# ══════════════════════════════════════════════════════════════════════════

class GraphEdge(QGraphicsLineItem):
    def __init__(self, source, target, rel_type=RelationType.LINK,
                 width=1.2, show_arrows=False):
        super().__init__()
        self.source = source
        self.target = target
        self.rel_type = rel_type
        self._width = width
        self._show_arrows = show_arrows
        color = RelationType.color(rel_type)
        self.setPen(QPen(color, width))
        self.setZValue(-1)
        self.update_position()

    def update_position(self):
        self.prepareGeometryChange()
        self.setLine(
            self.source.x(), self.source.y(),
            self.target.x(), self.target.y(),
        )

    def set_show_arrows(self, show):
        self._show_arrows = show
        self.update()

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self._show_arrows:
            line = self.line()
            if line.length() < 20:
                return
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(self.pen().color(), 1.5))
            angle = math.atan2(line.dy(), line.dx())
            size = 8
            tx = line.x2() - self.target.radius * math.cos(angle)
            ty = line.y2() - self.target.radius * math.sin(angle)
            p1 = QPointF(
                tx - size * math.cos(angle - 0.4),
                ty - size * math.sin(angle - 0.4),
            )
            p2 = QPointF(
                tx - size * math.cos(angle + 0.4),
                ty - size * math.sin(angle + 0.4),
            )
            painter.drawPolygon(QPolygonF([QPointF(tx, ty), p1, p2]))


# ══════════════════════════════════════════════════════════════════════════
# Force graph view
# ══════════════════════════════════════════════════════════════════════════

class ForceGraphView(QGraphicsView):
    node_clicked = pyqtSignal(str)
    node_hovered = pyqtSignal(str)
    edge_clicked = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-4000, -4000, 8000, 8000)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#181818")))
        self.setStyleSheet("border: none;")
        self.setAcceptDrops(True)

        self.scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.scene.setBspTreeDepth(8)
        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True
        )

        self.config = GraphConfig()
        self.filter = GraphFilter()
        self.groups = []
        self._errors = _DEFAULT_ROUTER

        self.nodes = {}
        self.edges = []
        self._adjacency = defaultdict(set)

        self._bh_tree = BarnesHutTree(self.config.barnes_hut_theta)

        self._timelapse_queue = []
        self._timelapse_timer = QTimer(self)
        self._timelapse_timer.timeout.connect(self._timelapse_step)
        self._timelapse_timer.setInterval(120)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.setInterval(33)
        self.timer.start()

    def clear_graph(self):
        for item in list(self.scene.items()):
            self.scene.removeItem(item)
        self.nodes.clear()
        self.edges.clear()
        self._adjacency.clear()

    def add_node(self, node_id, label, degree=0, **kwargs):
        if node_id in self.nodes:
            return self.nodes[node_id]
        size = self.config.node_base_size + min(degree, 20) * 0.6
        size = min(size, self.config.node_max_size)
        node = GraphNode(
            node_id, label, size=size,
            group_color=kwargs.get("group_color"),
            pixmap=kwargs.get("pixmap"),
            is_attachment=kwargs.get("is_attachment", False),
        )
        node._degree = degree
        node._created = kwargs.get("created")
        node._tags = kwargs.get("tags", [])
        self.scene.addItem(node)
        self.nodes[node_id] = node
        return node

    def add_edge(self, source_id, target_id, rel_type=RelationType.LINK):
        s = self.nodes.get(source_id)
        t = self.nodes.get(target_id)
        if not s or not t:
            return
        width = self.config.link_base_width
        edge = GraphEdge(
            s, t, rel_type=rel_type, width=width,
            show_arrows=self.config.show_arrows,
        )
        self.scene.addItem(edge)
        self.edges.append(edge)
        self._adjacency[source_id].add(target_id)
        self._adjacency[target_id].add(source_id)

    def build(self, note_paths, edges):
        self.clear_graph()
        if not note_paths:
            return
        path_set = set(note_paths)
        stem_to_path = {}
        for p in note_paths:
            stem_to_path[Path(p).stem.lower()] = p
            stem_to_path[p.lower()] = p

        degree = defaultdict(int)
        normalized = []
        for src, tgt in edges:
            s = src if src in path_set else stem_to_path.get(src.lower(), src)
            t = tgt if tgt in path_set else stem_to_path.get(tgt.lower(), tgt)
            if s not in path_set or t not in path_set or s == t:
                continue
            degree[s] += 1
            degree[t] += 1
            normalized.append((s, t))

        for p in note_paths:
            self.add_node(p, Path(p).stem, degree.get(p, 0))
        for s, t in normalized:
            self.add_edge(s, t)

    def _tick(self):
        self._errors.layout.safe_tick(self)

    def _tick_internal(self):
        node_list = list(self.nodes.values())
        n = len(node_list)
        if n == 0:
            return

        use_bh = self.config.barnes_hut and n >= self.config.barnes_hut_threshold
        if use_bh:
            self._bh_tree.theta = self.config.barnes_hut_theta
            self._bh_tree.build(node_list)

        for _ in range(self.config.iterations_per_tick):
            for i, a in enumerate(node_list):
                if a.pinned:
                    continue
                ax, ay = a.x(), a.y()
                if use_bh:
                    fx, fy = self._bh_tree.force_on(a)
                    fx *= self.config.repulsion / max(self._bh_tree.size, 1.0)
                    fy *= self.config.repulsion / max(self._bh_tree.size, 1.0)
                else:
                    fx = fy = 0.0
                    for j, b in enumerate(node_list):
                        if i == j:
                            continue
                        dx = ax - b.x()
                        dy = ay - b.y()
                        d2 = dx * dx + dy * dy
                        if d2 < 0.5:
                            dx = random.uniform(-1.0, 1.0)
                            dy = random.uniform(-1.0, 1.0)
                            d2 = 1.0
                        inv = self.config.repulsion / d2
                        inv_d = inv / math.sqrt(d2)
                        fx += dx * inv_d
                        fy += dy * inv_d

                fx -= ax * self.config.centering
                fy -= ay * self.config.centering

                a.velocity[0] = (a.velocity[0] + fx) * self.config.damping
                a.velocity[1] = (a.velocity[1] + fy) * self.config.damping

            for edge in self.edges:
                s, t = edge.source, edge.target
                dx = t.x() - s.x()
                dy = t.y() - s.y()
                d = math.sqrt(dx * dx + dy * dy) or 1.0
                force = (d - self.config.spring_length) * self.config.spring_k
                ux = dx / d
                uy = dy / d
                if not s.pinned:
                    s.velocity[0] += ux * force
                    s.velocity[1] += uy * force
                if not t.pinned:
                    t.velocity[0] -= ux * force
                    t.velocity[1] -= uy * force

            for a in node_list:
                if a.pinned:
                    continue
                vx, vy = a.velocity
                sp = math.sqrt(vx * vx + vy * vy)
                if sp > self.config.max_velocity:
                    vx = vx / sp * self.config.max_velocity
                    vy = vy / sp * self.config.max_velocity
                a.setPos(a.x() + vx, a.y() + vy)

        for edge in self.edges:
            edge.update_position()

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.position().toPoint())
        if isinstance(item, GraphNode):
            self.node_clicked.emit(item.node_id)
        elif isinstance(item, GraphEdge):
            self.edge_clicked.emit(item.source.node_id, item.target.node_id)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                p = Path(url.toLocalFile())
                if p.suffix.lower().lstrip(".") in ImageErrorHandler.supported_formats():
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            ext = p.suffix.lower().lstrip(".")
            if ext not in ImageErrorHandler.supported_formats():
                continue
            pos = self.mapToScene(event.position().toPoint())
            self._add_image_node(p, pos)
        event.acceptProposedAction()

    def _add_image_node(self, path, pos):
        pixmap = self._errors.image.safe_load_pixmap(path, max_size=64)
        if pixmap is None:
            return
        node_id = f"__img__{path.stem}_{int(time.time() * 1000) % 100000}"
        node = self.add_node(
            node_id, path.stem, degree=0,
            pixmap=pixmap, is_attachment=True,
        )
        if node:
            node.setPos(pos)

    def start_timelapse(self, node_ids):
        self._timelapse_queue = list(node_ids)
        self._timelapse_timer.start()

    def stop_timelapse(self):
        self._timelapse_timer.stop()
        self._timelapse_queue.clear()

    def _timelapse_step(self):
        if not self._timelapse_queue:
            self._timelapse_timer.stop()
            return
        nid = self._timelapse_queue.pop(0)
        node = self.nodes.get(nid)
        if node:
            node.setOpacity(1.0)


# ══════════════════════════════════════════════════════════════════════════
# Graph builder — 24 construction methods
# ══════════════════════════════════════════════════════════════════════════

class GraphBuilder:
    @staticmethod
    def full_vault(vault, backlinks):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        edges = []
        for src, tgt in backlinks.all_edges():
            resolved = GraphBuilder._resolve(tgt, notes)
            if resolved:
                edges.append((src, resolved))
        return notes, edges

    @staticmethod
    def local_graph(vault, backlinks, note_rel, depth=1):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        visited = {note_rel}
        frontier = {note_rel}
        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                for src, tgt in backlinks.all_edges():
                    if src == n:
                        r = GraphBuilder._resolve(tgt, notes)
                        if r and r not in visited:
                            next_frontier.add(r)
                    elif tgt == n:
                        if src not in visited:
                            next_frontier.add(src)
            visited |= next_frontier
            frontier = next_frontier
        paths = [p for p in notes if p in visited]
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in visited and GraphBuilder._resolve(t, notes) in visited]
        return paths, edges

    @staticmethod
    def by_tag(vault, tag_index, tag):
        files = tag_index.files_for_tag(tag)
        paths = [f for f in files if vault.abs_path(f).exists()]
        return paths, []

    @staticmethod
    def by_tags_all(vault, tag_index, tags):
        if not tags:
            return [], []
        sets = [set(tag_index.files_for_tag(t)) for t in tags]
        common = set.intersection(*sets) if sets else set()
        paths = [f for f in common if vault.abs_path(f).exists()]
        return paths, []

    @staticmethod
    def by_folder(vault, folder_rel):
        folder = vault.vault_path / folder_rel
        paths = [vault.rel_path(p) for p in folder.rglob("*.md")]
        return paths, []

    @staticmethod
    def orphans(vault, backlinks):
        all_notes = {vault.rel_path(p) for p in vault.list_notes()}
        linked = set()
        for s, t in backlinks.all_edges():
            linked.add(s)
            r = GraphBuilder._resolve(t, all_notes)
            if r:
                linked.add(r)
        paths = [p for p in all_notes if p not in linked]
        return paths, []

    @staticmethod
    def most_connected(vault, backlinks, top_n=30):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        degree = defaultdict(int)
        for s, t in backlinks.all_edges():
            degree[s] += 1
            r = GraphBuilder._resolve(t, notes)
            if r:
                degree[r] += 1
        top = sorted(degree.items(), key=lambda kv: -kv[1])[:top_n]
        top_set = {n for n, _ in top}
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in top_set and GraphBuilder._resolve(t, notes) in top_set]
        return list(top_set), edges

    @staticmethod
    def pagerank(vault, backlinks, top_n=30, damping=0.85, iters=20):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        if not notes:
            return [], []
        n = len(notes)
        rank = {p: 1.0 / n for p in notes}
        adj = defaultdict(list)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                adj[s].append(r)
        for _ in range(iters):
            new = {p: (1 - damping) / n for p in notes}
            for p in notes:
                out = adj.get(p, [])
                if not out:
                    continue
                share = rank[p] * damping / len(out)
                for q in out:
                    new[q] += share
            rank = new
        top = sorted(rank.items(), key=lambda kv: -kv[1])[:top_n]
        top_set = {n for n, _ in top}
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in top_set and GraphBuilder._resolve(t, notes) in top_set]
        return list(top_set), edges

    @staticmethod
    def by_search(vault, search_index, query):
        results = search_index.search(query, limit=100)
        paths = [r["path"] for r in results]
        return paths, []

    @staticmethod
    def by_date_range(vault, from_ts, to_ts):
        paths = []
        for p in vault.list_notes():
            try:
                mtime = p.stat().st_mtime
                if from_ts <= mtime <= to_ts:
                    paths.append(vault.rel_path(p))
            except OSError:
                continue
        return paths, []

    @staticmethod
    def recently_modified(vault, top_n=30):
        items = []
        for p in vault.list_notes():
            try:
                items.append((p.stat().st_mtime, vault.rel_path(p)))
            except OSError:
                continue
        items.sort(reverse=True)
        return [r for _, r in items[:top_n]], []

    @staticmethod
    def unresolved(vault, backlinks):
        notes = {vault.rel_path(p) for p in vault.list_notes()}
        stubs = {}
        edges = []
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if not r:
                stub_id = f"__stub__{t}"
                stubs[stub_id] = t
                edges.append((s, stub_id))
        return list(stubs.keys()) + list(notes), edges

    @staticmethod
    def attachments_only(vault, backlinks):
        attachment_exts = set(ImageErrorHandler.supported_formats())
        atts = {}
        for p in vault.vault_path.rglob("*"):
            if p.is_file() and p.suffix.lower().lstrip(".") in attachment_exts:
                atts[vault.rel_path(p)] = p
        return list(atts.keys()), []

    @staticmethod
    def random_sample(vault, backlinks, size=50):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        sample = set(random.sample(notes, min(size, len(notes))))
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in sample and GraphBuilder._resolve(t, notes) in sample]
        return list(sample), edges

    @staticmethod
    def shortest_path(vault, backlinks, start, end):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        adj = defaultdict(list)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                adj[s].append(r)
                adj[r].append(s)
        if start not in adj or end not in adj:
            return [start, end], []
        prev = {start: None}
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur == end:
                break
            for nb in adj[cur]:
                if nb not in prev:
                    prev[nb] = cur
                    q.append(nb)
        if end not in prev:
            return [start, end], []
        path = []
        cur = end
        while cur is not None:
            path.append(cur)
            cur = prev[cur]
        path.reverse()
        edges = [(path[i], path[i + 1]) for i in range(len(path) - 1)]
        return path, edges

    @staticmethod
    def communities(vault, backlinks, top_n=50):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        labels = {n: i for i, n in enumerate(notes)}
        adj = defaultdict(list)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                adj[s].append(r)
                adj[r].append(s)
        for _ in range(10):
            changed = False
            for n in notes:
                if not adj[n]:
                    continue
                counts = defaultdict(int)
                for nb in adj[n]:
                    counts[labels[nb]] += 1
                if counts:
                    best = max(counts, key=counts.get)
                    if labels[n] != best:
                        labels[n] = best
                        changed = True
            if not changed:
                break
        groups = defaultdict(list)
        for n, lbl in labels.items():
            groups[lbl].append(n)
        top_groups = sorted(groups.values(), key=len, reverse=True)[:top_n]
        flat = [n for g in top_groups for n in g]
        flat_set = set(flat)
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in flat_set and GraphBuilder._resolve(t, notes) in flat_set]
        return flat, edges

    @staticmethod
    def similar_to(vault, backlinks, note_rel, top_n=20):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        targets = set()
        for s, t in backlinks.all_edges():
            if s == note_rel:
                r = GraphBuilder._resolve(t, notes)
                if r:
                    targets.add(r)
        scores = defaultdict(int)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r and r in targets and s != note_rel:
                scores[s] += 1
        top = sorted(scores.items(), key=lambda kv: -kv[1])[:top_n]
        result = {note_rel} | {n for n, _ in top}
        edges = [(s, t) for s, t in backlinks.all_edges()
                 if s in result and GraphBuilder._resolve(t, notes) in result]
        return list(result), edges

    @staticmethod
    def by_property(vault, backlinks, key, value=None):
        paths = []
        for p in vault.list_notes():
            try:
                content = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if content.startswith("---"):
                end = content.find("\n---", 3)
                if end > 0:
                    fm = content[3:end]
                    for line in fm.splitlines():
                        if ":" in line:
                            k, _, v = line.partition(":")
                            if k.strip() == key:
                                if value is None or value.lower() in v.lower():
                                    paths.append(vault.rel_path(p))
                                    break
        return paths, []

    @staticmethod
    def by_word_count(vault, min_words=500):
        paths = []
        for p in vault.list_notes():
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if len(text.split()) >= min_words:
                paths.append(vault.rel_path(p))
        return paths, []

    @staticmethod
    def by_creation(vault, top_n=50):
        items = []
        for p in vault.list_notes():
            try:
                st = p.stat()
                items.append((min(st.st_ctime, st.st_mtime),
                              vault.rel_path(p)))
            except OSError:
                continue
        items.sort()
        return [r for _, r in items[:top_n]], []

    @staticmethod
    def bidirectional(vault, backlinks):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        edge_set = set()
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                edge_set.add((s, r))
        mutual = []
        for s, t in edge_set:
            if (t, s) in edge_set and s < t:
                mutual.append((s, t))
        nodes = set()
        for s, t in mutual:
            nodes.add(s)
            nodes.add(t)
        return list(nodes), mutual

    @staticmethod
    def by_tag_cooccurrence(vault, tag_index, min_shared=2):
        tag_files = defaultdict(set)
        for tag, _count in tag_index.all_tags():
            for f in tag_index.files_for_tag(tag):
                tag_files[tag].add(f)
        edges = []
        files = set()
        tags = list(tag_files.keys())
        for i, t1 in enumerate(tags):
            for t2 in tags[i + 1:]:
                shared = tag_files[t1] & tag_files[t2]
                if len(shared) >= min_shared:
                    fl = list(shared)
                    files |= shared
                    for j in range(len(fl)):
                        for k in range(j + 1, len(fl)):
                            edges.append((fl[j], fl[k]))
        return list(files), edges

    @staticmethod
    def by_link_distance(vault, backlinks, seeds, max_distance=2):
        notes = [vault.rel_path(p) for p in vault.list_notes()]
        adj = defaultdict(set)
        for s, t in backlinks.all_edges():
            r = GraphBuilder._resolve(t, notes)
            if r:
                adj[s].add(r)
                adj[r].add(s)
        visited = set(seeds)
        frontier = set(seeds)
        for _ in range(max_distance):
            nf = set()
            for n in frontier:
                nf |= adj[n] - visited
            visited |= nf
            frontier = nf
        edges = []
        for s in visited:
            for t in adj[s]:
                if t in visited and s < t:
                    edges.append((s, t))
        return list(visited), edges

    @staticmethod
    def custom(vault, predicate, backlinks=None):
        paths = []
        for p in vault.list_notes():
            rel = vault.rel_path(p)
            try:
                if predicate(rel, p):
                    paths.append(rel)
            except Exception:
                continue
        edges = []
        if backlinks:
            notes_set = set(paths)
            for s, t in backlinks.all_edges():
                r = GraphBuilder._resolve(t, paths)
                if s in notes_set and r in notes_set:
                    edges.append((s, r))
        return paths, edges

    @staticmethod
    def _resolve(target, known_paths):
        target = target.strip()
        stem = Path(target).stem.lower()
        for p in known_paths:
            if p == target or p == target + ".md":
                return p
            if Path(p).stem.lower() == stem:
                return p
        return None


# ══════════════════════════════════════════════════════════════════════════
# Graph widget
# ══════════════════════════════════════════════════════════════════════════

def _button_style():
    return (
        "QPushButton { background: #333; color: #ddd; border: none; "
        "padding: 4px 14px; border-radius: 4px; font-size: 12px; }"
        "QPushButton:hover { background: #444; }"
    )


def _combo_style():
    return (
        "QComboBox { background: #333; color: #ddd; border: 1px solid #555; "
        "padding: 3px 8px; border-radius: 4px; font-size: 11px; }"
        "QComboBox::drop-down { border: none; }"
    )


def _slider_style():
    return (
        "QSlider::groove:horizontal { background: #444; height: 4px; "
        "border-radius: 2px; }"
        "QSlider::handle:horizontal { background: #6f42c1; width: 12px; "
        "margin: -5px 0; border-radius: 6px; }"
    )


def _line_style():
    return (
        "QLineEdit { background: #333; color: #ddd; border: 1px solid #555; "
        "padding: 4px 8px; border-radius: 4px; font-size: 11px; }"
    )


def _check_style():
    return "QCheckBox { color: #ccc; font-size: 11px; }"


class GraphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._errors = _DEFAULT_ROUTER
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._build_toolbar(layout)
        self.view = ForceGraphView(self)
        layout.addWidget(self.view, 1)

    def _build_toolbar(self, layout):
        bar = QWidget()
        bar.setStyleSheet("background: #252526; border-bottom: 1px solid #333;")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(10, 6, 10, 6)
        bar_layout.setSpacing(8)

        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Global", "Local", "Tags", "Orphans",
            "Most Connected", "PageRank", "Communities",
        ])
        self.type_combo.setStyleSheet(_combo_style())
        bar_layout.addWidget(QLabel("Type:"))
        bar_layout.addWidget(self.type_combo)

        self.depth_slider = QSlider(Qt.Orientation.Horizontal)
        self.depth_slider.setRange(1, 5)
        self.depth_slider.setValue(1)
        self.depth_slider.setFixedWidth(80)
        self.depth_slider.setStyleSheet(_slider_style())
        bar_layout.addWidget(QLabel("Depth:"))
        bar_layout.addWidget(self.depth_slider)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter…")
        self.search_box.setStyleSheet(_line_style())
        self.search_box.setFixedWidth(150)
        bar_layout.addWidget(self.search_box)

        self.orphans_cb = QCheckBox("Orphans")
        self.orphans_cb.setChecked(True)
        self.orphans_cb.setStyleSheet(_check_style())
        bar_layout.addWidget(self.orphans_cb)

        self.arrows_cb = QCheckBox("Arrows")
        self.arrows_cb.setStyleSheet(_check_style())
        bar_layout.addWidget(self.arrows_cb)

        bar_layout.addWidget(QLabel("Repel:"))
        self.repel_slider = QSlider(Qt.Orientation.Horizontal)
        self.repel_slider.setRange(1, 100)
        self.repel_slider.setValue(50)
        self.repel_slider.setFixedWidth(70)
        self.repel_slider.setStyleSheet(_slider_style())
        bar_layout.addWidget(self.repel_slider)

        bar_layout.addWidget(QLabel("Link:"))
        self.link_slider = QSlider(Qt.Orientation.Horizontal)
        self.link_slider.setRange(1, 100)
        self.link_slider.setValue(50)
        self.link_slider.setFixedWidth(70)
        self.link_slider.setStyleSheet(_slider_style())
        bar_layout.addWidget(self.link_slider)

        bar_layout.addStretch()

        self.info_label = QLabel("0 nodes, 0 edges")
        self.info_label.setStyleSheet("color: #999; font-size: 11px;")
        bar_layout.addWidget(self.info_label)

        fit_btn = QPushButton("Fit")
        fit_btn.setStyleSheet(_button_style())
        fit_btn.clicked.connect(self.fit)
        bar_layout.addWidget(fit_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.setStyleSheet(_button_style())
        reset_btn.clicked.connect(self._reset)
        bar_layout.addWidget(reset_btn)

        layout.addWidget(bar)

        self._errors.ui.safe_connect(
            self.search_box.textChanged, self._on_search,
            context="search_changed",
        )
        self._errors.ui.safe_connect(
            self.orphans_cb.stateChanged, self._on_orphans,
            context="orphans_toggled",
        )
        self._errors.ui.safe_connect(
            self.arrows_cb.stateChanged, self._on_arrows,
            context="arrows_toggled",
        )
        self._errors.ui.safe_connect(
            self.repel_slider.valueChanged, self._on_repel,
            context="repel_changed",
        )
        self._errors.ui.safe_connect(
            self.link_slider.valueChanged, self._on_link,
            context="link_changed",
        )

    def load_graph(self, note_paths, edges, rel_types=None):
        self.view.build(note_paths, edges)
        if rel_types:
            for i, (s, t) in enumerate(edges):
                if i < len(self.view.edges):
                    self.view.edges[i].rel_type = rel_types[i]
                    self.view.edges[i].setPen(
                        QPen(RelationType.color(rel_types[i]),
                             self.view.config.link_base_width)
                    )
        self._update_info()

    def fit(self):
        if self.view.nodes:
            rect = self.view.scene.itemsBoundingRect()
            if rect.width() > 0 and rect.height() > 0:
                self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

    def _reset(self):
        self.view.resetTransform()
        self.fit()

    def _update_info(self):
        n = len(self.view.nodes)
        e = len(self.view.edges)
        self.info_label.setText(f"{n} nodes, {e} edges")

    def _on_search(self, text):
        self.view.filter.search_query = text
        self._apply_filter()

    def _on_orphans(self, state):
        self.view.filter.show_orphans = bool(state)
        self._apply_filter()

    def _on_arrows(self, state):
        self.view.config.show_arrows = bool(state)
        for edge in self.view.edges:
            edge.set_show_arrows(bool(state))

    def _on_repel(self, value):
        self.view.config.repulsion = 2000.0 + (value / 100.0) * 28000.0

    def _on_link(self, value):
        self.view.config.spring_length = 40.0 + (value / 100.0) * 260.0

    def _apply_filter(self):
        f = self.view.filter
        for node in self.view.nodes.values():
            visible = f.matches(
                node.node_id, node.label, node._degree,
                tags=node._tags,
            )
            node.setVisible(visible)
        for edge in self.view.edges:
            edge.setVisible(
                edge.source.isVisible() and edge.target.isVisible()
            )
        self._update_info()


__all__ = [
    "GraphNode", "GraphEdge", "ForceGraphView", "GraphWidget",
    "GraphBuilder", "GraphConfig", "GraphFilter", "NodeGroup",
    "RelationType", "BarnesHutTree", "ErrorRouter",
    "GraphErrorHandler", "ImageErrorHandler", "LayoutErrorHandler",
    "GraphUIErrorHandler", "default_router",
]