# Architecture (proposal — review before M0)

## 1. Layout

```
rvs/
  pyproject.toml            # runtime deps only; dev tooling under [project.optional-dependencies] dev
  src/rvs_core/             # no GUI, no network imports
    adapter/                # ONLY module importing doorstop (tree load/save, review, fingerprints)
    model/                  # dataclasses: Requirement, VerificationItem, Link, Baseline, ChangeRequest
    schema/                 # schema_version, migrations (v1 -> vN), newer-version refusal
    config/                 # loaders + JSON Schemas: rules, numbering, templates, export layouts, standards
    rules/                  # quality rules engine (deterministic, one rule = one config entry id)
    trace/                  # link validation, traceability, impact analysis, coverage
    matrices/               # traceability matrix, VCM
    changecontrol/          # baselines, diff, change requests
    exporters/              # csv, xlsx(openpyxl), docx(python-docx), pdf(ReportLab), html; importers csv/xlsx
    provenance.py           # tool/framework version, baseline, date, user for every output
  src/rvs_cli/              # `rvs validate|export|baseline|diff` (argparse; thin over core)
  src/rvs_gui/              # PySide6, Carbon theme, views, editor, Problems panel
  tests/  examples/{minimal10,satellite300,stress5000}/  docs/  packaging/
```
Dependency rule: `rvs_gui -> rvs_core <- rvs_cli`; enforced by an import-linter test.

## 2. Stack comparison

| Option | Pros | Cons |
| --- | --- | --- |
| **PySide6 + PyInstaller (recommended)** | Matches earlier tools; LGPL; one language with Doorstop; good tables (QTableView, 5k rows fine); no admin install | Carbon look must be hand-built in QSS; ~150 MB bundle |
| PySide6 + QtWebEngine/web UI (React+Carbon) | Real Carbon components | Chromium bundle, sandbox issues on locked-down hosts, JS toolchain, two languages |
| Electron/Tauri + Python sidecar | Rich UI | Needs sidecar IPC (local port → conflicts with "no network"), heavier packaging |

Decision: PySide6 widgets, Carbon design tokens (colours, spacing, type scale) in a bundled QSS, IBM Plex bundled. Markdown preview via `QTextBrowser` with python-markdown (no WebEngine). Monaco is not used (rule 20 avoided).

## 3. Data model and file format

A project is a Doorstop tree plus RVS files:
```
project/
  .doorstop.yml (per document)  *.yml items
  rvs-project.yaml               # schema_version, project name, doc tree, active config
  config/{rules,numbering,templates,exports,standards,glossary}.yaml  (+ *.schema.json shipped in app)
  baselines/<name>.yaml          # manifest, immutable
  changes/CR-0001.yaml           # change requests
```
- Every RVS-owned YAML has `rvs_schema_version: <int>`; items carry it as an extended attribute. Older -> migrate in memory and on explicit save; newer -> error naming file, found/supported version.
- Item extended attributes: `title, rationale, type, priority, status, owner, source, standard_clause, verify_method, verify_level` (requirements); `proc_id, verify_method, verify_level, v_status, evidence, executed_on, responsible, nonconformances` (verification items); typed links `link_satisfies|verifies|refines|conflicts|refs`.
- Fingerprints: only `text`, `title`, `type`, `verify_method`, `verify_level` listed in the document's fingerprint attribute settings; `status`, `owner`, `priority` excluded so status changes don't create suspect links.
- Determinism: stable key order, sorted link lists, no timestamps in files; IDs allocated by Doorstop sequence. Dates (execution date) are user data, not generation time.
- Writes only through Doorstop API; review state only via Doorstop review API.

## 4. Key components

