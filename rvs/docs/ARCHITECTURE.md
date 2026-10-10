# Architecture

This file started as the design proposal reviewed before M0. It now describes the system **as built** (version 0.1.0); where the proposal was changed the old idea is named, and anything that was proposed but not built is marked *not implemented*. Decisions are in `DECISIONS.md`, deviations from Doorstop and known limits in `DEVIATIONS.md`.

## 1. Layout (as built)

```
rvs/
  pyproject.toml            # runtime deps only; dev tooling under [project.optional-dependencies] dev
  src/rvs_core/             # no GUI, no network imports
    adapter/                # ONLY module importing doorstop: tree load/save, links/suspect stamps, fingerprints,
                            #   the item cache (cache.py), the offline guard (_offline_guard.py)
    config/                 # loaders, dataclasses, defaults/*.yaml and schemas/*.json (validated with fastjsonschema)
    schema/                 # rvs_schema_version handling: in-memory migration of older files, refusal of newer ones
    rules/                  # quality rules engine (engine.py) and the draft check used by the wizard (draft.py)
    trace/                  # LinkGraph, link validation, impact, neighbourhood, coverage, verification status
    matrices/               # MatrixTable, Provenance, traceability, VCM, coverage/impact tables, CSV/JSON rendering
    changecontrol/          # change requests, baselines (manifests, tags), diff, manifest helpers
    vcs/git.py              # the only dulwich user: commit a directory, annotated tags, read a tree
    exporters/              # neutral Doc model + html/docx/pdf renderers, xlsx tables, items CSV/XLSX
                            #   (itemsio), ReqIF (reqif.py), export_request.py, catalog.py, mdlite.py, fonts/
    examples/               # generators for the fictional example projects
    authoring.py            # EditService: create/update/set parents/clear suspect, history, reasons
    atomicio.py             # whole-file-or-nothing writes; validate.py; diagnostics.py (selftest, manifest, crash
                            #   reports); userconfig.py; project_templates.py; glossary.py; guide.py; textcheck.py
  src/rvs_cli/              # `rvs` (argparse; thin over core): main.py, changecontrol.py (baseline/cr/diff), output.py
  src/rvs_gui/              # PySide6: app.py (MainWindow), session.py (ProjectSession), models, editor, wizard,
                            #   matrix/graph/changes/baselines/diff views, dialogs, theme.py, jobs.py, shortcuts.py
  tests/  examples/{minimal10,satellite300}/  docs/  packaging/  scripts/
```
Dependency rule: `rvs_gui -> rvs_core <- rvs_cli`, only `rvs_core/adapter` imports `doorstop`, only `rvs_core/vcs` imports `dulwich`, and no `rvs_*` package imports a network-capable module. The proposal said an *import-linter* test; it is enforced by `tests/test_layering.py`, which walks the AST of every source file (import-linter is not used and is not a dependency). The 5,000-item stress project is generated on demand (`scripts/gen_stress.py`), not committed.

## 2. Stack comparison

| Option | Pros | Cons |
| --- | --- | --- |
| **PySide6 + PyInstaller (chosen)** | Matches earlier tools; LGPL; one language with Doorstop; good tables (QTableView, 5k rows fine); no admin install | Carbon look must be hand-built in QSS; bundle of about 180 MB (77 MB archive) |
| PySide6 + QtWebEngine/web UI (React+Carbon) | Real Carbon components | Chromium bundle, sandbox issues on locked-down hosts, JS toolchain, two languages |
| Electron/Tauri + Python sidecar | Rich UI | Needs sidecar IPC (local port → conflicts with "no network"), heavier packaging |

Decision: PySide6 widgets, Carbon design tokens (colours, spacing, type scale) in a bundled QSS, IBM Plex bundled. Markdown preview via `QTextBrowser` with python-markdown (no WebEngine). Monaco is not used (rule 20 avoided).

## 3. Data model and file format

