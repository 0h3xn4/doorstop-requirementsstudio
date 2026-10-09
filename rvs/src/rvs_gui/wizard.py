"""Guided mode: a step-by-step "new requirement" wizard with live rule feedback.

Pages: Where (document and parents) -> Statement -> Details (every template field, with help) ->
Verification (optionally create the verification item) -> Review (what will be created, and what the rules say).
The wizard only collects a :class:`RequirementSpec`; the main window creates the items."""

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from rvs_core.config.model import AttributeDef, DocumentDecl
from rvs_core.findings import Finding
from rvs_core.rules.draft import check_draft
from rvs_gui import fields
from rvs_gui.session import ProjectSession
from rvs_gui.widgets import AcronymHighlighter

_HIDDEN = {"rvs_schema_version"}
_LIVE_DEBOUNCE_ABOVE = 1000  # items; larger projects re-check after a short pause instead of on every key
NEW_STATEMENT_HINT = "The <system> shall <do something measurable> <under which conditions>."


@dataclass(frozen=True)
class VerificationSpec:
    document: str


@dataclass(frozen=True)
class RequirementSpec:
    document: str
    parents: list[str]
    text: str
    attrs: dict[str, Any]
    verification: VerificationSpec | None = None
    findings: list[Finding] = field(default_factory=list, compare=False)


def describe(finding: Finding) -> str:
    message = finding.message.replace("(new)", "This requirement")
    return f"• {message} {finding.hint}".strip()


class _Page(QWizardPage):
    def __init__(self, wizard: "NewRequirementWizard", title: str, subtitle: str) -> None:
        super().__init__()
        self.wiz = wizard
        self.setTitle(title)
        self.setSubTitle(subtitle)


class WherePage(_Page):
    def initializePage(self) -> None:
        self.wiz.fill_parents()

    def isComplete(self) -> bool:
        return self.wiz.where_complete()


class StatementPage(_Page):
    def isComplete(self) -> bool:
        return bool(self.wiz.statement.toPlainText().strip())


class DetailsPage(_Page):
    def isComplete(self) -> bool:
        return self.wiz.details_complete()


