# Changelog

This page lists what changed in each version of Requirements & Verification Studio (RVS). The format follows [Keep a Changelog](https://keepachangelog.com). (The file `CHANGELOG.md` at the repository root belongs to upstream Doorstop.)

## [Unreleased]

### Documentation
- New documentation set: a documentation index, getting started, a task-based user manual, an examples guide, FAQ, troubleshooting, glossary, tips, developer guide, contributing guide and this changelog. The repository README now describes RVS first and keeps the original Doorstop README below it, verbatim.
- Corrected the guide: the `layout` key of `settings.json`; the specification no longer says ReqIF is deferred.

## [0.1.0] - 2026-10-10

First version, merged into `develop`. No release archive has been published yet; install from source with `pip install ./rvs` ([Getting started](docs/getting-started.md)).

### Added
- Desktop application `rvs-studio` and command line `rvs`, built on Doorstop 3.2, fully offline.
- Projects of documents and items with parent links and typed links (`satisfies`, `refines`, `verifies`, `conflicts-with`); templates *Minimal*, *Small satellite* and *Software product*; two example projects.
- Quality rules, finding codes with hints, a glossary and acronym check.
- Verification items, verification control matrix, traceability, coverage, impact analysis and a graph.
- Change requests, immutable baselines bound to Git tags (built-in Git), reasons for changes to baselined items, comparison of two states.
- Import and export: CSV, XLSX, ReqIF; reports as DOCX, PDF, HTML, JSON; provenance on every output; reproducible bytes with `SOURCE_DATE_EPOCH`.
- Guided and expert modes, light and dark themes, built-in offline user guide (F1).
- Release build: clean-environment PyInstaller bundle, licences and SBOM, installers for Linux (and Windows, never run), `rvs selftest`.

### Fixed (after a full audit, before 0.1.0 was merged)
- Baselines: a `.gitignore` can no longer drop project data from a baseline; creation rolls back completely on failure; two creators of one name cannot overwrite each other; names differing only in case and Windows device names are refused.
- Security: custom YAML tags and alias bombs refused; ReqIF DOCTYPE refused in every encoding; the item cache and extracted snapshots are signed per user; XLSX export no longer writes project text to the system temporary folder.
- Robustness: the command line never prints a traceback; exports are written whole or not at all; corrupt change-request and manifest files give messages.
- Speed: DOCX and PDF specification export no longer slow down sharply with size.
- Window: keyboard use (tab order, focus ring, F4 into the editor), contrast, accessible names, window size on laptop screens, confirmation before discarding input, baselines from example projects, remembered window layout.
- Windows: project files always use LF line endings; item paths are always `/`-separated.

The full list with the reasons is in [docs/AUDIT.md](docs/AUDIT.md).
