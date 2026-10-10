# Plan

The milestone plan agreed before the build, with what was done. M0 to M6 and the post-v1 items are complete (version 0.1.0); what remains is under *Open after v1*.

Rule for every milestone: tests first; mypy + ruff clean; offline test and `doorstop` CLI validation of reference projects in CI; ends with a short demo note in `docs/demo/Mx.md`.

## M0 Foundation
- `rvs/` pyproject (runtime deps only), src layout, ruff/mypy/pytest config (the dependency rule is enforced by an AST test, `tests/test_layering.py`), CI (Linux + Windows, Python 3.11, 3.12 and 3.13), `pip install -e .` smoke test launching the GUI headless (offscreen).
- Empty Carbon-styled main window (tokens, IBM Plex bundled, light theme first), PyInstaller spec, portable folder, vendored wheelhouse (`scripts/build_wheelhouse.sh`), `scripts/sbom.sh` (dev extra).
- Offline test (design in DEVIATIONS V01). Git strategy: bundled `dulwich` (D17).
- **Accept:** the bundle builds, the app starts offline, offline test green, runtime `pip install` pulls no dev tools. (The Windows build was never run: V22.)

## M1 Model and files  *(done — see docs/demo/M1.md)*
- Adapter, extended attributes, fingerprint settings, schema versions + migration/newer-refusal, config loaders + JSON Schemas, `rvs validate` (Doorstop validation + RVS config/schema checks), minimal 10-item project.
- Spike: 5,000-item load timing.
- **Accept:** `doorstop` CLI passes on minimal project; byte-identical regeneration; migration tests; validate returns stable exit codes.

## M2 Authoring  *(done — see docs/demo/M2.md)*
- Tree + table views, editor (form + Markdown + preview), quality rules and Problems panel with jump links, glossary/acronym highlighting, edit with who/why recorded, satellite300 project generator.
- **Accept:** every rule has positive/negative unit tests; pytest-qt create/edit/save flow.

## M3 Links and matrices  *(done — see docs/demo/M3.md; the cold-open target was met later by D75)*
- Typed links + validation, traceability matrix (both directions, gaps), VCM (placeholder layout), impact analysis, coverage dashboard, graph view, stress5000 project.
- **Accept:** golden files for matrices; open 5k < 3 s, matrices < 5 s.

## M4 Import and export  *(done — see docs/demo/M4.md; ReqIF followed after v1)*
- CSV/XLSX import & export, DOCX, PDF, HTML with provenance blocks; Hypothesis round-trip and byte-identical regeneration; golden files on the reference projects. ReqIF was deferred (D04) and added after v1 (D73).
- **Accept:** unchanged-item round trip yields no diff; GUI stays responsive during export.

## M5 Change control  *(done — see docs/demo/M5.md)*
- Baselines (tag + manifest), change requests, open-CR gate with deferral, baseline diff and working-copy diff with visual before/after.
- **Accept:** baseline immutability tests; diff lists added/removed/changed.

## M6 Polish (done)
- Guided wizard and expert mode, keyboard shortcuts, user guide (offline HTML, shown with F1 and `rvs guide`) with both walkthroughs, developer docs (file format, rules config), installer hardening (no admin, uninstall, optional signing step), performance pass, licence report + SBOM per release.
- **Accept:** full pytest-qt suite, performance targets met, release checklist.

## Post-v1  *(done — see docs/demo/post-v1.md)*
- [x] ReqIF 1.x import and export (D73).
- [x] Dark theme and "follow the system" (D74).
- [x] Guide screenshots (D77).
- [x] Cold open of 5,000 items from 6.6 s to about 2 s with libyaml (D75).
- [x] Independent review pass with five reviewers and the fixes (D79-D83, V24) and a packaging/documentation audit (D84, D85, V26-V31).

## Open after v1
- [ ] ECSS compliance review once the standards text is supplied (`TODO-STANDARD` values, VCM layout).
- [ ] Company values (`TODO-COMPANY`): priority scale, vague words, implementation terms, change request statuses.
- [ ] Run and fix the Windows installer and build on a Windows machine (V22, V25); code-signing certificate.
- [ ] Hashed lock file and a pinned, repeatable dependency set (V27).
- [ ] A way to add a document to an existing project and to set `derived`/`level`/`active` without a spreadsheet (V31).
- [ ] Detect a file that changed on disk before saving an item (V29); limit the snapshot cache (V30).
- [ ] `.reqifz` archives, embedded files and images in ReqIF (V16).
