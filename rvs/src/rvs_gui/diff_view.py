"""Diff tab: two baselines, or a baseline and the working copy, with changed words marked."""

import html
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableView,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from rvs_core.changecontrol.baselines import list_baselines
from rvs_core.changecontrol.diff import (
    WORKING,
    DiffResult,
    ItemChange,
    diff_doc,
    diff_snapshots,
    diff_table,
    load_snapshot,
)
from rvs_core.exporters import render_doc
from rvs_core.matrices import Provenance
from rvs_core.matrices.render import to_csv
from rvs_core.matrices.table import MatrixTable
from rvs_gui.jobs import run_in_background
from rvs_gui.matrix_views import MatrixTableModel
from rvs_gui.session import ProjectSession
from rvs_gui.theme import TOKENS

WORKING_LABEL = "Working copy"


def _ins() -> str:
    return f"color:{TOKENS['diff_ins']};text-decoration:underline;"


def _del() -> str:
    return f"color:{TOKENS['diff_del']};text-decoration:line-through;"


def _marked(segments: tuple[tuple[str, str], ...]) -> str:
    out = []
    for op, text in segments:
        esc = html.escape(text).replace("\n", "<br>")
        out.append(
            {"insert": f'<span style="{_ins()}">{esc}</span>', "delete": f'<span style="{_del()}">{esc}</span>'}.get(
                op, esc
            )
        )
    return "".join(out)


