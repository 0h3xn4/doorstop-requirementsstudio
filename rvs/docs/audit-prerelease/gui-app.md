# Pre-release audit: GUI main window

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

All probe scripts are in <scratch>/gui-app/ (p1.py ... p31.py, run with devvenv python, QT_QPA_PLATFORM=offscreen, `S=<that dir>` env var). Machine load average was 6-7 on 4 cores during all timings.
Note on method: QTest.qWait holds the GIL, so timings of worker threads measured under qWait are wrong (10x slower); I re-measured under a real app.exec() and only report those.

## Coverage
Files read in full: src/rvs_gui/app.py (all 1,399 lines), shortcuts.py, __init__.py, plus jobs.py, session.py, crash.py, rvs_core/userconfig.py, doctree.py, models.py (filter proxy), baselines_view.create_baseline (to judge app.py interactions); docs/AUDIT.md, CLAUDE.md.
Probes run (one line each):
- p1 action enabled state: no project / project / busy; slots called with no project.
- p2 edit during background full validation (stale result adopted).
- p3 close window during background job. p4 open other project while baseline job runs.
- p5/p6/p6b recent projects: duplicates, relative, EACCES, ENAMETOOLONG, garbage, 500 entries; MainWindow() / main() with such settings.
- p7/p28/p29/p30 settings.json geometry/layout/header: corrupt, truncated, huge, off-screen, dock state, sort state.
- p8 column chooser persistence. p9 shortcuts with real key events (modal open, typing in search/editor, collisions).
- p10 document filter after refresh / project switch. p11-p16, p23 5,000-item project (scripts/gen_stress.py): open, filter, sort, save, refresh, navigation.
- p17 async/sync open of bad paths. p18 excepthook wiring. p19 signal connection counts after 6 reopen cycles. p20 closeEvent with real QMessageBox (Esc/Enter).
- p21 expert-mode in-place edit, mode toggle with open cell editor. p22 theme switching incl. help viewer. p24 create_project edge inputs. p25 open_example. p26 import plan applied after project switch. p27 bulk import time. p31 close with unsaved edit while busy.
Tests run: tests/test_gui_smoke, test_gui_modes, test_gui_io, test_gui_usability, test_review_gui, test_audit_gui_keyboard, test_audit_gui_layout, test_audit_gui_dialogs against an unmodified copy of src: all pass (1m29s). Mutation probes: see "Test judging" at the end.

## Findings
### GUIAPP-01 Finished full validation overwrites the session with a stale snapshot; later saves lose the user's earlier edit
- Where: src/rvs_gui/app.py:846-877 (run_full_validation.done), session.py:102-104 (adopt_validation/_apply)
- Severity: high
- Confidence: verified (reproduced)
- What is wrong: `done()` only checks that the project root is unchanged. It then adopts a report that was computed from the files as they were when validation started. Edits saved in the meantime (editor Save, in-place edit, import, new item) are on disk, but the GUI items/editor are reloaded from the old report. The editor then shows the OLD text (not dirty), and the next save writes old text + new change over the saved edit, with no warning.
- Evidence: p2.py on a copy of satellite300: start run_full_validation, wait until the worker has finished reading, `session.update_item("MIS-0006", text="EDITED WHILE VALIDATING")`, let the job finish. Output: `after edit: EDITED WHILE VALIDATING` then `after validation adopt: 'The mission shall return at least 600 GB'`, editor statement shows the old text; typing " PLUS SECOND EDIT" and saving gives on disk `'The mission shall return at least 600 GB of payload data per day. PLUS SECOND ED...'` - the first edit is gone. Full validation takes 45 s on the 5,000-item project (p11), so the window is long.
- Why it matters: silent loss of a saved requirement edit (data loss) in a normal workflow (run validation, keep working).
- Proposed fix: remember a project "generation" counter incremented by every session._load/edit; in done() discard (or re-run `session.refresh()` and only copy the Doorstop findings) if the generation changed. Simplest: on done, call refresh() and merge only the findings from the full report; or refuse edits while `_validating`.
- Test that would catch it: start validation with a patched slow full_validation_report, edit an item, wait for validation_finished, assert session.item(uid).text is the edited text.

