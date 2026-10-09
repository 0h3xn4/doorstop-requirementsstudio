"""Matrix tabs: a model that renders a MatrixTable, and the traceability, VCM and coverage views."""

from pathlib import Path
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rvs_core.exporters import TABLE_FORMATS, render_table
from rvs_core.matrices import (
    MatrixTable,
    Provenance,
    VcmFilter,
    build_traceability,
    build_vcm,
    coverage_table,
)
from rvs_core.matrices.render import to_csv
from rvs_core.trace import coverage
from rvs_gui.jobs import run_in_background
from rvs_gui.models import Index
from rvs_gui.session import ProjectSession
from rvs_gui.theme import TOKENS

_GAP_COLOR = {"unverified-approved": "#ffd7d9", "unverified": "#fcf4d6", "childless": "#fcf4d6", "orphan": "#ffd7d9"}


class MatrixTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.matrix: MatrixTable | None = None

    def set_matrix(self, matrix: MatrixTable | None) -> None:
        self.beginResetModel()
        self.matrix = matrix
        self.endResetModel()

    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() or self.matrix is None else len(self.matrix.rows)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() or self.matrix is None else len(self.matrix.columns)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if self.matrix and orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.matrix.columns[section]
        return None

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or self.matrix is None:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return self.matrix.rows[index.row()][index.column()]
        flag = self.matrix.flags[index.row()]
        if role == Qt.ItemDataRole.BackgroundRole and flag:
            return QBrush(QColor(_GAP_COLOR.get(flag, "#fcf4d6")))
        if role == Qt.ItemDataRole.ToolTipRole and flag:
            return f"Gap: {flag}"
        return None


class MatrixView(QWidget):
    """Title block (provenance, notes), a table and an export button. Subclasses add filter controls."""

    message = Signal(str, str)
    export_done = Signal(str, str)  # (path, error message or '')

    def __init__(self, session: ProjectSession) -> None:
        super().__init__()
        self.session = session
        self.model = MatrixTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.provenance_label = QLabel()
        self.provenance_label.setStyleSheet(f"color: {TOKENS['text_secondary']};")
        self.notes_label = QLabel()
        self.notes_label.setWordWrap(True)
        self.export_button = QPushButton("Export…")
        self.export_button.clicked.connect(self._choose_export)
        self.controls = QHBoxLayout()
        self.controls.addStretch(1)
        self.controls.addWidget(self.export_button)
        lay = QVBoxLayout(self)
        lay.addLayout(self.controls)
        lay.addWidget(self.provenance_label)
        lay.addWidget(self.notes_label)
        lay.addWidget(self.table, 1)
        session.loaded.connect(self.refresh)

    @property
    def matrix(self) -> MatrixTable:
        assert self.model.matrix is not None
        return self.model.matrix

    def build(self) -> MatrixTable | None:  # pragma: no cover - overridden
        raise NotImplementedError

    def refresh(self) -> None:
        if self.session.cfg is None or self.session.graph is None:
            return
        try:
            matrix = self.build()
        except ValueError as exc:
            self.message.emit("error", str(exc))
            return
        self.model.set_matrix(matrix)
        if matrix is not None:
            self.provenance_label.setText("  ·  ".join(matrix.provenance.lines()))
            self.notes_label.setText(" ".join(matrix.notes))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def provenance(self) -> Provenance:
        assert self.session.cfg is not None
        return Provenance.now(self.session.cfg, user=self.session.user, baseline=self.session.baseline_label)

    def _choose_export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", "", "Excel (*.xlsx);;CSV (*.csv);;Word (*.docx);;PDF (*.pdf);;HTML (*.html);;JSON (*.json)"
        )
        if path:
            self.export_file(Path(path))

    def export_file(self, path: Path) -> None:
        """Write the table shown here to ``path``; the format follows the file extension. Runs in the background."""
        fmt = path.suffix.lstrip(".").lower()
        if fmt not in TABLE_FORMATS:
            self.message.emit("error", f"'.{fmt}' is not a supported format. Use one of: {', '.join(TABLE_FORMATS)}.")
            return
        table = self.matrix

        def work() -> int:
            path.write_bytes(render_table(table, fmt))
            return len(table.rows)

        def done(count: int) -> None:
            self.message.emit("success", f"Exported {count} rows to {path}.")
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

    def export_csv(self, path: Path) -> None:
        try:
            path.write_text(to_csv(self.matrix), encoding="utf-8", newline="\n")
        except OSError as exc:
            self.message.emit(
                "error", f"The file {path} could not be written: {exc.strerror}. Choose another location."
            )
            return
        self.message.emit("success", f"Exported {len(self.matrix.rows)} rows to {path}.")


