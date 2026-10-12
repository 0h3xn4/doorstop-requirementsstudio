# Pre-release audit: GUI editor, wizard, views, dialogs, jobs

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

Auditor: gui-parts (rvs_gui except app.py and shortcuts.py, plus assets/). All probe scripts are in
`<scratch>/gui-parts/` (p_*.py,
shared helper common.py; each runs with `QT_QPA_PLATFORM=offscreen` on its own copy of examples/minimal10 or satellite300).
Repository untouched.

## Coverage
Files read in full: baseline_dialog.py, baselines_view.py, changes_view.py, completion.py, crash.py, dialogs.py, diff_view.py,
doctree.py, editor.py, export_dialog.py, fields.py, glossary_dialog.py, graph_layout.py, graph_view.py, help_viewer.py,
impact_panel.py, import_dialog.py, jobs.py, matrix_views.py, models.py, problems.py, project_dialogs.py, session.py, theme.py,
widgets.py, wizard.py, assets/ (5 .woff fonts + 2 OFL texts). Also read: BRIEF, CLAUDE.md, ARCHITECTURE/DECISIONS/DEVIATIONS (V24-V31),
AUDIT.md, SPEC.md, core `authoring.py`, `diagnostics.py` (crash report), `attrtypes.py`, the free-attribute config schema, and the
EnumDelegate / inline-edit / create_item / create_from_spec parts of app.py that feed my slice.
Tests read and judged: test_gui_authoring, test_gui_changecontrol, test_gui_editor_layout, test_gui_matrices, test_gui_theme,
test_graph_layout, test_audit_gui_editor, test_audit_gui_theme, test_audit_gui_dialogs, test_review_gui, test_gui_usability
(full text for the first six and test_audit_gui_editor/theme; test names and key assertions for the rest).

Probes run (one line each):
- p_poison/p_zero/p_zero2/p_prov/p_tip/p_find: item title/text/owner/project name/finding message containing HTML and `/dev/zero` images through every label, tooltip and the Markdown preview (RLIMIT_AS 3-4 GB so a runaway read aborts instead of eating the machine).
- p_ed1: save with changed parents + invalid date (partial save). p_ed2/p_ed3: out-of-vocabulary enum value (opens dirty, stuck, silently blanked), EnumDelegate commit, item changed on disk meanwhile (V29), item deleted on disk while dirty.
- p_int: free attributes of type int/date/string-list/text through the editor.
- p_wiz1/p_wiz2: wizard every page, Back/Next, required-field gating, draft vs real findings, timing at 339 and 1,000 items.
- p_models: sort/filter on None and mixed case, setData with bogus/empty/NUL/100k-char values.
- p_jobs: exception, SystemExit/KeyboardInterrupt in worker, callback raising, callback after widget deleted, 300 jobs, job started from a non-GUI thread, switch-interval restore.
- p_sess: 80 repeated refresh (RSS 89.6 -> 91.6 MB, flat), external edit/delete visibility.
- p_graph: fake neighbourhood with 200 and 2,000 nodes plus a self loop (0.04 s / 0.37 s; no hang).
- p_dlg/p_dlg2: path validation (long component, NUL, `~`), destination suffix, NewItemDialog validation vs service rules.
- p_help: link navigation (http, https, mailto, ftp, javascript, file, fragments).
- p_crash: crash report content; behaviour when an exception repeats (model.data raising).
- p_theme/p_font: QSS parse messages (none), contrast table of the token pairs actually used, font families/glyph coverage.
- p_cr/p_cr2: change request with a status the configuration does not define; baseline dialog vs core gate.
- p_bl/p_bl2: baseline list/verify timing (8 baselines on satellite300; 1,000-item project).
- p_long: 10k/200k/1M-character statement and 200k-character title.
- p_comp: UID completer with weird input. p_ui: tree expansion / problems sort after a save. p_a11y/p_tab: accessible names, tab order, minimum size (300x232).
- Mutation runs on a copy of src/ (mut/): 7 mutations, 5 survived (GUIP-18).
Tests run (targeted only): test_gui_authoring, test_gui_changecontrol, test_gui_editor_layout, test_gui_matrices, test_gui_theme, test_graph_layout (72 passed);
test_audit_gui_editor, test_audit_gui_theme, test_audit_gui_dialogs, test_review_gui, test_gui_usability (114 passed).

## Findings