### GUIAPP-02 A project open that completes while a modal dialog is open switches the project under the dialog; the dialog's result is then applied to the NEW project
- Where: src/rvs_gui/app.py:513-546 (open_project_async), 462-476 (_update_action_states does not look at `_opening`), 744-763 (import_items_dialog), 698-710, 1254-1276 (other dialogs)
- Severity: high
- Confidence: verified (reproduced for Import; reading-only for the wizard/new item/export dialogs, same mechanism)
- What is wrong: during an async open the menu stays enabled for the old project. If the user opens Import (or New Requirement, Export...) before `done()` fires, the open finishes inside the dialog's nested event loop and `session.adopt` replaces the project. When the dialog is accepted, `apply_import(dlg.plan, ...)` runs on `self.session.root`, which is now the other project, with a plan that was computed against the first one.
- Evidence: p26.py: project A=minimal10 copy, B=satellite300 copy, both have EPS-0001. ImportDialog on A with a row retitling EPS-0001; while it is open `open_project_async(B)` completes; accept -> `applying plan made for A on imB`, `Imported: 0 created, 1 updated`, and B's EPS-0001 title changed from `Bus voltage 24 #1` to `PLANNED AGAINST PROJECT A`.
- Why it matters: silent writes to the wrong project. Real window: opening a large project takes seconds (up to tens of seconds cold); the menu still looks usable.
- Proposed fix: disable all project actions (and Open Recent/Open) while `_opening`; and in every dialog flow remember `session.root` before `exec()` and refuse to apply if it differs afterwards.
- Test that would catch it: open B asynchronously with a slow open_report while the Import dialog is exec'd; assert nothing is written to B (or that the actions are disabled while `_opening`).

### GUIAPP-03 One unreadable/odd entry in the recent-projects list makes the application impossible to start
- Where: src/rvs_gui/app.py:583-590 (_refresh_recent, called from _build_menus at :370 in the constructor); rvs_core/userconfig.py:91-92
- Severity: high
- Confidence: verified (reproduced; EACCES case with a monkeypatched os.stat because the sandbox runs as root)
- What is wrong: `[p for p in recent_projects() if p.is_dir()]`. `Path.is_dir()` swallows only ENOENT/ENOTDIR/EBADF/ELOOP; EACCES, ENAMETOOLONG, ENOTCONN (dead FUSE/network mount), EIO propagate. The exception escapes `MainWindow.__init__`, `main()` has no guard, so every launch ends in the crash dialog until the user hand-edits settings.json (which the dialog does not mention).
- Evidence: p6.py: settings.json `{"recent":["/home/xxxxxxxx...(300 x)/proj"]}` -> `MainWindow() RAISED: OSError [Errno 36] File name too long`. p6b.py: os.stat raising PermissionError for the entry -> `main RAISED PermissionError [Errno 13] Permission denied`.
- Why it matters: cannot start; plausible with a recent project on a removable disk / network share / revoked folder.
- Proposed fix: wrap the check in try/except OSError (treat as not available) - e.g. a small `_is_dir(p)` helper; also cap the list to MAX_RECENT when loading.
- Test that would catch it: monkeypatch os.stat/Path.is_dir to raise PermissionError for a recent entry and construct MainWindow.

