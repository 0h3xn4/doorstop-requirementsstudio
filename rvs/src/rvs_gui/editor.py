"""Requirement editor: structured form (generated from the document template), Markdown statement with
live preview, parent links, a mandatory-when-baselined reason, and the item's own findings."""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
from rvs_gui.widgets import AcronymHighlighter, keyboard_text, named, secondary

NO_FIELD_HELP = "Select a field to see what it means."
STATEMENT_HELP = "The requirement text. Markdown is allowed; one 'shall' per requirement. Acronyms that are not in the glossary are underlined."
REASON_HELP = (
    "Why you are changing this item. It is required once the item is baselined, and is kept in the item's history."
)
SUSPECT_TIP = (
    "A suspect link means a parent item changed after this item was last reviewed. "
    "Review the parent, then use this button to accept its current state."
)
NO_SUSPECT_TIP = SUSPECT_TIP + "\nNothing to clear now: no parent item has changed since this item was last reviewed."

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
        self._signature: object | None = None
        self._help_for: dict[QWidget, str] = {}  # the form fields (rebuilt with the form)
        self._static_help: dict[QWidget, str] = {}  # the fixed widgets: statement, reason, buttons
        # Asked before unsaved edits are thrown away by Revert; the main window replaces it with a question to the user.
        self.confirm_discard: Callable[[str], bool] = lambda _uid: True

        self.heading = QLabel("No item selected")
        self.heading.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.form = QFormLayout()
        self.form.setVerticalSpacing(2)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.statement = named(keyboard_text(QPlainTextEdit()), "Requirement statement")
        self.statement.setPlaceholderText("Requirement statement (Markdown)")
        self.preview = named(QTextBrowser(), "Statement preview")
        self.preview.setOpenLinks(False)
        self.preview.setOpenExternalLinks(False)
        self.highlighter = AcronymHighlighter(self.statement.document())
        self.why = named(QLineEdit(), "Reason for change")
        self.why.setPlaceholderText("Reason for change (required once an item is baselined)")
        self.why.setMinimumWidth(240)
        self.save_button = QPushButton("Save")
        self.revert_button = QPushButton("Revert")
        secondary(self.revert_button)
        self.clear_suspect_button = QPushButton("Clear suspect links")
        secondary(self.clear_suspect_button)
        self.clear_suspect_button.setToolTip(NO_SUSPECT_TIP)
        self.clear_suspect_button.setEnabled(False)
        self.item_findings = named(QListWidget(), "Problems with this item")
        self.item_findings.setMaximumHeight(72)
        self.item_findings.setWordWrap(True)
        self.item_findings.setTabKeyNavigation(False)
        self.no_findings = QLabel("No problems with this item.")
        self.no_findings.setObjectName("Empty")

        text_split = QSplitter()
        text_split.addWidget(self.statement)
        text_split.addWidget(self.preview)
        form_holder = QWidget()
        form_holder.setLayout(self.form)
        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_scroll.setWidget(form_holder)
        self.form_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.form_scroll.setMinimumHeight(120)
        # Guided mode explains the field being edited here, instead of a help line under every field (which left
        # room for only three fields at once).
        self.help_line = fields.help_label(NO_FIELD_HELP)
        self.help_line.setMinimumHeight(44)
        self.help_line.setAlignment(Qt.AlignmentFlag.AlignTop)
        form_pane = QWidget()
        pane_layout = QVBoxLayout(form_pane)
        pane_layout.setContentsMargins(0, 0, 0, 0)
        pane_layout.addWidget(self.form_scroll, 1)
        pane_layout.addWidget(self.help_line)
        text_split.setMinimumHeight(100)
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.addWidget(form_pane)
        vertical.addWidget(text_split)
        vertical.setStretchFactor(0, 5)
        vertical.setStretchFactor(1, 2)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self.clear_suspect_button)
        buttons.addWidget(self.revert_button)
        buttons.addWidget(self.save_button)
        root = QVBoxLayout(self)
        root.addWidget(self.heading)
        root.addWidget(vertical, 1)
        root.addWidget(self.why)  # the reason has a row of its own: it was squeezed to a sliver beside three buttons
        root.addLayout(buttons)
        root.addWidget(QLabel("Problems with this item"))
        root.addWidget(self.item_findings)
        root.addWidget(self.no_findings)
        self.no_findings.hide()
        for widget, text in (
            (self.statement, STATEMENT_HELP),
            (self.preview, "A preview of the statement as it will be exported."),
            (self.why, REASON_HELP),
            (self.save_button, ""),
            (self.revert_button, ""),
            (self.clear_suspect_button, ""),
        ):
            self._static_help[widget] = text  # an empty text resets the help line to the generic hint
            widget.installEventFilter(self)

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
        self._help_for.clear()
        cfg = self.session.cfg
        kind = self.session.kind_of(item.document)
        self._defs = [
            a for a in cfg.templates.kinds[kind].attributes if a.name not in _HIDDEN and a.type != "ref-list"
        ] + list(cfg.project.free_attributes)
        for adef in self._defs:
            widget = fields.make_widget(self.session, adef, self._on_edited)
            self._fields[adef.name] = widget
            self.form.addRow(fields.label_text(adef), widget)
            self._track_help(widget, fields.help_text(adef))
        decl = cfg.project.document(item.document)
        root_doc = decl is not None and decl.parent is None
        parent_doc = decl.parent if decl else None
        parents = UidLineEdit(
            lambda: [i.uid for i in self.session.items if i.document == parent_doc and i.normative and i.active]
        )
        parents.setPlaceholderText("Parent item IDs, comma separated" if not root_doc else "Root document: no parents")
        parents.setEnabled(not root_doc)
        parents.setMinimumHeight(32)
        parents.setAccessibleName("Parents")
        parents.setToolTip(
            "The requirements this one derives from (items of the parent document). Item IDs, comma separated."
        )
        parents.textChanged.connect(self._on_edited)
        self._fields["parents"] = parents
        self.form.addRow("Parents", parents)
        self._track_help(
            parents,
            "The requirements this one derives from, from the parent document."
            if not root_doc
            else "A top-level document: its requirements have no parents.",
        )
        self._signature = self._form_signature(item)
        self._apply_tab_order()

    def _form_signature(self, item: ItemData) -> object:
        """Everything the form is built from, as a cheap comparable value. The configuration object itself is replaced on
        every refresh (each save), but the form only has to be rebuilt when this changes: rebuilding it on every save
        threw away the keyboard focus and the scroll position."""
        cfg = self.session.cfg
        assert cfg is not None
        kind = self.session.kind_of(item.document)
        decl = cfg.project.document(item.document)
        defs = tuple(
            (a.name, a.type, a.vocab, a.required, a.help)
            for a in [*cfg.templates.kinds[kind].attributes, *cfg.project.free_attributes]
        )
        vocabs = tuple((a[0], tuple(cfg.vocab.values(str(a[2])))) for a in defs if a[1] == "enum" and a[2])
        return (kind, item.document, decl.parent if decl else None, defs, vocabs)

    def focus_chain(self) -> list[QWidget]:
        """The widgets in the order Tab visits them: fields top to bottom, statement, reason, buttons."""
        chain = [self._fields[a.name] for a in self._defs if a.name in self._fields]
        if "parents" in self._fields:
            chain.append(self._fields["parents"])
        chain += [self.statement, self.why, self.clear_suspect_button, self.revert_button, self.save_button]
        return chain

    def _apply_tab_order(self) -> None:
        """Creation order is not visual order for a form that is rebuilt per document: say it explicitly."""
        chain = self.focus_chain()
        for before, after in zip(chain, chain[1:], strict=False):
            QWidget.setTabOrder(before, after)

    def first_focus_widget(self) -> QWidget:
        """Where keyboard users arrive from the item table: the statement (the one field every item has)."""
        return self.statement

    def focus_editor(self) -> bool:
        """Move the keyboard focus into the form. False when there is no item to edit."""
        if not self.isEnabled():
            return False
        self.statement.setFocus(Qt.FocusReason.ShortcutFocusReason)
        return True

    def _configure_highlighter(self) -> None:
        cfg = self.session.cfg
        assert cfg is not None
        rules = {r["id"]: r.get("params") or {} for r in cfg.rules["rules"]}
        params = rules.get("undefined-acronym", {})
        min_length = params.get("min_length")
        ignore = params.get("ignore")
        self.highlighter.configure(
            set(cfg.glossary.acronyms),
            min_length if isinstance(min_length, int) else 2,
            {str(x) for x in ignore} if isinstance(ignore, list) else set(),
        )

    def clear(self) -> None:
        """Forget the item (the project changed): empty form, nothing to save."""
        self._item = None
        self.current_uid = None
        self._fields.clear()
        self._defs = []
        self._signature = None
        self._loading = True
        try:
            self.statement.clear()
            self.why.clear()
            self.item_findings.clear()
            self.preview.clear()
            while self.form.rowCount():
                self.form.removeRow(0)
            self.heading.setText("No item selected")
        finally:
            self._loading = False
        self.clear_suspect_button.setEnabled(False)
        self.clear_suspect_button.setToolTip(NO_SUSPECT_TIP)
        self.item_findings.hide()
        self.no_findings.hide()
        self.setEnabled(False)
        self._update_buttons()

    def _track_help(self, widget: QWidget, text: str) -> None:
        self._help_for[widget] = text
        widget.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt API
        if event.type() == QEvent.Type.FocusIn and isinstance(obj, QWidget):
            if obj in self._help_for:
                self.help_line.setText(self._help_for[obj] or NO_FIELD_HELP)
            elif obj in self._static_help:  # the statement, the reason, the buttons: never leave the last field's help
                self.help_line.setText(self._static_help[obj] or NO_FIELD_HELP)
        return False

    def restyle(self) -> None:
        """Re-apply the colours of the current theme to the help line."""
        self.help_line.setStyleSheet(fields.help_label("").styleSheet())

    def help_visible(self) -> bool:
        return self._help_visible

    def set_help_visible(self, visible: bool) -> None:
        """Guided mode shows a line of help under every field; expert mode keeps the tooltips only."""
        self._help_visible = visible
        self.help_line.setVisible(visible)

    def field(self, name: str) -> Any:
        return self._fields[name]

    # reading / writing widget values ##########################################
    _get = staticmethod(fields.get_value)

    @staticmethod
    def _set(widget: QWidget, value: Any, kind: str) -> None:
        fields.set_value(widget, value, kind)

    def load(self, uid: str) -> None:
        item = self.session.item(uid)
        if item is None:
            return
        self._loading = True
        try:
            if (
                self._item is None
                or self._item.document != item.document
                or not self._fields
                or self._signature != self._form_signature(item)  # the template, vocabulary or document changed
            ):
                self._rebuild_form(item)
            self._configure_highlighter()
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
            self._update_suspect_button(uid)
            self.setEnabled(True)
        finally:
            self._loading = False
        self._on_edited()
        self.item_loaded.emit(uid)

    def _update_suspect_button(self, uid: str | None) -> None:
        suspect = self.session.suspect_parents(uid) if uid else []
        self.clear_suspect_button.setEnabled(bool(suspect))
        self.clear_suspect_button.setToolTip(
            f"{SUSPECT_TIP}\nSuspect parents: {', '.join(suspect)}." if suspect else NO_SUSPECT_TIP
        )

    def _refresh_findings(self) -> None:
        self.item_findings.clear()
        if self.current_uid:
            for f in self.session.findings_for(self.current_uid):
                entry = QListWidgetItem(f"{f.severity.value.upper()}  {f.message} {f.hint}".strip())
                if "suspect" in f.code.lower() or "suspect" in f.message.lower():
                    entry.setToolTip(SUSPECT_TIP)
                self.item_findings.addItem(entry)
        empty = self.item_findings.count() == 0
        self.item_findings.setVisible(not empty)
        self.no_findings.setVisible(empty and self.current_uid is not None)

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
        if self.is_dirty():
            self.message.emit(
                "warning", f"Save or revert your changes to {uid} first: clearing links reloads the item."
            )
            return
        try:
            self.session.clear_suspect(uid, why=self.why.text())
        except (ReasonRequiredError, ValueError, ProjectError, OSError) as exc:
            self.message.emit("error", str(exc))
            return
        self.load(uid)
        self.message.emit("success", f"Cleared the suspect links of {uid}.")

    def revert(self) -> bool:
        """Reload the item from disk. Unsaved edits are only thrown away after confirm_discard says so."""
        uid = self.current_uid
        if not uid:
            return False
        if self.is_dirty() and not self.confirm_discard(uid):
            return False
        self.load(uid)
        return True

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
        except OSError as exc:
            self.message.emit(
                "error", f"{uid} could not be saved ({exc.strerror or exc}). Your changes are still in the editor."
            )
            return False
        except Exception as exc:  # noqa: BLE001 - never show a traceback to the user (spec rule 19)
            self.message.emit("error", f"{uid} could not be saved: {exc}. Your changes are still in the editor.")
            return False
        self.load(uid)
        self.message.emit("success", f"Saved {uid}.")
        return True