### GUIP-01 Project data is shown as rich text; an image reference to a special file aborts the whole program
- Where: editor.py:79,387 (`preview.setMarkdown`), editor.py:71,328 (`heading` QLabel, AutoText), models.py:156-157 (ToolTipRole returns raw `item.text`/title), problems.py:69,117 (`detail` QLabel, AutoText, shows finding message/hint/location), matrix_views.py:110,112,170-171 (`provenance_label`/`notes_label` carry the project name and user)
- Severity: high
- Confidence: verified (Markdown preview, heading, Problems detail and a tooltip crash; formatting injection shown for the provenance label)
- What is wrong: Qt treats a QLabel/tooltip as rich text when a known HTML tag appears on the first line (Qt::mightBeRichText), so a title, a finding message that quotes a stored value (RVS-ATTR-VOCAB prints the bad value), a project name or a tooltip is parsed as HTML. The Markdown preview (`QTextBrowser.setMarkdown`) additionally loads any local file named by `![x](path)`. Nothing is fetched from the network (http(s) images do nothing), but a local special file is read to the end: `/dev/zero`, `/dev/urandom`, a FIFO or a multi-GB file. Memory grows until `std::bad_alloc` (here with a 3-4 GB limit) or the OOM killer; the process aborts with no Python traceback, so crash.py never runs and unsaved work is lost. Selecting such an item, hovering a table row, or selecting a problem row is enough. Item files come from Git (colleagues), so this is a hostile-input path. On Windows the same mechanism would read `//server/share/x.png` (SMB; reading-only, not run), which also breaks the no-network rule. Plain formatting injection: a project name `Proj <i>Italic</i> <b>B</b>` renders as HTML in the matrix provenance line; a title containing a real tag such as `<i>` or `<tt>` loses it in the editor heading.
- Evidence:
  - `p_zero2.py statement`: item text `The spacecraft shall X. ![x](/dev/zero)`; `w.select_item("SYS-0001")` -> `terminate called after throwing an instance of 'std::bad_alloc'`. Same for title `T <img src="/dev/zero">` (heading label).
  - `p_tip.py`: `QToolTip.showText(pos, 'Statement <img src="/dev/zero"> shall', w)` -> bad_alloc. The item table's tooltip returns exactly `item.text`.
  - `p_find.py`: item with `status: '<b>BOLD</b> <img src="/dev/zero">'`; finding message `Attribute 'status' of EPS-0001 is '<b>BOLD</b> <img src="/dev/zero">', which is not in the project vocabulary.`; selecting that row in the Problems panel -> bad_alloc.
  - `p_prov.py`: provenance text `Project: Proj <i>Italic</i> <b>B</b> ...`; label sizeHint 742 (rich) vs 854 (plain).
  - `p_zero.py http`: `![x](http://127.0.0.1:9/x.png)` and `<img src="https://example.com/a.png">` return instantly (no remote fetch: good).
- Why it matters: crash/denial of service from a project file, loss of unsaved edits, and wrong display of ordinary titles.
- Proposed fix: (1) Preview: subclass QTextBrowser, override `loadResource` to return an empty QVariant (or allow only files inside the project folder under a size cap); keep HTML off (`MarkdownNoHTML`). (2) Every QLabel that shows project data: `setTextFormat(Qt.TextFormat.PlainText)` (editor heading, Problems detail, provenance/notes labels, ImpactPanel summary, wizard parent_help, ChangesView heading, diff summary). (3) Model tooltips: return escaped text (`html.escape`) or a plain-text-forced tooltip.
- Test that would catch it: open an item whose statement is `![x](/dev/zero)` under a memory limit (or monkeypatch `loadResource` and assert it is never asked for a local path); assert PlainText format on the heading and Problems detail; assert a title `<b>x</b>` tooltip is not rich.