class DiffView(QWidget):
    message = Signal(str, str)
    diff_ready = Signal()
    export_done = Signal(str, str)

    def __init__(self, session: ProjectSession) -> None:
        super().__init__()
        self.session = session
        self.diff: DiffResult | None = None
        self.left, self.right, self.document = QComboBox(), QComboBox(), QComboBox()
        self.compare_button = QPushButton("Compare")
        self.export_button = QPushButton("Export…")
        self._generation = 0
        self.summary = QLabel("Choose two versions and press Compare.")
        self.model = MatrixTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.detail = QTextBrowser()
        self.detail.setOpenLinks(False)
        top = QHBoxLayout()
        for label, widget in (("From", self.left), ("To", self.right), ("Document", self.document)):
            top.addWidget(QLabel(label))
            top.addWidget(widget)
        top.addWidget(self.compare_button)
        top.addWidget(self.export_button)
        top.addStretch(1)
        split = QSplitter()
        split.addWidget(self.table)
        split.addWidget(self.detail)
        split.setStretchFactor(1, 2)
        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.summary)
        lay.addWidget(split, 1)
        self.compare_button.clicked.connect(self.compare)
        self.export_button.clicked.connect(self._choose_export)
        self.document.currentTextChanged.connect(lambda _t: self._show_table())
        self.table.selectionModel().currentRowChanged.connect(lambda *_a: self._show_detail())
        session.loaded.connect(self.refresh_choices)

    # choices ###################################################################
    def refresh_choices(self) -> None:
        if self.session.root is None or self.session.cfg is None:
            return
        try:
            names = [b.name for b in list_baselines(self.session.root)]
        except Exception:  # noqa: BLE001 - choices stay as they are
            return
        choices = [*names, WORKING_LABEL]
        for combo in (self.left, self.right):
            current = combo.currentText()
            if [combo.itemText(i) for i in range(combo.count())] != choices:
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(choices)
                combo.blockSignals(False)
                if current in choices:
                    combo.setCurrentText(current)
        if not self.left.currentText() or self.left.currentText() == WORKING_LABEL:
            self.left.setCurrentIndex(max(0, len(names) - 1)) if names else None
        self.right.setCurrentText(self.right.currentText() or WORKING_LABEL)
        docs = ["All documents", *[d.prefix for d in self.session.cfg.project.documents]]
        if [self.document.itemText(i) for i in range(self.document.count())] != docs:
            self.document.blockSignals(True)
            self.document.clear()
            self.document.addItems(docs)
            self.document.blockSignals(False)

    def set_range(self, left: str, right: str | None) -> None:
        self.refresh_choices()
        self.left.setCurrentText(left)
        self.right.setCurrentText(right or WORKING_LABEL)

    # comparing ####################################################################
    @staticmethod
    def _ref(text: str) -> str | None:
        return None if text in (WORKING_LABEL, WORKING, "") else text

    def compare(self) -> None:
        root = self.session.root
        if root is None:
            self.message.emit("info", "Open a project first.")
            return
        left, right = self._ref(self.left.currentText()), self._ref(self.right.currentText())
        self.summary.setText("Comparing …")
        self._generation += 1
        generation = self._generation  # a result that arrives after a newer request was made is discarded

        def work() -> DiffResult:
            return diff_snapshots(load_snapshot(root, left), load_snapshot(root, right))

        def done(result: DiffResult) -> None:
            if generation != self._generation:
                return
            self.diff = result
            self._show_table()
            self.diff_ready.emit()

        def failed(exc: Exception) -> None:
            if generation != self._generation:
                return
            self.summary.setText("The comparison failed.")
            self.message.emit("error", f"The comparison failed: {exc}")

        run_in_background(work, done, failed)

    def restyle(self) -> None:
        """Re-render the shown comparison with the colours of the current theme (the word marking is baked into HTML)."""
        if self.diff is not None:
            row = self.table.currentIndex().row()
            self._show_table()
            if row > 0:
                self.select_row(row)

    def _filtered(self) -> tuple[ItemChange, ...]:
        assert self.diff is not None
        if self.document.currentIndex() <= 0:
            return self.diff.changes
        return self.diff.for_document(self.document.currentText())

    def _show_table(self) -> None:
        if self.diff is None or self.session.cfg is None:
            return
        shown = DiffResult(self.diff.left, self.diff.right, self._filtered())
        table: MatrixTable = diff_table(shown, Provenance.now(self.session.cfg, user=self.session.user))
        self.model.set_matrix(table)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        d = self.diff
        self.summary.setText(f"{d.left} → {d.right}: {d.added} added, {d.removed} removed, {d.changed} changed")
        self.detail.setHtml("")
        if shown.changes:
            self.select_row(0)

    def select_row(self, row: int) -> None:
        self.table.selectRow(row)
        self._show_detail()

    def show_item(self, uid: str) -> None:
        for r in range(self.model.rowCount()):
            if self.model.index(r, 0).data() == uid:
                self.select_row(r)
                return

    def _show_detail(self) -> None:
        idx = self.table.currentIndex()
        if self.diff is None or not idx.isValid():
            return
        uid = str(self.model.index(idx.row(), 0).data())
        change = self.diff.for_item(uid)
        if change is None:
            return
        parts = [f"<h3>{html.escape(change.uid)} — {html.escape(change.title)} <small>({change.kind})</small></h3>"]
        if change.kind == "changed":
            for f in change.fields:
                parts.append(f"<p><b>{html.escape(f.name)}</b><br>{_marked(f.segments)}</p>")
        else:
            item = change.after or change.before
            assert item is not None
            op = "insert" if change.kind == "added" else "delete"
            parts.append(f"<p>{_marked(((op, item.text.strip()),))}</p>")
            for name, value in sorted(item.attrs.items()):
                if value not in (None, "", []) and name != "rvs_schema_version":
                    parts.append(f"<p><b>{html.escape(name)}:</b> {html.escape(str(value))}</p>")
        self.detail.setHtml("".join(parts))

    # export ########################################################################
    def _choose_export(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Export changes", "", "HTML (*.html);;Word (*.docx);;PDF (*.pdf);;CSV (*.csv)"
        )
        if path:
            self.export_file(Path(path))

    def export_file(self, path: Path) -> None:
        if self.diff is None or self.session.cfg is None:
            self.message.emit("info", "Compare two versions first.")
            return
        fmt = path.suffix.lstrip(".").lower()
        if fmt not in ("html", "docx", "pdf", "csv"):
            self.message.emit("error", f"'.{fmt}' is not a supported format. Use html, docx, pdf or csv.")
            return
        shown = DiffResult(self.diff.left, self.diff.right, self._filtered())
        prov = Provenance.now(self.session.cfg, user=self.session.user, baseline=f"{shown.left} → {shown.right}")

        def work() -> int:
            data = (
                to_csv(diff_table(shown, prov)).encode("utf-8")
                if fmt == "csv"
                else render_doc(diff_doc(shown, prov), fmt)
            )
            path.write_bytes(data)
            return len(shown.changes)

        def done(count: int) -> None:
            self.message.emit("success", f"Exported {count} changes to {path}.")
            self.export_done.emit(str(path), "")

        def failed(exc: Exception) -> None:
            text = (
                f"The file {path} could not be written: {exc.strerror}. Choose another location."
                if isinstance(exc, OSError)
                else f"The export failed: {exc}"
            )
            self.message.emit("error", text)
            self.export_done.emit(str(path), text)

        run_in_background(work, done, failed)