A project is a Doorstop tree plus RVS files:
```
project/
  <PREFIX>/.doorstop.yml    # one per document: prefix, parent, digits, sep, defaults, fingerprint ("reviewed") attributes
  <PREFIX>/<PREFIX>-0001.yml  # one per item
  rvs-project.yaml          # rvs_schema_version, project name, documents (prefix, kind, title, parent), free attributes
  config/{numbering,vocab,templates,rules,links,exports,standards,glossary,changes}.yaml  (schemas ship in the app)
  baselines/<name>.yaml     # manifest, immutable
  changes/CR-0001.yaml      # change requests
  history/<PREFIX>/<UID>.jsonl   # per-item edit history: who, when, why, action, changed field names
  .rvs-cache/               # disposable item cache and baseline snapshots (git-ignored, invisible to Doorstop)
```
- Every RVS-owned YAML has `rvs_schema_version: <int>`; items carry it as an extended attribute. Older -> migrate in memory and on explicit save; newer -> error naming file, found/supported version.
- Item extended attributes: `title, rationale, type, priority, status, owner, source, standard_clause, verify_method, verify_level` (requirements); `proc_id, verify_method, verify_level, v_status, evidence, executed_on, responsible, nonconformances` (verification items); typed links `link_satisfies|refines|conflicts|refs` on requirements and `link_verifies` on verification items (D13, D37).
- Fingerprints: the document's "reviewed" attributes are `title, type, verify_method, verify_level` (requirements) and `title, verify_method, verify_level` (verification), plus Doorstop's own text; `status`, `owner`, `priority` are excluded so status changes don't create suspect links. Only parent links carry stamps.
- **Edits are recorded in the history JSONL files** (D29), not in Git commit trailers as the proposal said. The files hold field names, never values; Git history of the item files holds the values.
- Determinism: stable key order, sorted link lists, no timestamps in item files; IDs allocated by Doorstop sequence. Dates (execution date) are user data; the generation time of an output comes from `Provenance`, which honours `SOURCE_DATE_EPOCH`.
- Writes go through Doorstop's API (with two run-time patches, DEVIATIONS V26) and `atomicio`; Doorstop's own review stamps are not used.

## 4. Key components (as built)

- **Adapter**: `DoorstopProject.open(path)` -> immutable `ItemData` snapshots and a write API; lazy loading, a one-pass index (UID, parents, children, typed-link reverse index), and a per-document item cache in `.rvs-cache/` keyed by (mtime, size) and signed with a per-user key (so a cache copied from elsewhere is ignored).
- **Rules engine**: eight rules in `rules.yaml` (`shall-present`, `single-statement`, `vague-words`, `no-implementation`, `verify-method-set`, `has-parent`, `verified-when-approved`, `undefined-acronym`); each yields `Finding(code, severity, message, hint, location, uid)`. Link validation, suspect links and baseline/CR checks produce `RVS-LINK-*`, `RVS-CR-*` and `RVS-BASELINE-*` findings through `validate_project`.
- **Matrices**: pure functions over the index produce a `MatrixTable`; every renderer (GUI tables, CSV/JSON, XLSX, HTML, DOCX, PDF) draws that one model. 30 outputs of the two reference projects are listed in `exporters/catalog.py` and hashed in the golden tests.
- **Change control**: change requests are files (`changes/`); baselines are a manifest of item digests plus one commit of the project folder and an annotated tag (D56); a baseline is refused while a blocking CR exists unless it is deferred with a reason; diff compares snapshots extracted from the tagged commits (word-level text diff via `difflib`).
- **Provenance**: header block on every output from `matrices/provenance.py` (project, baseline, generated date and time, user from the OS login, tool and Doorstop version).
- **Offline/privacy**: no network-capable module is imported (offline test, `_offline_guard.py`); Doorstop's logger is silenced so item text never reaches a log; crash reports hold the exception type and program locations only. *Not implemented, as the proposal said:* a scrubbing logger (there is no application logging at all) and a temporary folder forced to `<project>/.rvs-tmp` (temporary files are written next to their targets instead, DEVIATIONS V06).
- **GUI**: `MainWindow` with document tree, item table (column chooser, filters, `QSortFilterProxyModel`), editor (form generated from `templates.yaml`, Markdown preview), Problems dock, matrix tabs, impact dock, a graph view (QGraphicsView with an own layered layout, no graphviz), Changes/Baselines/Diff tabs. Guided vs expert mode is a UI flag over the same core.