class NewRequirementWizard(QWizard):
    PAGE_WHERE, PAGE_STATEMENT, PAGE_DETAILS, PAGE_VERIFICATION, PAGE_REVIEW = range(5)

    def __init__(
        self,
        session: ProjectSession,
        parent: QWidget | None = None,
        document: str | None = None,
        parents: tuple[str, ...] = (),
    ) -> None:
        super().__init__(parent)
        assert session.cfg is not None
        self.session = session
        self.setWindowTitle("New requirement")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        self.resize(760, 640)
        self._defs: list[AttributeDef] = []
        self.fields: dict[str, QWidget] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._update_findings)

        # Where ---------------------------------------------------------------------------------------------
        self.document = QComboBox()
        self.document.addItems(self.documents())
        if document and document in self.documents():
            self.document.setCurrentText(document)
        self.parent_help = QLabel()
        self.parent_help.setWordWrap(True)
        self.parents_list = QListWidget()
        where = WherePage(self, "Where does it belong?", "Choose the document, then the requirements it derives from.")
        lay = QVBoxLayout(where)
        lay.addWidget(QLabel("Document"))
        lay.addWidget(self.document)
        lay.addWidget(self.parent_help)
        lay.addWidget(self.parents_list, 1)
        self._preset_parents = list(parents)

        # Statement ----------------------------------------------------------------------------------------
        self.statement = QPlainTextEdit()
        self.statement.setPlaceholderText(NEW_STATEMENT_HINT)
        self.statement.setMinimumHeight(110)
        cfg = session.cfg
        params = {r["id"]: r.get("params", {}) for r in cfg.rules["rules"]}.get("undefined-acronym", {})
        self.highlighter = AcronymHighlighter(self.statement.document())
        self.highlighter.configure(
            set(cfg.glossary.acronyms), int(params.get("min_length", 2)), set(params.get("ignore", []))
        )
        self.live_findings = QPlainTextEdit()
        self.live_findings.setReadOnly(True)
        self.live_findings.setPlaceholderText("Quality hints appear here as you type.")
        statement_page = StatementPage(
            self, "What must it say?", "One requirement, one 'shall'. Write it so that it can be verified."
        )
        lay = QVBoxLayout(statement_page)
        lay.addWidget(QLabel(f"Pattern: {NEW_STATEMENT_HINT}"))
        lay.addWidget(self.statement, 2)
        lay.addWidget(QLabel("Quality hints (from the project's rules; they never block you)"))
        lay.addWidget(self.live_findings, 1)

        # Details ------------------------------------------------------------------------------------------
        self.details_form = QFormLayout()
        self.details_form.setVerticalSpacing(2)
        holder = QWidget()
        holder.setLayout(self.details_form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        details = DetailsPage(self, "Details", "Fill in what you know. Fields marked * are required.")
        lay = QVBoxLayout(details)
        lay.addWidget(scroll)

        # Verification -------------------------------------------------------------------------------------
        self.verify_check = QCheckBox("Also create a planned verification item for this requirement")
        self.verify_document = QComboBox()
        self.verify_document.addItems(session.documents_of_kind("verification"))
        verification = _Page(self, "How will you show it is met?", "A requirement without verification is a gap.")
        lay = QVBoxLayout(verification)
        lay.addWidget(
            QLabel(
                "The verification method and level come from the Details page. A planned verification item "
                "links to this requirement so it appears in the verification matrix."
            )
        )
        lay.addWidget(self.verify_check)
        lay.addWidget(self.verify_document)
        lay.addStretch(1)
        has_verification = self.verify_document.count() > 0
        self.verify_check.setEnabled(has_verification)
        self.verify_document.setEnabled(has_verification)
        if not has_verification:
            self.verify_check.setToolTip("This project has no verification document.")

        # Review -------------------------------------------------------------------------------------------
        self.review = QPlainTextEdit()
        self.review.setReadOnly(True)
        review_page = _Page(self, "Review", "Check what will be created. You can go back to change anything.")
        lay = QVBoxLayout(review_page)
        lay.addWidget(self.review)

        for page in (where, statement_page, details, verification, review_page):
            self.addPage(page)
        self._where, self._statement_page, self._details_page = where, statement_page, details

        self._build_details()
        self.document.currentTextChanged.connect(self._on_document)
        self.parents_list.itemChanged.connect(lambda _i: where.completeChanged.emit())
        self.statement.textChanged.connect(self._on_statement)
        self.currentIdChanged.connect(self._on_page)
        self.fill_parents()
        self.restart()  # the first page is current (and its Next button correct) before the wizard is shown

    # where ---------------------------------------------------------------------------------------------------
    def documents(self) -> list[str]:
        return self.session.documents_of_kind("requirements")

    def _decl(self) -> DocumentDecl | None:
        assert self.session.cfg is not None
        return self.session.cfg.project.document(self.document.currentText())

    def is_root_document(self) -> bool:
        decl = self._decl()
        return decl is None or decl.parent is None

    def parent_candidates(self) -> list[str]:
        decl = self._decl()
        if decl is None or decl.parent is None:
            return []
        return [i.uid for i in self.session.items if i.document == decl.parent and i.normative and i.active]

    def fill_parents(self) -> None:
        self.parents_list.blockSignals(True)
        self.parents_list.clear()
        root = self.is_root_document()
        decl = self._decl()
        if root:
            self.parent_help.setText("This is the top-level document: its requirements have no parents.")
        else:
            self.parent_help.setText(
                f"Tick the requirement(s) in {decl.parent if decl else ''} that this one derives from. "
                "At least one is needed so that the requirement is traceable."
            )
        for uid in self.parent_candidates():
            parent_item = self.session.item(uid)
            title = (parent_item.attrs.get("title") or parent_item.header) if parent_item else ""
            entry = QListWidgetItem(f"{uid}   {title}")
            entry.setData(Qt.ItemDataRole.UserRole, uid)
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Checked if uid in self._preset_parents else Qt.CheckState.Unchecked)
            self.parents_list.addItem(entry)
        self.parents_list.setEnabled(not root)
        self.parents_list.blockSignals(False)
        self._where.completeChanged.emit()

    def checked_parents(self) -> list[str]:
        out = []
        for row in range(self.parents_list.count()):
            entry = self.parents_list.item(row)
            if entry.checkState() == Qt.CheckState.Checked:
                out.append(str(entry.data(Qt.ItemDataRole.UserRole)))
        return out

    def check_parent(self, uid: str, checked: bool = True) -> None:
        for row in range(self.parents_list.count()):
            entry = self.parents_list.item(row)
            if entry.data(Qt.ItemDataRole.UserRole) == uid:
                entry.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                return
        raise ValueError(f"{uid} cannot be a parent in {self.document.currentText()}.")

    def where_complete(self) -> bool:
        return self.is_root_document() or bool(self.checked_parents())

    def _on_document(self, _text: str) -> None:
        self._preset_parents = []
        self.fill_parents()
        self._build_details()
        self._on_statement()

    # details -------------------------------------------------------------------------------------------------
    def _build_details(self) -> None:
        assert self.session.cfg is not None
        previous = {n: fields.get_value(w, d.type) for d in self._defs for n, w in self.fields.items() if n == d.name}
        while self.details_form.rowCount():
            self.details_form.removeRow(0)
        self.fields.clear()
        cfg = self.session.cfg
        decl = self._decl()
        kind = decl.kind if decl else "requirements"
        self._defs = [
            a for a in cfg.templates.kinds[kind].attributes if a.name not in _HIDDEN and a.type != "ref-list"
        ] + list(cfg.project.free_attributes)
        defaults = cfg.templates.kinds[kind].defaults
        for adef in self._defs:
            widget = fields.make_widget(self.session, adef, self._on_field)
            self.fields[adef.name] = widget
            self.details_form.addRow(fields.label_text(adef), widget)
            tip = fields.help_text(adef)
            if tip:
                self.details_form.addRow("", fields.help_label(tip))
            value = previous.get(adef.name) or defaults.get(adef.name)
            if value not in (None, ""):
                fields.set_value(widget, value)
        fields.refresh_completions(self.session, self._defs, self.fields)

    def field_set(self, name: str, value: Any) -> None:
        fields.set_value(self.fields[name], value)

    def attrs(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for adef in self._defs:
            value = fields.get_value(self.fields[adef.name], adef.type)
            if value not in ("", [], None):
                out[adef.name] = value
        return out

    def details_complete(self) -> bool:
        for adef in self._defs:
            if (
                adef.required
                and adef.type in ("string", "text")
                and not fields.get_value(self.fields[adef.name], adef.type)
            ):
                return False
        return True

    def _on_field(self, *_args: object) -> None:
        self._details_page.completeChanged.emit()
        self._schedule()

    # live findings ---------------------------------------------------------------------------------------------
    def _on_statement(self) -> None:
        self._statement_page.completeChanged.emit()
        self._schedule()

    def _schedule(self) -> None:
        if len(self.session.items) > _LIVE_DEBOUNCE_ABOVE:
            self._timer.start()
        else:
            self._update_findings()

    def findings(self) -> list[Finding]:
        assert self.session.cfg is not None
        text = self.statement.toPlainText().strip()
        if not text:
            return []
        return check_draft(
            self.session.cfg,
            self.session.items,
            self.session.docs,
            document=self.document.currentText(),
            text=text,
            attrs=self.attrs(),
            parents=self.checked_parents(),
        )

    def _update_findings(self) -> None:
        found = self.findings()
        if not self.statement.toPlainText().strip():
            self.live_findings.setPlainText("")
        elif not found:
            self.live_findings.setPlainText("No quality problems found.")
        else:
            self.live_findings.setPlainText("\n".join(describe(f) for f in found))

    # review / result -----------------------------------------------------------------------------------------
    def _on_page(self, page: int) -> None:
        if page == self.PAGE_REVIEW:
            self.refresh_review()

    def refresh_review(self) -> None:
        spec = self.spec()
        lines = [
            f"Document: {spec.document}",
            f"Parents: {', '.join(spec.parents) if spec.parents else 'none'}",
            "",
            f"Statement: {spec.text}",
            "",
        ]
        lines += [
            f"{k.replace('_', ' ').capitalize()}: {v if not isinstance(v, list) else ', '.join(v)}"
            for k, v in spec.attrs.items()
        ]
        lines.append("")
        lines.append(
            f"A planned verification item will be created in {spec.verification.document}."
            if spec.verification
            else "No verification item will be created now. Add one later to close the verification gap."
        )
        lines.append("")
        if spec.findings:
            lines.append(
                "The project's rules found the following. You can still create the requirement and fix it later:"
            )
            lines += [describe(f) for f in spec.findings]
        else:
            lines.append("The project's rules found no problems.")
        self.review.setPlainText("\n".join(lines))

    def spec(self) -> RequirementSpec:
        verification = (
            VerificationSpec(self.verify_document.currentText())
            if self.verify_check.isChecked() and self.verify_document.count()
            else None
        )
        return RequirementSpec(
            document=self.document.currentText(),
            parents=self.checked_parents(),
            text=self.statement.toPlainText().strip(),
            attrs=self.attrs(),
            verification=verification,
            findings=self.findings(),
        )