### GUIP-02 An item whose stored enum value is not in the vocabulary opens "modified", cannot be left, and any save silently blanks the value
- Where: fields.py:149-150 (`set_value`: `findText` = -1 -> `max(0,-1)` selects the blank entry), editor.py:363-376 (`changes`), editor.py:312-341 (`load`)
- Severity: high
- Confidence: verified
- What is wrong: a value outside the current vocabulary (renamed/removed entry, hand edit, import) shows as an empty combo, so `get_value` ("") differs from the stored value and the item is dirty as soon as it is opened. `select_item` then refuses to leave ("has unsaved changes"); Revert reloads and is dirty again; the only exits are picking a value or saving. Saving any other field also writes `priority: ''`, destroying the old value without telling the user. (The earlier audit fixed only "stored value is empty".)
- Evidence: `p_ed2.py`/`p_ed3.py`: EPS-0001 with `priority: urgent`: `priority combo shows: ''  dirty on open: True  changes: {'priority': ''}`; `select_item("EPS-0002")` -> `False | EPS-0001 has unsaved changes. Save or revert them before opening EPS-0002.`; after changing only `owner`, saved: disk has `priority: ''`.
- Why it matters: silent data change the user did not ask for (the validator already reports RVS-ATTR-VOCAB, so the value was meaningful) and a navigation trap on every item carrying a retired vocabulary value, which is exactly what happens after the vocabulary is edited.
- Proposed fix: add the unknown stored text as an extra, marked combo entry ("urgent (not in vocabulary)") so it round-trips and compares equal.
- Test that would catch it: open an item with an out-of-vocabulary enum value; assert not dirty, switching works, and saving another field leaves the value unchanged.

### GUIP-03 In-table enum editor silently assigns the first vocabulary value
- Where: app.py:98-118 (`EnumDelegate.setEditorData/setModelData`; named in the brief), models.py:84-94 (`setData`)
- Severity: medium
- Confidence: verified (delegate driven directly)
- What is wrong: `setEditorData` uses `max(0, findText(...))`. For an unset or out-of-vocabulary value in a required column the combo shows the first entry (`draft`, `functional`...), and Qt commits the editor on Enter or focus loss even when the user changed nothing, so opening and leaving the cell assigns that value (history entry written; reason asked on baselined items).
- Evidence: `p_ed2.py` B2: EPS-0001 `status: weird`; editor shows `draft`; `setModelData` -> item status `draft`.
- Why it matters: silent status/type changes through a stray click in expert mode.
- Proposed fix: for required enums offer an empty first entry when the current value is empty/unknown; skip the commit when `findText` was -1 and nothing was chosen.
- Test that would catch it: delegate round trip with an unknown value must not change the item.

### GUIP-04 Integer free attributes can never be saved from the editor (or the wizard)
- Where: fields.py:105-115 (QLineEdit for int), fields.py:134-141 (`get_value` returns text); core authoring.py `_check_values` (`type_ok("int","42")` is false)
- Severity: medium
- Confidence: verified
- What is wrong: `free_attributes` may have type `int` (project schema: string|text|int|date|string-list). The editor sends the string `"42"`; `EditService` refuses it. Because the refusal is for the whole save, other edits made at the same time are blocked until the number field is emptied. The wizard's `attrs()` has the same problem.
- Evidence: `p_int.py` with `free_attributes: [{name: mass_kg, type: int}, ...]`: `save int 42: False | 'mass_kg' must be a whole number; got '42'.`; the item stays dirty.
- Why it matters: a configuration option the schema allows is unusable in the GUI, and no test covers non-string types in the form.
- Proposed fix: convert `int` fields in `get_value` (`int(raw)` when it parses, otherwise pass the text so the service reports it).
- Test that would catch it: editor test with an int free attribute: set "42", save, assert stored int 42 and clean form.

### GUIP-05 Editor save writes the parents first; a later failure leaves a half-saved item with a misleading message
- Where: editor.py:426-450 (`save`: `set_parents` then `update_item`)
- Severity: medium
- Confidence: verified
- What is wrong: parents and attribute/text changes are two independent writes (two history entries). If the second fails (invalid date, control character, type error) the first is already on disk, but the message names only the second problem and the editor still shows everything as unsaved.
- Evidence: `p_ed1.py`: VER-0001, parents `SYS-0001` and `executed_on = "next tuesday"`: `save -> False | 'executed_on' must be a date written YYYY-MM-DD; got 'next tuesday'.`; afterwards `links on disk now: ('SYS-0001',)`, editor still dirty.
- Why it matters: silent partial commit of a traceability change (and, on a baselined item, a consumed reason).
- Proposed fix: validate everything before writing (one all-or-nothing EditService call), or reload/mark the part that succeeded and say so.
- Test that would catch it: change parents plus an invalid date; assert the item file is unchanged after the failed save.

