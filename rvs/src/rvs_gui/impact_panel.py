"""Impact dock: what a change to the selected item would affect, as a tree and as a list."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QLabel,
    QTableView,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rvs_core.matrices import Provenance, impact_table
from rvs_core.trace import ImpactNode, impact
from rvs_gui.matrix_views import MatrixTableModel
from rvs_gui.session import ProjectSession


class ImpactPanel(QDockWidget):
    item_requested = Signal(str)

    def __init__(self, session: ProjectSession) -> None:
        super().__init__("Impact")
        self.setObjectName("ImpactPanel")
        self.session = session
        self.uid: str | None = None
        self.summary = QLabel("Select an item to see what a change to it would affect.")
        self.summary.setWordWrap(True)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Item", "Via", "Title"])
        self.list_model = MatrixTableModel(self)
        self.list_view = QTableView()
        self.list_view.setModel(self.list_model)
        self.list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.list_view.verticalHeader().hide()
        tabs = QTabWidget()
        tabs.addTab(self.tree, "Tree")
        tabs.addTab(self.list_view, "List")
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.addWidget(self.summary)
        lay.addWidget(tabs, 1)
        self.setWidget(body)
        self.tree.itemDoubleClicked.connect(lambda item, _c: self.item_requested.emit(item.text(0)))
        self.list_view.doubleClicked.connect(lambda idx: self.item_requested.emit(str(idx.siblingAtColumn(0).data())))
        session.loaded.connect(self._reload)

    def _reload(self) -> None:
        if self.uid:
            self.set_item(self.uid)

    def set_item(self, uid: str) -> None:
        self.uid = uid
        graph, cfg = self.session.graph, self.session.cfg
        self.tree.clear()
        if graph is None or cfg is None or uid not in graph.uids:
            self.list_model.set_matrix(None)
            return
        result = impact(graph, uid)
        titles = {i.uid: str(i.attrs.get("title") or i.header or "") for i in self.session.items}

        def add(parent: QTreeWidgetItem | QTreeWidget, node: ImpactNode) -> None:
            row = QTreeWidgetItem([node.uid, node.via, titles.get(node.uid, "")])
            if isinstance(parent, QTreeWidget):
                parent.addTopLevelItem(row)
            else:
                parent.addChild(row)
            for child in node.children:
                add(row, child)

        for child in result.root.children:
            add(self.tree, child)
        self.tree.expandAll()
        self.list_model.set_matrix(
            impact_table(self.session.items, result, Provenance.now(cfg, user=self.session.user))
        )
        n = result.count
        text = f"{n} item{'s' if n != 1 else ''} affected by a change to {uid}"
        if result.related:
            text += f" (also review, conflicts-with: {', '.join(result.related)})"
        self.summary.setText(text)

    def clear(self) -> None:
        self.tree.clear()
        self.summary.setText("Select an item to see what a change to it would affect.")
        self.list_model.set_matrix(None)
        self.uid = None
        _ = Qt  # keep the import used for future flags
