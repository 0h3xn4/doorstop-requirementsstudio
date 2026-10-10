# Requirements & Verification Studio (RVS) — Specification

## Role and context

You are a senior software engineer building **Requirements & Verification Studio (RVS)**, an offline desktop application for requirements management and verification tracking at a small satellite company. Treat this file as the specification. Before writing code, read it completely, ask your clarifying questions in one batch, and propose an architecture and milestone plan. Where the spec is silent, choose the simplest option, record it in `docs/DECISIONS.md` with a one-line rationale, and continue. Where the spec is ambiguous in a way that affects the data model or file format, stop and ask.

### Product goal

A lightweight, Git-friendly alternative to IBM DOORS: engineers write requirements as plain files, link them to parents, children, tests and evidence, and the tool produces ECSS-style traceability and verification control matrices on demand. It must feel like a modern desktop app, not a text editor with a plugin.

### Base framework

RVS is built on **[Doorstop](https://github.com/doorstop-dev/doorstop)** (Python, LGPLv3, requirements as files in Git). Doorstop is the storage and traceability core; RVS is the desktop application, rule engine and matrix generator around it. Pin Doorstop to 3.2 ([PyPI](https://pypi.org/project/doorstop/), requires Python 3.10+), never patch its internals, and put everything RVS-specific in your own package that wraps it, as Basilisk and WireViz were treated. If Doorstop lacks a capability, add it in RVS code or record it in `docs/DEVIATIONS.md`.

A project folder must stay a valid Doorstop tree: `doorstop` run on it from the command line passes, and `doorstop publish` still works. Map RVS concepts onto Doorstop like this:

| RVS concept | Doorstop mechanism |
| --- | --- |
| Document (SYS, EPS, OBC, VER…) | A Doorstop document: a folder with `.doorstop.yml` holding `prefix`, `sep`, `digits` and `parent` |
| Document tree | Doorstop's parent-document hierarchy |
| Requirement and verification items | Doorstop items (one file per item); statement in `text`, ordering in `level`, headings as non-normative items |
| Parent/child (derivation) links | Doorstop `links`, with `derived: true` for items that have no parent |
| Typed links (satisfies, verifies, refines, conflicts-with) | Extended attributes, validated by RVS; Doorstop links only point to parents |
| RVS fields (type, status, owner, verification method…) | Extended attributes, with defaults in `.doorstop.yml` |
| Suspect links after a parent changes | Doorstop link fingerprints; RVS surfaces them in the Problems panel |
| Review state | Doorstop `reviewed` fingerprint, set only through Doorstop's review API |
| Evidence and source files | Doorstop `ref` / references to files in the repository |
| Quality rules | RVS rules called as item and document hooks in Doorstop's tree validation |
| Baselines, change requests, matrices | RVS only, built on Git tags and the Doorstop tree |

Use Doorstop's Python API for all reads and writes; do not write item files by hand. Do not ship or start `doorstop-server` (it opens a network port) or the Tk `doorstop-gui`; the RVS GUI replaces both. List any extended attribute that must affect fingerprints in the document's fingerprint settings, so changing a status alone does not mark links suspect.

### Users

- **Systems engineers** write and baseline requirements, build the tree from mission down to subsystem and unit level, and own the verification matrix.
- **Subsystem engineers** (electrical, mechanical, thermal, software) read their allocated requirements, propose changes, and attach verification evidence.
- **AIT and test engineers** link test procedures and reports to requirements and mark verification status.
- **Quality and product assurance** audit traceability, review open non-compliances and export matrices for customer or ESA reviews.
- **Reviewers and customers** read exported documents (PDF, DOCX, XLSX) without the tool installed.

## Hard constraints and lessons learned

These rules come from two earlier tools built the same way (SpaceMissionStudio on Basilisk, Harness Design Studio on WireViz). Each one cost time once; do not relearn them.

### Offline and closed operation

1. The tool must be fully usable offline and closed: no cloud services, no AI features, and no background network access (no telemetry, analytics, crash reporting, licence checks, online help, CDNs, web fonts or automatic update checks). Bundle every dependency and asset locally.
2. The only permitted network use is downloading reference data or asset updates, and only when the user starts the download or explicitly agrees to a prompt naming the source, files and size. Verify the integrity of every download (checksum or signature), keep the previous version for rollback, and always offer the same update via manual file import.
3. Add an automated test that runs the tool with networking disabled and fails if any networking module is imported or a socket is opened at runtime. It runs in CI.
4. Help, examples and templates ship with the tool, since there is no online documentation.
5. All checks and warnings are deterministic and traceable to a defined rule. Autocomplete comes only from the local data, never from a language model.

### Environment and packaging

6. Runs on locked-down workstations without admin rights. Deliver a self-contained installer or portable build for Windows 10/11 and Linux (RHEL/Rocky 8+ and Ubuntu LTS). Treat macOS as optional.
7. Only permissively licensed or LGPL dependencies that allow closed internal use. Pin all versions, make builds reproducible from a vendored or mirrored package set, and produce an SBOM (CycloneDX) and licence report with every release.
8. **Keep release and dev tooling out of the runtime dependencies.** In Harness Design Studio, `cyclonedx-bom` in the install set pulled in `lxml`, which had no wheel for the newest Python and broke `pip install` for the whole app. Put pytest, mypy, ruff, pyinstaller, cyclonedx-bom, pip-licenses, pip-audit and similar under `[project.optional-dependencies] dev`, and make sure `pip install -e .` alone yields a runnable GUI.
9. State the supported Python versions explicitly (currently 3.11 to 3.13) and test the install on the newest one, since brand-new interpreters often lack prebuilt wheels for C extensions.
10. Prefer pure-Python dependencies where a C extension brings no real benefit, so the install never needs a compiler or system dev packages.

### Data and security

11. Project files may contain export-controlled information. Never write project content to logs, temp files outside the project folder, or crash dumps.
12. Project data is plain-text Doorstop items (YAML or Doorstop's Markdown item format) that diffs and merges cleanly in Git. Several people work on different subsystems as separate files.
13. Every file carries a schema version. Loading an older version migrates it; loading a newer version fails with a clear message.
14. Regenerating an unchanged project produces byte-identical output files (deterministic IDs, stable ordering, no timestamps in content).

### Standards and numbers

15. **Never invent values from standards.** Where ECSS, NASA or company rules require specific numbers, thresholds or wording, leave a clearly marked placeholder in a configuration file and list it as an open decision. Both earlier tools had to be audited for this.
16. The applicable standards are ECSS-E-ST-10C (system engineering), ECSS-E-ST-10-02C (verification), ECSS-E-ST-10-06C (technical requirements specification), ECSS-M-ST-40C (configuration management), ECSS-E-ST-40C (software) and ECSS-Q-ST-80C (software product assurance). Build the data model so that the fields these standards expect exist; the actual compliance review is a separate task later.

### Design system and UX

17. Use **IBM Carbon** as the design system, with IBM Plex fonts bundled, for data-dense tables, forms, notifications and a Problems panel. Match the look of SpaceMissionStudio and Harness Design Studio so the tools feel like one family.
18. Every output (document, matrix, report) carries provenance: tool version, framework version, project baseline, generation date and the user's name, in a title block or header.
19. Errors speak the user's language: what is wrong, where, and what to do, with a link that jumps to the offending item. Never show raw tracebacks in the GUI.
20. If the Monaco editor or any web component is used, package it with the tool; it loads from a CDN by default.

### Working method

21. Separate a **headless core** (data model, file I/O, traceability engine, matrix generators) from the **GUI**. The core has no GUI imports and no network imports. Expose it through a **CLI** so validation and exports run in scripts and CI (e.g. `rvs validate project/`, `rvs export project/ --vcm`).
22. Keep rules, naming schemes and document templates in **project configuration files**, not in code.
23. Propose the technology stack with a short comparison of two or three options. A strong default is Python with PySide6 (Qt, LGPL) and PyInstaller. Accept an alternative only if it is clearly better for offline packaging or rendering quality.
24. Record every decision in `docs/DECISIONS.md` and every known deviation from the base framework in `docs/DEVIATIONS.md`.
25. Write tests first for every milestone. Static typing and linting enforced in CI; no warnings on the main branch.

## Functional scope

### Data model

- **Document tree:** mission requirements, system requirements, subsystem and unit specifications, interface requirements, plus derived documents (verification plan, test specifications). Each document has a prefix (e.g. `SYS`, `EPS`, `OBC`) and a numbering scheme defined in configuration.
- **Requirement item:** ID, title, text, rationale, type (functional, performance, interface, environmental, operational, design, verification), priority, status (draft, reviewed, approved, baselined, obsolete), owner, source, applicable standard clause, verification method (test, analysis, inspection, review of design), verification level (unit, subsystem, system), and free attributes defined per project.
- **Links:** parent and child (derivation), satisfies, verifies, refines, conflicts-with, and a generic reference link to external documents by document number and revision. Links are typed, directional and validated.
- **Verification item:** procedure or analysis ID, title, method, level, status (planned, in progress, passed, failed, waived), evidence (file path or document number and revision), execution date, responsible person, and non-conformance references.
- **Baselines:** a named, immutable snapshot of the whole tree bound to a Git tag. Diffs between baselines list added, removed and changed items with before and after text.

### Authoring

- Rich requirement editor with a structured form (fields) and a Markdown text area for the statement, side by side with a live rendered preview.
- Quality checks on every requirement, each traceable to a rule in configuration: uses "shall"; one requirement per statement; no vague words ("adequate", "as appropriate", "user-friendly"); no implementation in a functional requirement; verification method set; at least one parent unless it is a root document; at least one verification link once status reaches approved. Each check produces a plain-language finding in a Problems panel, with severity and a jump link.
- Bulk import from CSV, XLSX and ReqIF; export to the same plus DOCX, PDF and HTML. Round-trip import must not change unchanged items.
- Glossary and acronym list per project, with automatic highlighting of undefined acronyms.

### Traceability and verification

- Traceability matrix: any two document levels, both directions, with gaps highlighted (orphans, childless items, unverified approved items).
- Verification control matrix (VCM): every requirement with its verification method, level, item, status and evidence, filterable and exportable, formatted after ECSS-E-ST-10-02C Annex conventions where the annex defines them (leave placeholders for anything the standard text is needed for).
- Impact analysis: select an item and see everything downstream that would be affected by a change, as a tree and a list.
- Coverage dashboard: per document, the share of items in each status and each verification state. Keep it a simple table or bar chart, no decorative visuals.

### Change control

- Every edit records who, when and why; the why is mandatory once an item is baselined.
- Change requests group edits, carry a status and link to the affected items. A baseline cannot be created while change requests are open against it unless they are explicitly deferred.
- Visual diff of any item or document between two baselines or between the working copy and a baseline.

### Views

- Tree view of documents and items, table view with column chooser and filters, and a graph view of links for one item and its neighbourhood.
- A Problems panel listing all findings across the project, sortable by severity and document.
- Guided mode for occasional users (wizard-style requirement creation, no fields hidden) and expert mode for systems engineers (dense table, keyboard shortcuts, inline editing).

### Out of scope for version 1

- Multi-user real-time editing (Git is the collaboration layer).
- Workflow engine with electronic signatures.
- Direct integration with Jira, Polarion or DOORS beyond ReqIF exchange.

## Architecture, quality and milestones

### Architecture

- Packages: `rvs_core` (model, Doorstop adapter, rules, matrices, exporters), `rvs_cli`, `rvs_gui`. The GUI depends on the core; nothing depends on the GUI.
- The Doorstop adapter is the only module that imports Doorstop. All RVS attributes beyond Doorstop's defaults live in Doorstop's extended attributes, so the files remain valid for plain Doorstop. A CI test runs the Doorstop CLI's own validation on every reference project.
- Rules (quality checks), naming schemes, document templates and export layouts live in `project/config/*.yaml` with a JSON Schema each.
- Exports use only bundled components and fonts. DOCX via python-docx, PDF via a bundled renderer (e.g. WeasyPrint or ReportLab), XLSX via openpyxl.

### Quality

- Unit tests for the data model, every quality rule, every link type and the baseline diff.
- Property-based tests (Hypothesis) showing that import, export and re-import of any project is lossless and that regeneration is byte-identical.
- Golden-file tests for every export type on three reference projects you create: a minimal 10-item example, a realistic small satellite (about 300 requirements across mission, system, EPS, OBC, AOCS, TT&C, structure, thermal and payload), and a stress project of 5,000 items for performance.
- Performance targets: open the 5,000-item project in under 3 s, matrix generation under 5 s, GUI stays responsive during exports.
- GUI tests with pytest-qt for the main flows; the offline test runs in CI.
- A user guide (Markdown, bundled as offline HTML or PDF) with a guided-mode and an expert-mode walkthrough, plus developer documentation for the file format and the rules configuration.

### Milestones

Propose a detailed plan in `docs/PLAN.md` roughly in this order. Each milestone ends with working, tested software and a short demo note.

1. **M0 Foundation:** repository, build, CI, packaging of an empty Carbon-styled app into an offline installer, offline test, SBOM in the dev extra only.
2. **M1 Model and files:** Doorstop adapter, extended attributes, schema version, config files, `rvs validate`.
3. **M2 Authoring:** tree and table views, requirement editor, quality rules, Problems panel.
4. **M3 Links and matrices:** typed links, traceability matrix, VCM, impact analysis, coverage dashboard.
5. **M4 Import and export:** CSV, XLSX, ReqIF, DOCX, PDF, HTML, round-trip tests.
6. **M5 Change control:** baselines, change requests, visual diff.
7. **M6 Polish:** guided mode, keyboard shortcuts, user guide, installer hardening, performance pass.

## Open decisions

See `DECISIONS.md` for the answers recorded so far.

- [x] **Doorstop item format:** YAML (answered).
- [x] **Numbering scheme:** `SYS-0012` (answered).
- [ ] **Standards text:** will you provide ECSS-E-ST-10-02C and ECSS-E-ST-10-06C as files? Without them, placeholders stay.
- [x] **ReqIF:** deferred past version 1 (answered), then implemented after version 1 (decision D73): export and import work; see the user guide.
- [ ] **Operating systems:** Windows only, Linux only, or both? (default: both)
- [ ] **Evidence storage:** repository, network share, or document number only? (default: repository path or doc number + revision)
- [ ] **Approval:** status field enough, or review and sign-off record per baseline? (default: status field)
- [ ] **Licence and ownership:** internal only, or possibly open source later? (default: internal; permissive/LGPL deps only)
- [ ] **Security accreditation:** code signing or specific SBOM format? (default: CycloneDX, unsigned)