### GUIAPP-04 A document filter from the tree survives a refresh or project switch invisibly; the empty-state message blames the wrong thing
- Where: src/rvs_gui/app.py:660-682 (_on_loaded), doctree.py:27-31 (populate clears the model), models.py (ItemFilterProxy._document never reset)
- Severity: medium
- Confidence: verified
- What is wrong: `doc_tree.populate()` clears the tree (selection lost) but `table_proxy._document` keeps the prefix. After any edit/F5 the table is still filtered to that document while no tree node is highlighted. After opening another project that lacks the prefix the table shows 0 rows with the text "No items match the search or filters. Clear the search, or choose All statuses." (neither search nor status is set).
- Evidence: p10.py: open satellite300, select tree node AOCS (40 rows), `session.refresh()` -> `rows 40 tree current None`; open minimal10 -> `rows 0 model rows 10 no_match visible True ... doc filter AOCS`.
- Why it matters: a freshly opened project looks empty; user is told to clear search/status, which does nothing (they must click "All items").
- Proposed fix: in `_on_loaded` re-select the tree node of the active document filter (or reset the filter when the prefix is gone / when the root changed), and mention the document in the empty message.
- Test that would catch it: open a project, select a document, open a project without it, assert rows == model rows.

### GUIAPP-05 The column chooser selection is saved but never restored
- Where: src/rvs_gui/app.py:486-490 (_apply_column_visibility), :1167-1175 (_restore_geometry restores the header state incl. hidden sections), :1247-1250
- Severity: medium (low impact, but docs/AUDIT.md claim layout is remembered)
- Confidence: verified
- What is wrong: header.saveState() stores which columns are hidden; restoreState applies it, but the View > Columns check marks are not synced, and `_apply_column_visibility()` (called on every project load) re-hides/shows columns from the check marks (defaults). So the chosen columns reappear as the defaults as soon as a project loads, and the menu check marks are wrong before that.
- Evidence: p8.py: show Priority, hide Owner, close, restart: before open `visible: [..priority..]` but menu checks `[..owner..]`; after open `[..owner..]` again.
- Proposed fix: after restoring the header state, set each column action's checked state from `not header.isSectionHidden(col)` (or store visibility separately).
- Test that would catch it: toggle a column, close, new window, open project, assert column state.

### GUIAPP-06 Opening another project (or creating/opening an example) is allowed while a baseline is being created; the success message then names the wrong project
- Where: src/rvs_gui/app.py:504-511, 600-621, 628-649 (no `session.busy` check); baselines_view.py:140-150
- Severity: medium
- Confidence: verified
- What is wrong: `begin_busy` only disables edit actions. Open Project stays enabled; the worker keeps writing the old project, `session.adopt` switches root, `busy` stays True for the new project (its edits refused with "baseline BL-1 is being created"), and on completion "Baseline BL-1 created: 3 items" is shown while another project is displayed.
- Evidence: p4.py: `opened other project while baseline job runs: True sat busy True` ... `after: success Baseline BL-1 created ... sat`.
- Proposed fix: refuse open/new/example (and window close with a confirmation) while `session.busy`.
- Test that would catch it: begin_busy, call open_project, assert refused.

### GUIAPP-07 open_example crashes on an unusual target; builds the satellite example on the GUI thread
- Where: src/rvs_gui/app.py:628-649
- Severity: low
- Confidence: verified
- What is wrong: `target.exists() and any(target.iterdir())` is outside the try/except: a FILE named rvs-example-<key> (or an unreadable folder) raises NotADirectoryError/PermissionError -> crash dialog. Also `build_satellite_project` + open run synchronously: 7.1 s frozen window under load 7 (p25), contradicting "window stays usable" elsewhere.
- Evidence: p25.py: `NotADirectoryError: [Errno 20] Not a directory: '.../ex/afile'` traceback from app.py:638.
- Proposed fix: move the check inside the try (catch OSError); run the builder via run_in_background.

### GUIAPP-08 Crash hook shows a modal dialog per exception with no guard (dialog storm on a repeating error)
- Where: src/rvs_gui/crash.py:13-49 wired at app.py:1393-1395
- Severity: medium
- Confidence: likely (reproduced with the dialog stubbed; not with a real QMessageBox)
- What is wrong: every uncaught exception in a slot/timer/paint calls `QMessageBox.critical` (nested event loop) and writes a crash file. An exception that repeats (a model.data() or paint handler, a timer) opens a new modal each time and nested loops pile up; crash files accumulate (no cap).
- Evidence: p18.py: a 10 ms timer raising ZeroDivisionError for 300 ms -> `repeating timer exceptions -> dialogs: 30`.
- Proposed fix: ignore/queue while a crash dialog is open, rate-limit, and offer "Quit".

