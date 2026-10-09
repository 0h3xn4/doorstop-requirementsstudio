# Plan (proposal)

Rule for every milestone: tests first; mypy + ruff clean; offline test and `doorstop` CLI validation of reference projects in CI; ends with a short demo note in `docs/demo/Mx.md`.

## M0 Foundation
- `rvs/` pyproject (runtime deps only), src layout, ruff/mypy/pytest/import-linter config, CI (Linux + Windows, Python 3.11 and 3.13), `pip install -e .` smoke test launching the GUI headless (offscreen).
- Empty Carbon-styled main window (tokens, IBM Plex bundled, light theme first), PyInstaller spec, offline installer/portable zip, vendored wheelhouse, `make sbom` (dev extra).
- Offline test (design in DEVIATIONS V01). Decide Git strategy.
- **Accept:** installer builds on both OSes, app starts offline, offline test green, runtime `pip install` pulls no dev tools.

## M1 Model and files  *(done — see docs/demo/M1.md)*
- Adapter, extended attributes, fingerprint settings, schema versions + migration/newer-refusal, config loaders + JSON Schemas, `rvs validate` (Doorstop validation + RVS config/schema checks), minimal 10-item project.
- Spike: 5,000-item load timing.
- **Accept:** `doorstop` CLI passes on minimal project; byte-identical regeneration; migration tests; validate returns stable exit codes.

## M2 Authoring  *(done — see docs/demo/M2.md)*
- Tree + table views, editor (form + Markdown + preview), quality rules and Problems panel with jump links, glossary/acronym highlighting, edit with who/why recorded, satellite300 project generator.
- **Accept:** every rule has positive/negative unit tests; pytest-qt create/edit/save flow.

## M3 Links and matrices  *(done, one target open — see docs/demo/M3.md)*
- Typed links + validation, traceability matrix (both directions, gaps), VCM (placeholder layout), impact analysis, coverage dashboard, graph view, stress5000 project.
- **Accept:** golden files for matrices; open 5k < 3 s, matrices < 5 s.

## M4 Import and export  *(done, ReqIF deferred — see docs/demo/M4.md)*
- CSV/XLSX import & export, DOCX, PDF, HTML with provenance blocks; Hypothesis round-trip and byte-identical regeneration; golden files on 3 projects. ReqIF deferred (D04) behind the format-plugin interface.
- **Accept:** unchanged-item round trip yields no diff; GUI stays responsive during export.

## M5 Change control  *(done — see docs/demo/M5.md)*
- Baselines (tag + manifest), change requests, open-CR gate with deferral, baseline diff and working-copy diff with visual before/after.
- **Accept:** baseline immutability tests; diff lists added/removed/changed.

## M6 Polish (done)
- Guided wizard and expert mode, keyboard shortcuts, user guide (offline HTML/PDF) with both walkthroughs, developer docs (file format, rules config), installer hardening (no admin, uninstall, optional signing step), performance pass, licence report + SBOM per release.
- **Accept:** full pytest-qt suite, performance targets met, release checklist.

## Post-v1
ECSS compliance review once standards text is supplied; dark theme.