- **Adapter**: `Project.open(path)` -> immutable snapshot objects; a write API with explicit `save(item, reason)`. Lazy loading + one-pass index (UID, parents, children, typed-link reverse index) for the 5,000-item target; cache keyed by file mtime inside the project folder only.
- **Rules engine**: rule ids in `rules.yaml` (`shall-present`, `single-statement`, `vague-words` (word list in config), `no-implementation` (term list in config), `verify-method-set`, `has-parent`, `verified-when-approved`, ...). Each yields `Finding(rule_id, severity, item_uid, message, hint)`. Also covers link validation (unknown target, wrong direction, doc-level mismatch) and suspect links.
- **Matrices**: pure functions over the index -> table model; exporters render the table model (single source for GUI, CLI, XLSX/DOCX/PDF/HTML). VCM columns come from `standards.yaml` with placeholders.
- **Change control**: edits recorded via Git commit with reason trailer; CR files group item UIDs; baseline refuses when open, non-deferred CRs exist; diff compares manifests then item contents (word-level text diff via `difflib`).
- **Provenance**: header block on every export from `provenance.py`; user name from OS login or project config.
- **Offline/privacy**: no logging of item content (logger scrubs; only UIDs/rule ids); temp dir forced to `<project>/.rvs-tmp`; crash handler writes UID-free message; see DEVIATIONS V01 for offline test design.
- **GUI**: main window with tree, table (column chooser/filters, QSortFilterProxyModel), editor (form + Markdown + live preview), Problems dock, matrix/dashboard/impact/graph (QGraphicsView, own layered layout, no graphviz) tabs; long jobs in `QThreadPool` workers (responsive exports); guided vs expert mode is a UI flag, same core.

## 5. Dependencies (runtime)
`doorstop==3.2`, `PySide6` (pinned), `openpyxl`, `python-docx`, `reportlab` (pure-Python PDF; WeasyPrint rejected: needs Pango/Cairo system libs), `markdown`, `pyyaml` (via Doorstop), `jsonschema`, `platformdirs`. Dev only: pytest, pytest-qt, hypothesis, mypy, ruff, import-linter, pyinstaller, cyclonedx-bom, pip-licenses, pip-audit. Builds from a vendored wheelhouse (`pip download` mirror) for reproducibility.

## 5a. As built in M1
- `rvs-project.yaml` declares documents/kinds (D21); the Doorstop tree has a single root, so VER is a child of SYS (V07).
- `rvs_core.validate.validate_project` = config load + schema versions + RVS hooks (documents, items) + Doorstop's own validation, all read-only (V09). Findings carry code, severity, message, hint, location, uid.
- Performance spike (5,000 items): open 0.01 s (lazy), read all 4.4 s, full validate 15.6 s, build 62 s. Target (open < 3 s) needs the index cache (D27) in M3.

## 5b. As built in M2
- `rvs_core.rules` (8 rules, config-driven), `rvs_core.glossary`, `rvs_core.authoring.EditService` (create/update/set_parents + history), `rvs_core.examples.satellite`.
- `rvs_gui`: `ProjectSession` -> models (`ItemTableModel`/`ItemFilterProxy`/`FindingsModel`) -> widgets (`DocumentTree`, `RequirementEditor`, `ProblemsPanel`, `InlineNotification`) -> `MainWindow`. The editor form is generated from `config/templates.yaml`, so project-specific free attributes appear without code changes.
- Strict offline guard (`adapter/_offline_guard.py`, DEVIATIONS V01).

## 5c. As built in M3
- `rvs_core.trace`: `LinkGraph` (parent + typed links, config/links.yaml), link validation, `impact`, `neighbourhood`, `coverage`, `aggregate_status`. `rvs_core.matrices`: `MatrixTable` + `Provenance` (+ CSV/JSON rendering) for traceability, VCM, coverage and impact; everything the GUI tabs and `rvs export` show comes from these.
- `rvs_core.adapter.cache`: per-document item cache (D43). `ItemData` now carries `stamp` and `link_stamps`, so suspect links are computed from snapshots.
- GUI: tabs Items / Traceability / VCM / Coverage / Graph, Impact dock, "Clear suspect links", New Verification Item. `ProjectSession` reuses the validation report's items, docs and graph (no second load).
- Measured at 5,000 items: warm open + rules + links 0.4 s; graph + VCM + trace + coverage 0.04 s; cold open 6.0 s (V14).

## 6. Risks
1. Doorstop's transitive network libs vs. offline test (DEVIATIONS V01).
2. Doorstop load time at 5,000 items — benchmark in M1 spike; fallback is the one-pass cached index.
3. Carbon fidelity in Qt widgets — limit to tokens, tables, forms, notifications.
4. Git availability on locked-down hosts — decide bundled `dulwich` vs system git in M0.