## 5. Dependencies (runtime, pinned in `pyproject.toml`)
`doorstop==3.2`, `PySide6-Essentials` (not the `PySide6` meta package: no WebEngine), `PyYAML`, `fastjsonschema` (pure Python; `jsonschema` needs the compiled `rpds-py`, D20), `python-docx`, `reportlab` (pure-Python PDF; WeasyPrint rejected: needs Pango/Cairo system libs), `openpyxl`, `Markdown`, `dulwich` (pure-Python Git, D17). There is no `platformdirs` (the per-user folder is computed in `userconfig.py`) and no `jsonschema`. Dev only: pytest, pytest-qt, hypothesis, mypy, ruff, pyinstaller, cyclonedx-bom, pip-licenses, pip-audit, build, pypdf, fonttools. A wheelhouse (`scripts/build_wheelhouse.sh`) allows offline installs; no hashed lock file yet (DEVIATIONS V27).

## 5a. As built in M1
- `rvs-project.yaml` declares documents/kinds (D21); the Doorstop tree has a single root, so VER is a child of SYS (V07).
- `rvs_core.validate.validate_project` = config load + schema versions + RVS hooks (documents, items) + Doorstop's own validation, all read-only (V09). Findings carry code, severity, message, hint, location, uid.
- Performance spike (5,000 items): open 0.01 s (lazy), read all 4.4 s, full validate 15.6 s, build 62 s. Target (open < 3 s) needed the index cache (D27) in M3.

## 5b. As built in M2
- `rvs_core.rules` (8 rules, config-driven), `rvs_core.glossary`, `rvs_core.authoring.EditService` (create/update/set_parents + history), `rvs_core.examples.satellite`.
- `rvs_gui`: `ProjectSession` -> models (`ItemTableModel`/`ItemFilterProxy`/`FindingsModel`) -> widgets (`DocumentTree`, `RequirementEditor`, `ProblemsPanel`, `InlineNotification`) -> `MainWindow`. The editor form is generated from `config/templates.yaml`, so project-specific free attributes appear without code changes.
- Strict offline guard (`adapter/_offline_guard.py`, DEVIATIONS V01).

## 5c. As built in M3
- `rvs_core.trace`: `LinkGraph` (parent + typed links, config/links.yaml), link validation, `impact`, `neighbourhood`, `coverage`, `aggregate_status`. `rvs_core.matrices`: `MatrixTable` + `Provenance` (+ CSV/JSON rendering) for traceability, VCM, coverage and impact; everything the GUI tabs and `rvs export` show comes from these.
- `rvs_core.adapter.cache`: per-document item cache (D43). `ItemData` carries `stamp` and `link_stamps`, so suspect links are computed from snapshots.
- GUI: tabs Items / Traceability / VCM / Coverage / Graph, Impact dock, "Clear suspect links", New Verification Item. `ProjectSession` reuses the validation report's items, docs and graph (no second load).
- Measured at 5,000 items (original M3 figures): warm open + rules + links 0.4 s; graph + VCM + trace + coverage 0.04 s; cold open 6.0 s (V14; since improved by D75).

## 5d. As built in M4
- `rvs_core.exporters`: `model` (neutral Doc) + `builders` (matrix_doc, spec_doc) -> `html_out`, `docx_out`, `pdf_out`; `xlsx_out` (tables); `itemsio` (item table CSV/XLSX export, `read_csv`/`read_xlsx`, `plan_import` -> `apply_import`); `export_request` (ExportRequest/build_output); `catalog` (all outputs, for golden tests); `zipnorm`; `mdlite`.
- Offline: the offline test runs all 30 outputs of a project with sockets blocked (29 after M4, plus `project.reqif`). Fonts: 4 TTF (PDF) and 4 subset WOFF (HTML) in `exporters/fonts`.
- GUI: File > Export… / Import Items…, an export button on each matrix tab (format by file extension), background `jobs`.
- Measured at 5,000 items: items CSV 0.1 s, XLSX export 2.1 s, import plan 0.2 s, VCM xlsx/pdf/docx 0.5/3.6/6.1 s, spec html/pdf/docx 0.1/9.1/23 s (background thread; the DOCX and PDF writers were made linear / chunked in the audit pass, see `AUDIT.md`).