def _combo(items: list[str], parent: QWidget | None = None) -> QComboBox:
    box = QComboBox(parent)
    box.addItems(items)
    return box


class TraceabilityView(MatrixView):
    def __init__(self, session: ProjectSession) -> None:
        super().__init__(session)
        self.source, self.target, self.direction = QComboBox(), QComboBox(), _combo(["down", "up"])
        self.controls.insertWidget(0, QLabel("From"))
        self.controls.insertWidget(1, self.source)
        self.controls.insertWidget(2, QLabel("to"))
        self.controls.insertWidget(3, self.target)
        self.controls.insertWidget(4, self.direction)
        self.direction.setToolTip("down: the items below each row; up: the items above each row")
        for box in (self.source, self.target, self.direction):
            box.currentTextChanged.connect(self._changed)
        self._filling = False
        session.loaded.connect(self._fill)

    def _fill(self) -> None:
        if self.session.cfg is None:
            return
        prefixes = [d.prefix for d in self.session.cfg.project.documents]
        if [self.source.itemText(i) for i in range(self.source.count())] == prefixes:
            return
        self._filling = True
        try:
            for box in (self.source, self.target):
                box.clear()
                box.addItems(prefixes)
            self.target.setCurrentIndex(1 if len(prefixes) > 1 else 0)
        finally:
            self._filling = False
        self.refresh()

    def _changed(self, *_a: object) -> None:
        if not self._filling:
            self.refresh()

    def build(self) -> MatrixTable | None:
        cfg, graph = self.session.cfg, self.session.graph
        assert cfg is not None and graph is not None
        if not self.source.currentText() or not self.target.currentText():
            return None
        return build_traceability(
            cfg, self.session.items, graph, self.source.currentText(), self.target.currentText(),
            self.direction.currentText(), provenance=self.provenance(),
        )  # fmt: skip

    def refresh(self) -> None:
        if getattr(self, "_filling", False):
            return
        super().refresh()


class VcmView(MatrixView):
    def __init__(self, session: ProjectSession) -> None:
        super().__init__(session)
        self.document, self.method, self.level, self.status = QComboBox(), QComboBox(), QComboBox(), QComboBox()
        self.only_gaps = QCheckBox("Only unverified")
        for i, box in enumerate((self.document, self.method, self.level, self.status)):
            self.controls.insertWidget(i, box)
        self.controls.insertWidget(4, self.only_gaps)
        for box in (self.document, self.method, self.level, self.status):
            box.currentTextChanged.connect(self._changed)
        self.only_gaps.toggled.connect(self._changed)
        self._filling = False
        session.loaded.connect(self._fill)

    def _fill(self) -> None:
        cfg = self.session.cfg
        if cfg is None:
            return
        want = {
            self.document: ["All documents", *self.session.documents_of_kind("requirements")],
            self.method: ["All methods", *cfg.vocab.values("verify_method")],
            self.level: ["All levels", *cfg.vocab.values("verify_level")],
            self.status: ["All statuses", *["not verified", *cfg.vocab.values("verification_status")]],
        }
        if all([box.itemText(i) for i in range(box.count())] == items for box, items in want.items()):
            return
        self._filling = True
        try:
            for box, items in want.items():
                box.clear()
                box.addItems(items)
        finally:
            self._filling = False
        self.refresh()

    def _changed(self, *_a: object) -> None:
        if not self._filling:
            self.refresh()

    @staticmethod
    def _pick(box: QComboBox) -> tuple[str, ...]:
        return () if box.currentIndex() <= 0 else (box.currentText(),)

    def build(self) -> MatrixTable | None:
        cfg, graph = self.session.cfg, self.session.graph
        assert cfg is not None and graph is not None
        flt = VcmFilter(
            self._pick(self.document), self._pick(self.method), self._pick(self.level), self._pick(self.status),
            self.only_gaps.isChecked(),
        )  # fmt: skip
        return build_vcm(cfg, self.session.items, graph, flt, provenance=self.provenance())

    def refresh(self) -> None:
        if getattr(self, "_filling", False):
            return
        super().refresh()


class CoverageView(MatrixView):
    def build(self) -> MatrixTable | None:
        cfg, graph = self.session.cfg, self.session.graph
        assert cfg is not None and graph is not None
        return coverage_table(cfg, coverage(cfg, self.session.items, graph), self.provenance())