### GUIAPP-09 Closing the window during a background job prints a traceback and leaves the process alive until the job ends
- Where: src/rvs_gui/app.py:1235-1251 (closeEvent does not look at running jobs), jobs.py:47-55
- Severity: low
- Confidence: verified
- What is wrong: no warning that an export/validation/baseline is running; the window disappears, the process lingers (4.4 s in p3 for a 3 s job) and then writes `RuntimeError: Signal source has been deleted` from `_Task.run` to stderr. For a running baseline creation the user gets no confirmation that it finished.
- Evidence: p3.py output: `Error calling Python override of QRunnable::run(): ... RuntimeError: Signal source has been deleted`.
- Proposed fix: closeEvent asks while `session.busy`/jobs alive (or waits with a message); catch RuntimeError in `_Task.run`.

### GUIAPP-10 Recent-projects list: no normalisation, no cap on load, relative paths stored
- Where: rvs_core/userconfig.py:86-92, app.py:562, 583-590
- Severity: low
- Confidence: verified
- What is wrong: `add_recent(str(project))` stores the path as given: `m10`, `m10/`, `m10/../m10` and a symlink to it are separate entries (only the first 8 kept); a relative entry depends on the current folder (hidden after `cd /`). A hand-edited list of 500 entries yields a 500-item menu (MAX_RECENT only applied on add).
- Evidence: p5.py: settings recent = [m10link, m10/../m10, m10, 'm10', sat]; menu with 500 identical entries.
- Proposed fix: store `Path(project).resolve()` (or absolute + normpath) and slice to MAX_RECENT in `recent_projects()`.

### GUIAPP-11 `rvs-studio <path>` ignores the path
- Where: src/rvs_gui/app.py:1379-1399 (create_app passes argv to QApplication only)
- Severity: low
- Confidence: verified by reading (documented nowhere; see QUESTIONS)
- What is wrong: the argument is dropped silently; the desktop entry `Exec="%s"` has no %f either, so "open with" does not work. Qt options (-style, -platform) are consumed from argv.

### GUIAPP-12 Some error messages show raw exception/parser text
- Where: app.py:542 (failed), 580 (_open_failure_text), 615 (create_project `str(exc)`), 780
- Severity: low
- Confidence: verified
- Evidence: p17/p24: broken rvs-project.yaml gives `...not valid YAML (while parsing a block mapping\nexpected <block end>, but found ':'\n  in "<unicode string>", line 1, column 1: ...` (multi-line libyaml text in the banner); a file as target of New Project gives `[Errno 20] Not a directory: '/.../np/file'`; a 5,000-char path gives "Validation stopped unexpectedly (OSError)" plus a crash report. Not item text, but not actionable.

### GUIAPP-13 Minor state inconsistencies
- Low, verified: (a) `session.adopt` assigns `self.report = report` before checking for failure, so after a failed open of another project `session.report.exit_code == 3` while the old project is still shown (p17; nothing reads it today). (b) Toggling guided/expert while an in-place cell editor is open leaves it open in guided mode (p21). (c) With no project open, F8/Shift+F8 show a green "No problems to go to." (p1) instead of "Open a project first." (d) `new_project` accepts project names with NUL/newline (title bar) - see NewProjectDialog (other auditor).

### GUIAPP-14 Test gaps in the GUI shell
- Medium, verified by reading: tests/conftest.py `_no_modal_prompts` replaces `ask_unsaved`, `confirm_overwrite`, `confirm_revert` for every test, so the real closeEvent prompt is never exercised (I drove it manually with Esc/Enter in p20: correct). Keyboard tests use `action.trigger()`, never real key events, so shortcut registration (key_for, context, conflicts with a modal) is untested (p9 checked manually: correct). Nothing tests: edits during a background validation, project switch under an open dialog, recent entries raising OSError, column persistence, jobs running at close.