## 5e. As built in M5
- `rvs_core.vcs.git`: the only dulwich user (commit a directory, annotated tags, read a tree at a commit). `rvs_core.changecontrol`: `manifests` (light helpers), `changes` (CR store + validation), `baselines` (create/list/verify/snapshot), `diff` (snapshots, field/word diff, `diff_doc`/`diff_table`).
- Config: `config/changes.yaml`. Files: `baselines/*.yaml`, `changes/CR-*.yaml`, `history/**.jsonl`. Validation adds `RVS-CR-*` and `RVS-BASELINE-*` findings.
- GUI tabs Changes / Baselines / Diff; New Baseline dialog; `ProjectSession.active_cr`; baseline creation, comparison and diff export run on worker threads.
- Measured at 5,000 items: baseline create 7.9 s, deep verify (cold) 7.2 s, load a baseline snapshot 0.6 s, diff 0.1 s.

## 5f. As built in M6
- GUI: `wizard` (NewRequirementWizard -> RequirementSpec), `fields` (shared attribute widgets), `completion`, `shortcuts`, `glossary_dialog`, `project_dialogs`, `help_viewer`, `crash`; `MainWindow` gained modes, inline editing (`ItemTableModel.setData` + `EnumDelegate`), go-to / next problem, recent projects, new project, examples, async open.
- Core: `userconfig`, `project_templates`, `rules/draft`, `diagnostics` (crash report, selftest, manifest), `guide`.
- Release: `scripts/build_guide.py`, `build_release.sh`, `make_manifest.py`; `packaging/install-*.sh|ps1`.

## 5g. As built after v1
- **ReqIF** (`exporters/reqif.py`, standard-library XML only, D73): export writes one specification per document, one object per item and relations for parent and typed links; the statement is carried as XHTML and as lossless Markdown. The header declares ReqIF 1.0 and the element order follows 1.2; it could not be validated against the official XSD offline (V16). Import converts the file to the same rows as the CSV/XLSX import and goes through `plan_import`, so dry run, checks, history and reasons are shared. DOCTYPE and entity declarations are refused.
- **Themes** (`rvs_gui/theme.py`, D74): `LIGHT` and `DARK` token dictionaries (Carbon white and g100) with the same 26 tokens; the stylesheet is generated from the active tokens and switched at run time (light, dark, follow the system, remembered in `settings.json`); tests check token parity and WCAG AA contrast.
- **Jobs** (`rvs_gui/jobs.py`, D53): `run_in_background` runs exports, baseline creation, comparisons and project opening on a worker thread and delivers the result on the GUI thread; while any job runs the interpreter switch interval is lowered so the GUI stays responsive (V17).
- **Faster cold open** (D75): libyaml's C parser for Doorstop's reads, plus a run-time patch for atomic item writes (V26).
- **Atomic writes** (`atomicio.py`) and a signed cache (per-user key in the settings folder) came from the review passes (D79-D83).

## 6. Risks (original list, with outcome)
1. Doorstop's transitive network libs vs. offline test -> resolved strictly (V01).
2. Doorstop load time at 5,000 items -> index cache and libyaml (D27, D43, D75).
3. Carbon fidelity in Qt widgets -> limited to tokens, tables, forms, notifications.
4. Git availability on locked-down hosts -> bundled `dulwich` (D17, V20).
5. New: the Linux bundle depends on the build machine's glibc and on system Qt libraries (V28); Windows has never been run (V22, V25).