### GUIP-06 Change request with a status the configuration does not know: the form shows another request's status and Save rewrites it
- Where: changes_view.py:154-168 (`_load`: `status.setCurrentText(cr.status)` is a no-op for unknown text), 200-221 (`save`)
- Severity: medium
- Confidence: verified
- What is wrong: `setCurrentText` on a non-editable combo ignores unknown text, so the combo keeps the previously shown request's status. `save()` compares `status.currentText()` with the stored status and calls `set_status` with the wrong one even when only the title changed.
- Evidence: `p_cr2.py`: CR-0001 closed, CR-0002 file `status: opne`. Select CR-0001 then CR-0002: combo shows `closed`; edit title, Save -> `success Saved CR-0002.`, file now `status: closed`. Core treats an undefined status as open (it blocks baselines); the title edit closed it.
- Why it matters: the change-control gate is silently opened.
- Proposed fix: add unknown status to the combo (marked "not configured") or set index -1 and skip `set_status` unless the user picked something.
- Test that would catch it: load a CR with an undefined status, change only the title, save, assert status unchanged.

### GUIP-07 Baseline dialog hides change requests with an undefined status that the core gate still counts
- Where: baseline_dialog.py:159 (`c.status in session.cfg.changes.open_statuses`) vs core `ChangeRequestStore.open_requests` (also counts statuses the configuration does not define)
- Severity: medium
- Confidence: verified
- What is wrong: the dialog lists only CRs in `open_statuses`, so a request with a typo status has no deferral row and "Create permanent baseline" is enabled. The background job then fails with the core message, and the dialog offers no way to defer it (and see GUIP-06 for the Changes tab).
- Evidence: `p_cr2.py` A: `baseline dialog lists: [] | create enabled: True`; `create_baseline` -> `OpenChangeRequestsError A baseline cannot be created while change requests are open: CR-0002 (opne). Close them, or defer each one explicitly with a reason.`
- Why it matters: dead end; the message asks for a deferral the dialog cannot make.
- Proposed fix: build the dialog list from `session.store().open_requests()`.
- Test that would catch it: dialog with an undefined-status CR must list it and block Create until deferred.

### GUIP-08 The wizard lets a required choice stay empty; its quality hints do not mention the resulting error
- Where: wizard.py:323-331 (`details_complete` checks only `string`/`text`), wizard.py:377-390 (`findings` via `check_draft`)
- Severity: medium
- Confidence: verified
- What is wrong: the Details page says "Fields marked * are required", but `type` (enum, required) may stay empty and Next/Finish stay enabled. The Review page lists only `RVS-RULE-VERIFY-METHOD-SET`; the created item immediately has an `RVS-ATTR-REQUIRED` error that the draft check never reports (draft checks differ from the real rules). Expert mode instead fills `type` with the first vocabulary value (app.py:1366), so the two modes disagree.
- Evidence: `p_wiz1.py`: title "T", type empty -> `spec attrs {'title': 'T', 'status': 'draft'} findings ['RVS-RULE-VERIFY-METHOD-SET']`; created SYS-0005 has `[('RVS-ATTR-REQUIRED','error'), ('RVS-RULE-VERIFY-METHOD-SET','warning'), ('RVS-TRACE-NO-CHILD','warning')]`.
- Why it matters: guided mode (for occasional users) creates items that begin with an error.
- Proposed fix: gate `details_complete` on every required attribute including enums; report required attributes in `check_draft`.
- Test that would catch it: wizard with `type` empty must not reach Finish, or must show the required-attribute finding.

### GUIP-09 The crash handler has no de-duplication or rate limit (dialog and file storm)
- Where: crash.py:327-356 (`handle_exception`, `install_excepthook`); core diagnostics.py:45-55 (`save_crash_report`)
- Severity: medium
- Confidence: verified
- What is wrong: every unhandled exception opens a modal QMessageBox and writes a new file; an error that repeats on every paint produces one dialog and one file per call. No in-progress flag, no repeat suppression, no cap on the crash folder.
- Evidence: `p_crash.py`: QTableView over a model whose `data()` raises, one repaint -> `dialogs shown for one repaint: 126`, `crash files: 126`. (Report content is fine: exception class and `file:line in function` with program-relative paths or basenames; no message text, no user name.)
- Why it matters: after one unexpected error the program can become unusable and the settings folder fills.
- Proposed fix: one dialog at a time, suppress repeats of the same (type, frames) signature, keep the newest N reports.
- Test that would catch it: call the hook 50 times with one exception; assert one dialog and one file.

