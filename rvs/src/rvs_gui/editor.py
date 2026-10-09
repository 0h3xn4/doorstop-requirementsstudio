"""Requirement editor: structured form (generated from the document template), Markdown statement with
live preview, parent links, a mandatory-when-baselined reason, and the item's own findings."""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from rvs_core.adapter import ItemData, ProjectError
from rvs_core.authoring import ReasonRequiredError
from rvs_core.config.model import AttributeDef
from rvs_gui import fields
from rvs_gui.completion import UidLineEdit
from rvs_gui.fields import normalise as _norm
from rvs_gui.fields import parse_list as _parse_list
from rvs_gui.session import ProjectSession
from rvs_gui.widgets import AcronymHighlighter

# Attributes edited elsewhere or managed by RVS.
_HIDDEN = {"rvs_schema_version"}
_LIST_TYPES = fields.LIST_TYPES


class RequirementEditor(QWidget):
    message = Signal(str, str)  # (kind, text) -> shown by the main window's notification
    dirty_changed = Signal(bool)
    item_loaded = Signal(str)

    def __init__(self, session: ProjectSession) -> None:
        super().__init__()
        self.session = session
        self.current_uid: str | None = None
        self._item: ItemData | None = None
        self._defs: list[AttributeDef] = []
        self._fields: dict[str, QWidget] = {}
        self._loading = False
        self._last_dirty = False
        self._help_visible = True
        self._help_labels: list[QLabel] = []

        self.heading = QLabel("No item selected")
        self.heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.form = QFormLayout()
        self.form.setVerticalSpacing(4)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.statement = QPlainTextEdit()
        self.statement.setPlaceholderText("Requirement statement (Markdown)")
        self.preview = QTextBrowser()
        self.preview.setOpenLinks(False)
        self.preview.setOpenExternalLinks(False)
        self.highlighter = AcronymHighlighter(self.statement.document())
        self.why = QLineEdit()
        self.why.setPlaceholderText("Reason for change (required once an item is baselined)")
        self.save_button = QPushButton("Save")
        self.revert_button = QPushButton("Revert")
        self.clear_suspect_button = QPushButton("Clear suspect links")
        self.clear_suspect_button.setToolTip("Accept the current state of the parent items this item links to")
        self.clear_suspect_button.setEnabled(False)
        self.item_findings = QListWidget()
        self.item_findings.setMaximumHeight(110)
        self.item_findings.setWordWrap(True)

        text_split = QSplitter()
        text_split.addWidget(self.statement)
        text_split.addWidget(self.preview)
        form_holder = QWidget()
        form_holder.setLayout(self.form)
        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(form_holder)
        form_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        form_scroll.setMinimumHeight(280)
        text_split.setMinimumHeight(150)
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(form_scroll)
        vertical.addWidget(text_split)
        vertical.setStretchFactor(0, 3)
        vertical.setStretchFactor(1, 2)
        buttons = QHBoxLayout()
        buttons.addWidget(self.why, 1)
        buttons.addWidget(self.clear_suspect_button)
        buttons.addWidget(self.revert_button)
        buttons.addWidget(self.save_button)
        root = QVBoxLayout(self)
        root.addWidget(self.heading)
        root.addWidget(vertical, 1)
        root.addLayout(buttons)
        root.addWidget(QLabel("Problems with this item"))
        root.addWidget(self.item_findings)

        self.statement.textChanged.connect(self._on_edited)
        self.why.textChanged.connect(self._update_buttons)
        self.save_button.clicked.connect(self.save)
        self.revert_button.clicked.connect(self.revert)
        self.clear_suspect_button.clicked.connect(self.clear_suspect)
        self.setEnabled(False)

    # form construction ########################################################
    def _rebuild_form(self, item: ItemData) -> None:
        assert self.session.cfg is not None
        while self.form.rowCount():
            self.form.removeRow(0)
        self._fields.clear()
        self._help_labels.clear()
        cfg = self.session.cfg
        kind = self.session.kind_of(item.document)
        self._defs = [
            a for a in cfg.templates.kinds[kind].attributes if a.name not in _HIDDEN and a.type != "ref-list"
        ] + list(cfg.project.free_attributes)
        for adef in self._defs:
            widget = fields.make_widget(self.session, adef, self._on_edited)
            self._fields[adef.name] = widget
            self.form.addRow(fields.label_text(adef), widget)
            self._add_help(fields.help_text(adef))
        decl = cfg.project.document(item.document)
        root_doc = decl is not None and decl.parent is None
        parent_doc = decl.parent if decl else None
        parents = UidLineEdit(
            lambda: [i.uid for i in self.session.items if i.document == parent_doc and i.normative and i.active]
        )
        parents.setPlaceholderText("Parent item IDs, comma separated" if not root_doc else "Root document: no parents")
        parents.setEnabled(not root_doc)
        parents.setMinimumHeight(32)
        parents.setToolTip(
            "The requirements this one derives from (items of the parent document). Item IDs, comma separated."
        )
        parents.textChanged.connect(self._on_edited)
        self._fields["parents"] = parents
        self.form.addRow("Parents", parents)
        self._add_help("The requirements this one derives from, from the parent document." if not root_doc else "")
        rules = {r["id"]: r.get("params", {}) for r in cfg.rules["rules"]}
        params = rules.get("undefined-acronym", {})
        self.highlighter.configure(
            set(cfg.glossary.acronyms), int(params.get("min_length", 2)), set(params.get("ignore", []))
        )

    def _add_help(self, text: str) -> None:
        label = fields.help_label(text)
        label.setVisible(self._help_visible and bool(text))
        self._help_labels.append(label)
        self.form.addRow("", label)

    def help_visible(self) -> bool:
        return self._help_visible

    def set_help_visible(self, visible: bool) -> None:
        """Guided mode shows a line of help under every field; expert mode keeps the tooltips only."""
        self._help_visible = visible
        for label in self._help_labels:
            label.setVisible(visible and bool(label.text()))

    def field(self, name: str) -> Any:
        return self._fields[name]

    # reading / writing widget values ##########################################
    _get = staticmethod(fields.get_value)

    @staticmethod
    def _set(widget: QWidget, value: Any, kind: str) -> None:
        fields.set_value(widget, value)

    def load(self, uid: str) -> None:
        item = self.session.item(uid)
        if item is None:
            return
        self._loading = True
        try:
            if self._item is None or self._item.document != item.document or not self._fields:
                self._rebuild_form(item)
            self._item = item
            self.current_uid = uid
            self.heading.setText(f"{uid}  {item.attrs.get('title') or item.header}")
            for adef in self._defs:
                self._set(self._fields[adef.name], item.attrs.get(adef.name), adef.type)
            self._set(self._fields["parents"], list(item.links), "uid-list")
            fields.refresh_completions(self.session, self._defs, self._fields)
            self.statement.setPlainText(item.text.strip())
            self.why.clear()
            self._refresh_findings()
            self.clear_suspect_button.setEnabled(bool(self.session.suspect_parents(uid)))
            self.setEnabled(True)
        finally:
            self._loading = False
        self._on_edited()
        self.item_loaded.emit(uid)

    def _refresh_findings(self) -> None:
        self.item_findings.clear()
        if self.current_uid:
            for f in self.session.findings_for(self.current_uid):
                self.item_findings.addItem(f"{f.severity.value.upper()}  {f.message} {f.hint}".strip())

    # dirty tracking ###########################################################
    def changes(self) -> tuple[str | None, dict[str, Any], list[str] | None]:
        item = self._item
        if item is None:
            return None, {}, None
        text = self.statement.toPlainText().strip()
        new_text = text if text != item.text.strip() else None
        attrs = {}
        for adef in self._defs:
            value = self._get(self._fields[adef.name], adef.type)
            if value != _norm(item.attrs.get(adef.name), adef.type):
                attrs[adef.name] = value
        parents = _parse_list(self._fields["parents"].text())  # type: ignore[attr-defined]
        new_parents = sorted(set(parents)) if sorted(set(parents)) != sorted(item.links) else None
        return new_text, attrs, new_parents

    def is_dirty(self) -> bool:
        if self._item is None:
            return False
        text, attrs, parents = self.changes()
        return text is not None or bool(attrs) or parents is not None

    def _on_edited(self, *_args: object) -> None:
        if self._loading:
            return
        self.preview.setMarkdown(self.statement.toPlainText())
        self._update_buttons()

    def _update_buttons(self, *_args: object) -> None:
        dirty = self.is_dirty()
        self.save_button.setEnabled(dirty)
        self.revert_button.setEnabled(dirty)
        if dirty != self._last_dirty:
            self._last_dirty = dirty
            self.dirty_changed.emit(dirty)

    # actions ##################################################################
    def clear_suspect(self) -> None:
        uid = self.current_uid
        if uid is None:
            return
        try:
            self.session.clear_suspect(uid, why=self.why.text())
        except (ReasonRequiredError, ValueError, ProjectError) as exc:
            self.message.emit("error", str(exc))
            return
        self.load(uid)
        self.message.emit("success", f"Cleared the suspect links of {uid}.")

    def revert(self) -> None:
        if self.current_uid:
            self.load(self.current_uid)

    def save(self) -> bool:
        uid = self.current_uid
        if uid is None or self._item is None:
            return False
        text, attrs, parents = self.changes()
        if text is None and not attrs and parents is None:
            self.message.emit("info", "Nothing to save.")
            return True
        why = self.why.text()
        try:
            if parents is not None:
                self.session.set_parents(uid, parents, why=why)
            if text is not None or attrs:
                self.session.update_item(uid, text=text, attrs=attrs, why=why)
        except (ReasonRequiredError, ValueError, ProjectError) as exc:
            self.message.emit("error", str(exc))
            return False
        except Exception as exc:  # noqa: BLE001 - never show a traceback to the user (spec rule 19)
            self.message.emit("error", f"{uid} could not be saved: {exc}. Your changes are still in the editor.")
            return False
        self.load(uid)
        self.message.emit("success", f"Saved {uid}.")
        return True
