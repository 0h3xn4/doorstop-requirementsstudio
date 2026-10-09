"""Graph tab: an item and its neighbourhood, drawn in layers (upstream above, downstream below)."""

from collections.abc import Callable

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF, QResizeEvent
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rvs_core.trace import neighbourhood
from rvs_gui.graph_layout import layout
from rvs_gui.session import ProjectSession
from rvs_gui.theme import TOKENS

NODE_W, NODE_H = 170.0, 54.0
_EDGE_COLOR = {
    "parent": "#525252",
    "verifies": "#24a148",
    "satisfies": "#0f62fe",
    "refines": "#8a3ffc",
    "conflicts-with": "#da1e28",
}


class NodeItem(QGraphicsRectItem):
    def __init__(self, uid: str, title: str, centre: bool, view: "GraphView") -> None:
        super().__init__(QRectF(-NODE_W / 2, -NODE_H / 2, NODE_W, NODE_H))
        self.uid, self._view = uid, view
        self.setBrush(QBrush(QColor(TOKENS["layer"] if not centre else "#d0e2ff")))
        self.setPen(QPen(QColor(TOKENS["interactive"] if centre else TOKENS["border_strong"]), 2 if centre else 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        head = QGraphicsSimpleTextItem(uid, self)
        head.setPos(-NODE_W / 2 + 8, -NODE_H / 2 + 6)
        body = QGraphicsSimpleTextItem(title if len(title) <= 24 else title[:23] + "…", self)
        body.setBrush(QBrush(QColor(TOKENS["text_secondary"])))
        body.setPos(-NODE_W / 2 + 8, -NODE_H / 2 + 28)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self._view.click_node(self.uid)
        event.accept()


class GraphView(QWidget):
    def __init__(self, session: ProjectSession) -> None:
        super().__init__()
        self.session = session
        self.uid: str | None = None
        self.on_node_clicked: Callable[[str], object] = lambda uid: None  # replaced by the main window
        self.depth_box = QSpinBox()
        self.depth_box.setRange(1, 4)
        self.depth_box.setValue(1)
        self.depth_box.valueChanged.connect(lambda _v: self.refresh())
        self.hint = QLabel("Select an item. Upstream items are above it, downstream items (children, verifiers) below.")
        self.scene_ = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene_)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = QHBoxLayout()
        top.addWidget(QLabel("Depth"))
        top.addWidget(self.depth_box)
        top.addWidget(self.hint, 1)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.view, 1)
        session.loaded.connect(self.refresh)

    def show_item(self, uid: str) -> None:
        self.uid = uid
        self.refresh()

    def refresh(self) -> None:
        self.scene_.clear()
        graph = self.session.graph
        if graph is None or self.uid is None:
            return
        n = neighbourhood(graph, self.uid, self.depth_box.value())
        pos = layout(n)
        titles = {i.uid: str(i.attrs.get("title") or i.header or "") for i in self.session.items}
        for e in n.edges:
            self._draw_edge(pos[e.source], pos[e.target], e.type)
        for node in n.nodes:
            item = NodeItem(node.uid, titles.get(node.uid, ""), node.uid == self.uid, self)
            item.setPos(*pos[node.uid])
            item.setZValue(1)
            self.scene_.addItem(item)
        self.scene_.setSceneRect(self.scene_.itemsBoundingRect().adjusted(-40, -40, 40, 40))
        self._fit()

    def _fit(self) -> None:
        rect = self.scene_.sceneRect()
        if rect.isValid() and not rect.isEmpty():
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            if self.view.transform().m11() > 1.0:  # never magnify small graphs
                self.view.resetTransform()
                self.view.centerOn(rect.center())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit()

    def _draw_edge(self, a: tuple[float, float], b: tuple[float, float], kind: str) -> None:
        pen = QPen(QColor(_EDGE_COLOR.get(kind, "#525252")), 1.5)
        start, end = QPointF(*a), QPointF(*b)
        line = QLineF(start, end)
        if line.length() == 0:
            return
        # shorten to the node borders so the arrow head is visible
        unit = QPointF(line.dx() / line.length(), line.dy() / line.length())
        end = end - QPointF(unit.x() * NODE_W / 2 * abs(unit.x()) + unit.x() * 0, unit.y() * NODE_H / 2)
        item = self.scene_.addLine(QLineF(start, end), pen)
        item.setData(0, kind)
        head = QPolygonF([end, end - QPointF(unit.x() * 12 + unit.y() * 6, unit.y() * 12 - unit.x() * 6),
                          end - QPointF(unit.x() * 12 - unit.y() * 6, unit.y() * 12 + unit.x() * 6)])  # fmt: skip
        self.scene_.addPolygon(head, pen, QBrush(pen.color())).setData(0, "arrow")
        label = self.scene_.addSimpleText(kind)
        label.setBrush(QBrush(pen.color()))
        label.setPos((start.x() + end.x()) / 2 + 4, (start.y() + end.y()) / 2 - 8)

    # introspection (used by tests) and interaction ###############################
    def node_uids(self) -> list[str]:
        return [i.uid for i in self.scene_.items() if isinstance(i, NodeItem)]

    def edge_count(self) -> int:
        return sum(1 for i in self.scene_.items() if i.data(0) not in (None, "arrow"))

    def click_node(self, uid: str) -> None:
        self.on_node_clicked(uid)