### GUIP-10 Unsaved edits are dropped silently when the item disappears from disk
- Where: app.py `_on_loaded` (triggered by session.py:111-116) -> `editor.clear()`
- Severity: medium
- Confidence: verified
- What is wrong: when a refresh no longer contains the open item (`git pull`/checkout removing it, a file deleted by hand) the editor is cleared even when it holds unsaved edits; no message appears.
- Evidence: `p_gone.py`: statement edited (dirty), `EPS-0001.yml` deleted, `session.refresh()` -> `dirty False current None statement: ''`, `notification visible: False`.
- Why it matters: typed text lost without notice in a Git-based workflow.
- Proposed fix: warn naming the item (and keep the text copyable).
- Test that would catch it: dirty editor, external delete, refresh -> a notification is shown.

### GUIP-11 Path validation can raise in a textChanged slot (crash dialog while typing)
- Where: project_dialogs.py:80-83 (`exists/is_dir/iterdir`), export_dialog.py:290-293 (`is_dir`)
- Severity: low
- Confidence: verified
- What is wrong: on Python 3.11-3.13 `Path.is_dir()/exists()` raise `OSError(ENAMETOOLONG)` and `iterdir()` raises PermissionError on an unreadable folder. The validators run on every keystroke, so the exception reaches the "Something unexpected went wrong" dialog.
- Evidence: `p_dlg.py`: `/tmp/` + 300 "a": `errs [('OSError', "[Errno 36] File name too long: ...")]` for NewProjectDialog and for ExportDialog (folder and file case). Also `~/proj` is accepted and would create a folder literally named `~` (no `expanduser`).
- Proposed fix: wrap the filesystem calls in `try/except OSError` and return a sentence; expand `~`.
- Test that would catch it: a 300-character component in both dialogs gives a problem text and no exception.

### GUIP-12 New item dialogs validate less than the service; list separators differ between widgets
- Where: dialogs.py:95,98-110; completion.py:289-298
- Severity: low
- Confidence: verified
- What is wrong: the dialog checks only that the IDs exist. A parent in the same document, or a verification item as the verified target, passes; the dialog closes and the service refuses afterwards (input lost), or the item is created with an `RVS-LINK-KIND` error. Editor fields accept `;` as separator, the dialog and the completer do not; `SYS-0001,S` (no space) gets no completion because suggestions contain `, `.
- Evidence: `p_dlg2.py`: `wrong-doc parent: problem='' ok=True`, then `create -> None | EPS-0001 is in EPS, but the parent document of EPS is SYS...`; verification dialog with `VER-0001`: ok=True, creates VER-0004 with `RVS-LINK-KIND` error; `SYS-0001;SYS-0002` -> "There is no item SYS-0001;SYS-0002"; `p_comp.py`: completer count 0 for `SYS-0001,S`.
- Why it matters: the earlier audit's "dialogs validate before closing" holds only partly.
- Proposed fix: reuse the service's parent rules in `validate`; use `fields.parse_list` everywhere.
- Test that would catch it: same-document parent shows a problem and keeps OK disabled.