## Checked and found correct
- Action enabled state: no project (only Open/New/Quit/mode/tabs/help enabled), project open, busy (import/new/baseline/save/revert disabled); all slots safe with no project (p1).
- Shortcuts: no duplicate defaults; not delivered to the main window while a modal dialog is open; work from search field and statement editor; Ctrl+S saves from the editor (p9).
- Async open: refuses when a project is already opening or the editor is dirty; failed opens (missing, empty, file, broken YAML, NUL, empty path) leave the previous project open and mention it; busy cursor restored in all paths (p17).
- No signal leaks/double execution after 6 open cycles (receiver counts constant, one `_on_loaded` per refresh); QAction count constant after repeated recent refresh (p19).
- Settings: corrupt/short/non-ASCII/oversized geometry, layout, header values, list/dict mix-ups all fall back cleanly; huge/tiny/off-screen saved geometry is clamped by Qt; dock visibility/floating and header sort state restore correctly (p7, p28-p30).
- closeEvent: dirty editor prompt Esc = cancel (window stays), Enter = save then close; save refused while busy keeps window open with a message (p20, p31).
- Theme switching (light/dark/system) with all tabs and help viewer open, unknown theme/mode raise ValueError before changing state (p22).
- Large project (5,000 items, loaded under load 6-7): worker open_report ~1.1-1.3 s warm; GUI-thread part of open 0.3 s; filter keystroke 0.02-0.06 s; sort 0.25-0.8 s; item selection 0.05-0.09 s; arrow key navigation 13 ms/key; save (sync refresh on GUI thread) 0.8 s; F5 0.75-1.3 s; bulk import of 200 updates 1.65 s. Full Doorstop validation 45 s in the background (window stays responsive when measured with a real event loop).
- create_project rejects non-empty folder, empty name, "."/empty folder, unknown template with plain text; unicode names work.
- Expert-mode in-place edits (title, status combo) save and refresh without re-entrancy problems; edit refused while the editor of that item is dirty.

## Questions about intended behaviour
- Should `rvs-studio <folder>` open that project (GUIAPP-11)? Nothing in the guide promises it.
- Should Open/New/Quit be allowed while a baseline is being created (GUIAPP-06, GUIAPP-09)?
- Is it intended that "Open Example" refuses an existing non-empty folder instead of opening the example already there?
- "Read-only project" (no write permission): not testable here (sandbox runs as root); only reading: edit paths show `exc.strerror` for OSError (app.py:1083) and create paths show str(exc); no up-front read-only indication.

## Test judging (mutation probes on a copy of src in scratch; the 8 listed GUI test files, 139 tests)
Mutations of app.py and result:
- closeEvent: dirty-editor prompt removed -> caught (test_review_gui::test_closing_the_window_also_closes_the_guide_and_asks_about_unsaved_edits).
- open_project_async.done: "editing started meanwhile" check removed -> caught (test_an_async_open_does_not_overwrite_work_started_meanwhile).
- `_refresh_recent` `is_dir()` filter removed -> caught. `userconfig.add_recent` removed -> caught. `_show_selection` filter reset removed -> caught.
- **SURVIVED** run_full_validation.done: the `self.session.root != root` guard ("another project was opened meanwhile") replaced by `False`: all 139 tests pass. The guard that protects against a stale validation result has no test (and GUIAPP-01 shows the neighbouring stale-result case is also untested).
- **SURVIVED** `_update_action_states`: `action_import.setEnabled(have and not busy)` -> `have`: all 139 pass. Import being disabled while a baseline is created is untested.
(GUIAPP-14 lists the structural gaps: real key events, real unsaved prompt, project switch under a dialog.)


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
