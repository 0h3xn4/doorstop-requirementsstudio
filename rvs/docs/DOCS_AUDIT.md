# Documentation audit

What this is for: a record of what was wrong with the documentation of Requirements & Verification Studio (RVS) when this audit started, what was done about it, and what is still open. It is about documentation only; the earlier audit of the code is in [AUDIT.md](AUDIT.md).

**Contents:** [Where things stood](#where-things-stood) · [Findings](#findings) · [Found while doing the work](#found-while-doing-the-work) · [Findability check](#findability-check) · [Upstream README changes](#upstream-readme-changes) · [How it was verified](#how-it-was-verified) · [Deferred, and decisions for the owner](#deferred-and-decisions-for-the-owner)

## Where things stood

- **This repository is a fork** of [`doorstop-dev/doorstop`](https://github.com/doorstop-dev/doorstop) (GitHub REST API: `fork: true`, `parent: doorstop-dev/doorstop`). The default branch is `develop`; **there is no `main` branch**, so the pull request for this work targets `develop`. The upstream base is commit `c944c86` (Doorstop 3.2 development, 2026-10-09). There is no `upstream` git remote in the clone.
- Upstream is the repository root (`doorstop/`, `docs/`, `reqs/`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `mkdocs.yml`, ...). What Claude built on top is the folder `rvs/` (the application **Requirements & Verification Studio**), `.github/workflows/rvs-ci.yml` and two small changes to upstream workflows.
- Method: every Markdown file was listed (`git ls-files '*.md'`, 52 files at the start); relative links and images were checked with `markdown-link-check`; anchors with a small script; every `--option` named in the docs was compared with the real command-line parser; every keyboard shortcut named in the guide with the shortcut table in the code; and the install and a first session were run in a clean virtual environment (Python 3.13, `pip install ./rvs`, 15 s).

## Findings

Status: **fixed** or **deferred** (reason given).

| # | File | Problem | Severity | Fix | Status |
|---|---|---|---|---|---|
| 1 | `README.md` (root) | Only the upstream Doorstop README: a visitor could not tell RVS exists, what it is or how to start it. Its badges showed the upstream project's CI. | High | Two-part README: RVS first (banner, quick start, doc table, features, requirements, what the fork adds), the original README verbatim below a divider. | fixed |
| 2 | `rvs/README.md` | 26 lines; no quick start, no picture, no links to docs. | High | Rewritten as the tool README. | fixed |
| 3 | `rvs/docs/` | No index; seven engineering documents, a `demo/` folder and the guide sources side by side with no map. | High | `docs/README.md`: index grouped as Getting started / User guides / Help / Reference / Examples / Developer docs / History / Upstream Doorstop documentation. | fixed |
| 4 | install instructions | Only in guide chapter 1 (HTML inside the program) and `RELEASE.md`, both assuming a release archive that is not published. The real route (`pip install`) was not described anywhere. | High | `docs/getting-started.md`: prerequisites, install on Linux, macOS and Windows, first run in the window, a worked example from the command line with expected output. Every command replayed in a clean venv. | fixed |
| 5 | `rvs/examples/` | Two example projects with no README. | High | `examples/README.md`: what each shows, how to run it, real expected output, the seven planted defects listed. | fixed |
| 6 | user documentation | Organised by program part, not by task. | Medium | `docs/user-manual/`: ten "How do I ...?" pages linking to the guide for the reference. | fixed |
| 7 | troubleshooting / FAQ | Spread over guide chapters 1 and 7 and `RELEASE.md`. | Medium | `docs/troubleshooting.md` (real messages from the clean-venv run, marked **real**, plus the likely ones) and `docs/faq.md`. | fixed |
| 8 | glossary | Terms only in a table in guide chapter 1; ECSS, VCM, NCR, SRR, PDR, CDR, AIT, ICD, SBOM, ReqIF, subsystem acronyms undefined at first use. | Medium | `docs/glossary.md` (about 70 entries, alphabetical, with anchors); links from the README, getting-started and the manual. The acronyms are also spelled out at first use in the README and getting-started. "Link budget" is not used anywhere in RVS, so it has no entry. | fixed |
| 9 | tips | No single page of shortcuts and power-user workflows. | Medium | `docs/tips.md`. | fixed |
| 10 | integration with the owner's other tools (SpaceMissionStudio, Harness Design Studio, Requirements Studio, Budget Studio, AIT Logbook, ICD Studio) | Nothing in the code or the specification mentions any of them, so no integration exists or is known. | Medium | Nothing was invented. `tips.md` documents the real exchange routes (CSV, XLSX, ReqIF, DOCX, PDF, HTML, JSON) and how to map a table from any tool. | deferred: needs your input (see below) |
| 11 | `CONTRIBUTING.md`, `CHANGELOG.md` | The root files are upstream Doorstop's (Poetry, `make`, Doorstop releases). Nothing for RVS. | Medium | `rvs/CONTRIBUTING.md` and `rvs/CHANGELOG.md`; the root files are untouched. | fixed |
| 12 | developer documentation | Only `CLAUDE.md` (assistant instructions), `ARCHITECTURE.md`, `RELEASE.md`. | Medium | `docs/developer/README.md`: set up, tests and lint, code layout, documentation, CI, releases, syncing with upstream, known side effects of the fork. | fixed |
| 13 | `docs/guide/01-getting-started.md`, `07-reference.md` | The `settings.json` table lacked the `layout` key (added after the last documentation pass). | Medium | Added; bundled guide rebuilt (`scripts/build_guide.py`; the guide tests pass). | fixed |
| 14 | `docs/SPEC.md` | Said ReqIF is "deferred past version 1"; ReqIF shipped (D73). The other open decisions are genuinely open. | Medium | ReqIF line corrected; the open ones are listed under "decisions for the owner". | fixed |
| 15 | `docs/demo/*.md` | Point-in-time notes, labelled, but linked from nowhere. | Low | Listed in the index under "History". | fixed |
| 16 | `docs/AUDIT.md` and this file | Two documents with similar names. | Low | Cross-linked, each says what it covers. | fixed |
| 17 | screenshots | Seven images existed. Missing: Problems, Traceability, Coverage, Changes, Baselines, the baseline dialog, Export dialog, import preview. | Medium | Eight new screenshots generated from the real application (offscreen, fictional data) into `docs/images/`, used in the manual and getting-started. | fixed |
| 18 | duplicated content | Terms and install steps repeated in the guide, `RELEASE.md`, and (new) the manual. | Medium | Rule adopted and written down in the developer guide: the in-app guide is the reference; new pages are short, task-oriented and link to it instead of copying its tables. The quick start appears in the two READMEs and getting-started on purpose (it is the first thing a visitor reads). | fixed |
| 19 | operating systems | Docs accurate, but a newcomer was not told which systems are tested. | Medium | README and getting-started: Linux and Windows are tested on every change; macOS is not; the Windows installer has never been run. | fixed |
| 20 | external links | See "How it was verified": most hosts cannot be reached from the sandbox. | Info | Re-run the online pass in a normal environment. | deferred |
| 21 | CLI `--help` text | Some positional arguments and options have no help text. | Low | The brief excludes code changes. (Done in a related change: every `project` argument now says what it is, the export help lists ReqIF, exit codes are in the epilog.) | deferred |
| 22 | upstream README inside the new root README | Its headings had to be one level deeper; its links are all absolute. | Info | Headings demoted (8 lines); nothing else; see below. | fixed |

## Found while doing the work

| # | Where | What | Fix | Status |
|---|---|---|---|---|
| 23 | `docs/index.md` (upstream) | It is a link to the root `README.md`, and upstream's `Makefile` re-creates it. The upstream documentation site would now show the RVS part first, with relative links that do not resolve there. | Not changed (upstream files are left alone). Written up in the developer guide ("Known side effects of the fork"). This fork does not publish that site. | deferred: your call |
| 24 | root `pyproject.toml` | `readme = "README.md"`: if upstream Doorstop were ever built from this repository its package description would start with the RVS text. | Same: noted in the developer guide. | deferred: your call |
| 25 | `reqs/tutorial/TUT017.yml` (upstream) | A local run of plain `doorstop` at the repository root, made earlier to fix CI, stripped two trailing spaces from this file and the change was committed by accident. | Restored to the upstream text (commit `ecf30ad`). The developer guide warns not to run plain `doorstop` at the root casually. | fixed |
| 26 | `docs/DECISIONS.md` | Rows D73 to D83 had three cells in a four-column table, so GitHub renders them without a status. | Status `D` (a default chosen by Claude, the file's own definition) added; change any you want to mark `A`. | fixed |
| 27 | `docs/user-manual/08-command-line.md` | A table with unescaped `\|` inside code spans (caught by a table check; GitHub would have split the cells). | Escaped. | fixed |
| 28 | `.github/workflows/rvs-ci.yml` | Runs only when `rvs/**` changes, so a change to the root README alone does not run it. | Noted; no change. | fixed (noted) |
| 29 | `rvs/.doorstop.skip-all` | Needed so plain `doorstop` at the root works (earlier fix); easy to forget. | Documented in the README ("What this fork adds") and the developer guide. | fixed |

## Findability check

Goal: from the README to install, first result, user manual, examples and troubleshooting in three clicks or fewer.

| Step | Before | After |
|---|---|---|
| Install | not reachable | README, "Quick start" (0 clicks) or [Getting started](getting-started.md) (1 click) |
| First result | not reachable | README quick start (0 clicks); Getting started, "First run" (1 click) |
| User manual | not reachable from the repository | README table, "User manual" (1 click) |
| Examples | no README | README table, "Examples" (1 click) |
| Troubleshooting | guide chapter 7 | README table, "Troubleshooting" (1 click) |
| Glossary, tips, developer docs | missing | 1 click from the README or the index |

## Upstream README changes

The original Doorstop README is kept untouched in `docs/upstream/README.upstream.md` (identical to the file at upstream commit `c944c86`; its last upstream change was commit `b12f6d8`, 2026-06-26). The copy inside `README.md`, between `<!-- BEGIN UPSTREAM README -->` and `<!-- END UPSTREAM README -->`, differs from it in exactly these lines, all heading levels:

| Original | In `README.md` |
|---|---|
| `# Overview` | `## Overview` |
| `# Setup` | `## Setup` |
| `## Requirements` | `### Requirements` |
| `## Installation` | `### Installation` |
| `# Usage` | `## Usage` |
| `## Create documents` | `### Create documents` |
| `## Link items` | `### Link items` |
| `## Publish reports` | `### Publish reports` |

No links or images needed changing: every link and image in the upstream README is an absolute URL. `rvs/docs/developer/refresh_upstream_readme.py` produces this block from the copy (and `--check` proves it is current); the developer guide explains the refresh.

## How it was verified

- **Clean install and every step of Getting started.** A new virtual environment (Python 3.13), `pip install ./rvs`, then each command of [Getting started](getting-started.md) and of the [examples README](../examples/README.md) was run and its output compared with the page by a script. All matched: the version line, `selftest`, the dry run and import summaries, the last line of `validate` for the demo project, `minimal10` and `satellite300`, the VCM, trace and impact tables. The other commands named in the manual (`export` to xlsx, docx, pdf and reqif, `cr new/list/status/show`, `diff`, `baseline verify`, `--only-gaps`, `--baseline`, `--strict`, `--fast`) were run and succeed. Two exports with the same `SOURCE_DATE_EPOCH` are byte-identical. (The repository was installed from a local path, not cloned from GitHub, because the new pages are not on GitHub yet.)
- **Internal links and images:** `markdown-link-check` over every new and changed Markdown file and the original README: 0 broken. **Anchors:** a script resolves every `file.md#heading` link with GitHub's heading rules: 0 broken after two were fixed.
- **Tables:** a script checks that every table row has as many cells as its header: 0 problems after the two fixes above.
- **Options and shortcuts:** every `--option` in the docs exists in the CLI parser and every real option is documented; shortcuts named in the guide match the code (the only ones not in the table are Ctrl+C, F2 and an example override).
- **Upstream copy:** the embedded block differs from the untouched copy by the eight heading lines above and nothing else.
- **Not possible here:** the online pass over external links. From the sandbox used for this work most hosts (`doorstop.dev`, shields.io, gitter, speakerdeck, the Doorstop GitHub pages and badges) are unreachable (no response or HTTP 403 from a proxy), and GitHub's own rendering cannot be viewed. Of 38 external addresses only `pypi.org`, `raw.githubusercontent.com` and this repository's own page answered. All of them are either upstream's (unchanged) or standard addresses; re-run `lychee` (without `--offline`) once in a normal environment. Rendering on GitHub was checked by construction (heading anchors, table cell counts, relative image paths, no raw HTML in the new pages) rather than by looking at it.

## Deferred, and decisions for the owner

1. **Integration with your other tools** (SpaceMissionStudio, Harness Design Studio, Requirements Studio, Budget Studio, AIT Logbook, ICD Studio): the brief asks for notes on importing from and exporting to them. Nothing in the code or specification says any such link exists, so none is documented. Tell me which tools exchange what (file format, columns) and I will write it up, or the CSV/XLSX/ReqIF routes in `tips.md` can be used as they are.
2. **The `main` branch:** it does not exist; the default branch is `develop`. This work targets `develop`.
3. **Licence text:** `rvs/LICENSE` says proprietary, internal use only, while the repository root is LGPL-3.0 (Doorstop). The README says so plainly; whether you want a different statement is yours to decide. Standards texts (ECSS-E-ST-10-02C, -10-06C, ECSS-M-ST-40C), the operating-system scope, evidence storage, approval, licence and accreditation questions in `docs/SPEC.md` ("Open decisions") are still open.
4. **Upstream's documentation site and package metadata** (items 23 and 24): decide whether the Doorstop site is ever built or published from this fork.
5. **Release archives:** none is published, so Getting started leads with `pip install ./rvs`. If you publish archives, add a download step.
6. **macOS and the Windows installer** have never been run; the pages say so. Tell me if you can test them.
7. **Screenshots** were generated offscreen from the fictional examples; replace them if you want a different look.
8. **Item 21** (command-line help text) and **item 20** (online link pass) as above.

Next: [Documentation index](README.md) · [Engineering audit](AUDIT.md) · [Developer guide](developer/README.md)
