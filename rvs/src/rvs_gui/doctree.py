"""Document tree: documents nested by their parent document, items listed under their document."""

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTreeView

from rvs_gui.session import ProjectSession
from rvs_gui.widgets import keyboard_view, named

ROLE_KIND = Qt.ItemDataRole.UserRole + 1  # "all" | "doc" | "item"
ROLE_KEY = Qt.ItemDataRole.UserRole + 2  # prefix or uid


class DocumentTree(QTreeView):
    document_selected = Signal(object)  # prefix or None (= all documents)
    item_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        keyboard_view(self)
        named(self, "Documents and items")
        self.setHeaderHidden(True)
        self._syncing = False
        self.selectionModel().currentChanged.connect(self._on_current)  # once: populate() runs after every refresh
        self._doc_nodes: dict[str, QStandardItem] = {}
        self._item_nodes: dict[str, QStandardItem] = {}

    def populate(self, session: ProjectSession) -> None:
        assert session.cfg is not None
        self._model.clear()
        self._doc_nodes.clear()
        self._item_nodes.clear()
        all_node = self._node("All items", "all", "")
        self._model.appendRow(all_node)
        decls = list(session.cfg.project.documents)
        by_parent: dict[str | None, list[str]] = {}
        for d in decls:
            by_parent.setdefault(d.parent, []).append(d.prefix)
        titles = {d.prefix: d.title for d in decls}

        def add_doc(prefix: str, parent_node: QStandardItem | None) -> None:
            node = self._node(f"{prefix}  {titles[prefix]}", "doc", prefix)
            (parent_node.appendRow(node) if parent_node else self._model.appendRow(node))
            self._doc_nodes[prefix] = node
            for child_prefix in by_parent.get(prefix, []):
                add_doc(child_prefix, node)
            for item in (i for i in session.items if i.document == prefix):
                label = f"{item.uid}  {item.attrs.get('title') or item.header}"
                child = self._node(label, "item", item.uid)
                node.appendRow(child)
                self._item_nodes[item.uid] = child

        for root_prefix in by_parent.get(None, []):
            add_doc(root_prefix, None)
        self.expandToDepth(0)

    @staticmethod
    def _node(label: str, kind: str, key: str) -> QStandardItem:
        node = QStandardItem(label)
        node.setEditable(False)
        node.setData(kind, ROLE_KIND)
        node.setData(key, ROLE_KEY)
        return node

    # queries ################################################################
    def document_prefixes(self) -> list[str]:
        order: list[str] = []

        def walk(node: QStandardItem) -> None:
            for r in range(node.rowCount()):
                child = node.child(r)
                if child.data(ROLE_KIND) == "doc":
                    order.append(child.data(ROLE_KEY))
                    walk(child)

        walk(self._model.invisibleRootItem())
        return order

    def item_uids(self, prefix: str) -> list[str]:
        node = self._doc_nodes[prefix]
        return [node.child(r).data(ROLE_KEY) for r in range(node.rowCount()) if node.child(r).data(ROLE_KIND) == "item"]

    # selection ##############################################################
    def _on_current(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if self._syncing or not current.isValid():
            return
        kind, key = current.data(ROLE_KIND), current.data(ROLE_KEY)
        if kind == "item":
            self.item_selected.emit(key)
        else:
            self.document_selected.emit(key or None)

    def select_document(self, prefix: str | None) -> None:
        node = self._doc_nodes.get(prefix) if prefix else self._model.item(0)
        if node is not None:
            self.setCurrentIndex(node.index())

    def select_item(self, uid: str) -> None:
        node = self._item_nodes.get(uid)
        if node is not None:
            self.setCurrentIndex(node.index())

    def show_item(self, uid: str) -> None:
        """Highlight ``uid`` (expanding its document) without emitting selection signals."""
        node = self._item_nodes.get(uid)
        if node is None:
            return
        ancestor = node.parent()
        while ancestor is not None:
            self.expand(ancestor.index())
            ancestor = ancestor.parent()
        self._syncing = True
        try:
            self.setCurrentIndex(node.index())
            self.scrollTo(node.index())
        finally:
            self._syncing = False