### GUIP-13 Contrast of graph edge labels (and unused-by-tests tokens)
- Where: theme.py:211 (`edge_verifies #24a148`), graph_view.py:459-461 (label drawn in the edge colour)
- Severity: low
- Confidence: verified (computed)
- What is wrong: the "verifies" label is #24a148 text on #ffffff = 3.35:1 (3.05 on `layer`), below 4.5:1. The contrast tests do not include edge or success tokens. All other pairs actually used pass (text_secondary on border 5.9, link on layer 4.55, warning_text on layer 4.53, diff_ins/del on layer 4.56/4.55), several with almost no margin; the dark theme passes everywhere used. Reading-only: `AcronymHighlighter` takes its underline colour once and is not restyled on a theme switch (`editor.restyle` only touches the help line).
- Evidence: `p_theme.py` contrast table (light): `edge_verifies/background 3.35`, `support_success/background 3.35`.
- Proposed fix: darker green for text (for example #198038) or draw the label in `text_secondary`.
- Test that would catch it: add the edge tokens to the contrast test.

### GUIP-14 Tree expansion and Problems sort are reset on every save
- Where: doctree.py:152-179 (`populate`: `model.clear()`, `expandToDepth(0)`), problems.py:127 (`sortByColumn(0)` in `set_findings`)
- Severity: low
- Confidence: verified
- Evidence: `p_ui.py`: expanded `{'SYS': True, 'EPS': True, 'VER': True}` -> after one save `VER: False`; problems sort section 3 -> 0.
- Proposed fix: remember expanded prefixes and the sort indicator across refreshes.
- Test that would catch it: expand a document, save, assert still expanded.

### GUIP-15 Table sorting and search quirks
- Where: models.py:152-155 (`SORT_ROLE` strings), models.py:214 (`item.attrs.get('title','')` in an f-string)
- Severity: low
- Confidence: verified
- What is wrong: sorting is case-sensitive (`Zulu` before `apple battery`); `title: null` puts the word "None" into the search text, so searching "none" finds that item.
- Evidence: `p_models.py`: `sorted titles asc: [..., 'Payload power', 'Zulu', 'apple battery']`; `search 'none' rows: ['EPS-0001']`.
- Proposed fix: `setSortCaseSensitivity(CaseInsensitive)`; `or ''` in the haystack.
- Test that would catch it: sort test with mixed-case titles (the existing test compares with Python's `sorted`, which has the same bias).

### GUIP-16 Glossary and change-request writes are not paused while a baseline is created
- Where: glossary_dialog.py:179-195, changes_view.py create/save versus session `begin_busy`
- Severity: low
- Confidence: verified
- What is wrong: item edits are refused while `session.busy`, but saving the glossary (config/glossary.yaml) and creating or editing a change request (the input of the baseline gate) proceed. The glossary also accepts `Ab` and `AB` as separate acronyms and only complains at Save (`add_acronym` is case-sensitive, `problems` is not).
- Evidence: `p_gone.py`: `glossary save while busy -> True`, `CR create while busy -> CR-0001`, `problems: ["Acronyms, row 4: 'AB' appears more than once."]`.
- Proposed fix: check `session.busy` in both; one case rule.
- Test that would catch it: `begin_busy` then glossary save must refuse.

### GUIP-17 Background jobs: callbacks into deleted widgets; use from a non-GUI thread
- Where: jobs.py:246-275, 328-335
- Severity: low
- Confidence: verified
- What is wrong: a callback touching a widget destroyed meanwhile raises `RuntimeError: Internal C++ object already deleted` in the slot and ends in the crash dialog. `run_in_background` called from a non-GUI thread never delivers its callbacks, keeps the entry in `_alive` forever and leaves the switch interval at 0.1 ms for the session. (Everything else holds, see below.)
- Evidence: `p_jobs.py`: case 4 `RuntimeError libshiboken: Internal C++ object (PySide6.QtWidgets.QLabel) already deleted.`; case 7 `from worker thread: []`, `final interval 9.999999999999999e-05`.
- Proposed fix: guard callbacks with `shiboken6.isValid`; document/assert GUI-thread use.
- Test that would catch it: delete the widget before the job finishes; no excepthook call.

### GUIP-18 Test gaps: five of seven mutations in the slice survive
- Where: tests for help_viewer.py, diff_view.py, session.py, wizard.py, editor.py
- Severity: medium
- Confidence: verified (mutations on a copy of src in scratch; repo untouched)
- Evidence (mutation -> relevant test files):
  - help_viewer `_clicked` navigates to every URL (external links no longer blocked) -> 68 passed (test_gui_usability, test_audit_gui_dialogs, test_gui_theme, test_guide, test_offline). No test clicks a link in the help viewer.
  - diff_view `_marked` without `html.escape` -> 78 passed (test_gui_changecontrol, test_audit_gui_editor, test_review_gui).
  - session `end_busy` no longer runs the postponed refresh -> 76 passed.
  - wizard `where_complete` always True (Next without a parent) -> 79 passed.
  - editor preview `setOpenLinks(True)` -> 56 passed.
  - Caught: jobs.py switch interval not restored (test_small_findings); changes_view save without `set_status` (test_gui_changecontrol).
  - Uncovered, found by this audit: non-string attribute types in the form (GUIP-04), out-of-vocabulary values (GUIP-02), partial save (GUIP-05), Markdown images and rich tooltips (GUIP-01), repeated crash hook (GUIP-09), CR with undefined status (GUIP-06/07). `test_text_has_aa_contrast_on_every_surface` covers 16 pairs.
- Proposed fix: add the tests named in the findings above.

### GUIP-19 Smaller points (low)
- BaselinesView.verify (baselines_view.py:415-428) runs on the GUI thread: 0.76 s on satellite300, 1.05 s on a 1,000-item project (verified), so about 5 s frozen at 5,000 items (extrapolated). `done()` refreshes twice (`end_busy` already runs a postponed refresh; reading-only).
- DiffView/MatrixView `failed()` use `exc.strerror`, `None` for an OSError without errno ("could not be written: None", reading-only). ExportDialog accepts a path with an embedded NUL (`validate` returns '', verified); the write then fails with a different text.
- DiffView export with a typed name without extension says "'.' is not a supported format" (reading-only).
- NewBaselineDialog shows change request titles in a QCheckBox: an `&` becomes a mnemonic (cosmetic, reading-only).
- Wizard reads `int(params.get("min_length", 2))`, `set(params.get("ignore", []))` unguarded while the editor guards types and `params: null` (wizard.py:138-141; whether the schema forbids it was not checked).
- Statement preview is rebuilt for the whole text on each keystroke: 200k characters = 0.39 s, 1M = 1.9 s per keystroke (verified; unrealistic sizes).

## Checked and found correct
- Markdown preview: `setOpenLinks(False)`/`setOpenExternalLinks(False)`; http(s) images, raw `<img>`, `<script>` do nothing (no fetch); only local-file images load (GUIP-01).
- Help viewer: http, https, mailto, ftp, javascript links ignored; fragments navigate inside the guide; the guide has no non-fragment links; `show_section` anchors work.
- InlineNotification and the diff detail escape item text and field names; baselines/changes tables use plain model text; graph nodes use plain QGraphicsSimpleTextItem.
- Reason-for-change cannot be bypassed from the GUI: editor save, set_parents, clear_suspect and the table inline edit all reach `require_reason` (whitespace-only reasons are refused); a refused save leaves the file byte-identical; cancelling the inline reason prompt changes nothing.
- Edit-then-switch: `select_item` refuses with a message when dirty and the selection snaps back; Revert asks first.
- V29 in the editor: only changed fields are written, so an external change to another field survives (verified); same-field concurrent edits are overwritten silently (documented). The editor reloads from disk after a successful save.
- Jobs: Exception, SystemExit and KeyboardInterrupt in a worker are reported through `failed`; the switch interval is restored after normal, failing and callback-raising jobs; 300 jobs in 0.03 s, no residue.
- Session: 80 refreshes keep RSS flat (89.6 -> 91.6 MB); external edit and delete are seen on the next refresh; a failed re-read keeps the old data and emits `load_failed`.
- Graph: 2,000 neighbours lay out and draw in 0.37 s (one row 440,000 px wide, tiny after fit-to-view, no hang); self loops skipped; BFS cannot loop on cycles.
- Models: setData rejects out-of-vocabulary and NUL input with the service's message; 100,000-character titles accepted; sort by problems is numeric.
- Crash report content: exception class, version, time, `file:line in function` with program-relative or basename paths; no message text, no home directory name (spec rule 11 holds); written to the user config folder.
- Theme: both stylesheets parse without Qt warnings; light and dark token sets match; IBM Plex fonts register (incl. SemiBold style) with glyphs for → — · × … ≥ ≤ ± µ Ω ° Greek and Cyrillic; both OFL texts ship with the fonts.
- Accessibility: every input/table has an accessible name; the notification close button is named; in-editor Tab order is fields, parents, statement, reason, buttons; main window minimum size hint 300x232.
- Wizard: five pages, Back keeps ticked parents, Cancel asks when input exists, root documents need no parent, an empty parent document is explained, live checks cost about 1 ms at 1,000 items.
- Baseline dialog (name rule, reason, permanent note, git option) and import dialog (reads baselines once) behave as documented.
- Targeted tests: 72 + 114 pass.

## Questions about intended behaviour
1. Should the Markdown preview load local images at all? (Nothing in the guide mentions images.) If yes, restrict to the project folder with a size cap.
2. Is an editor field for an `int` free attribute meant to work (the schema allows it), or should the schema drop `int` for free attributes?
3. Should a required enum left empty behave the same in expert mode (dialog fills the first value) and guided mode (wizard leaves it empty)?
4. The item cache identifies a file by (mtime_ns, size); an in-place edit with identical size and a restored mtime is not seen by `refresh()` (verified: `same-size edit, mtime preserved: visible? False`). Core cache is outside my slice and the case is contrived; flagging for the core auditor.
5. `help_viewer._clicked` follows any `file://` URL (`file:///etc/passwd` loads in the viewer). The guide has no such link; acceptable, or restrict to the guide file?


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
