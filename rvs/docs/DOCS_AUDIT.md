# Documentation audit

What this is for: a list of what was wrong with the documentation of Requirements & Verification Studio (RVS) when this audit
started, what was done about it, and what is still open. It is about documentation only; the earlier engineering audit
of the code is in [AUDIT.md](AUDIT.md).

Status column: **planned** (before the work), then **fixed** or **deferred** (with the reason).

## Where things stand (before the work)

- **This repository is a fork** of [`doorstop-dev/doorstop`](https://github.com/doorstop-dev/doorstop) (GitHub fork status read
  with the REST API: `fork: true`, `parent: doorstop-dev/doorstop`; the default branch is `develop`, there is no `main`).
  The upstream base is commit `c944c86` (Doorstop 3.2 development, 2026-10-09). Everything upstream is in the repository root
  (`doorstop/`, `docs/`, `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `mkdocs.yml`, ...). Everything Claude built on top is in
  the folder `rvs/` (the application **Requirements & Verification Studio**), plus a few CI files under `.github/workflows/`.
- There is no `upstream` git remote in this clone.
- Method: all Markdown files were listed (`git ls-files '*.md'`), relative links were checked with `markdown-link-check`,
  anchors with a small script, every `--option` named in the docs was compared with the real command-line parser, every
  keyboard shortcut named in the guide with the shortcut table in the code, and the install and a first CLI session were run
  in a clean virtual environment (Python 3.13, `pip install -e rvs`, 27 s, no errors).

## Findings

| # | File | Problem | Severity | Planned fix | Status |
|---|---|---|---|---|---|
| 1 | `README.md` (root) | It is only the upstream Doorstop README. A visitor to the repository cannot tell that RVS exists, what it is or how to start it. Its badges show the upstream project's CI, not this repository's. | High | Rewrite as a two-part README: RVS first (banner, quick start, doc table, what the fork adds), the original README verbatim below a divider. | planned |
| 2 | `rvs/README.md` | 26 lines. No quick start, no picture, no link to the guide or any docs, installation reduced to two bullets. | High | Rewrite as the tool README (non-fork layout). | planned |
| 3 | `rvs/docs/` | No index. Seven engineering documents, a `demo/` folder of old notes and the guide sources sit side by side with no map. | High | Add `docs/README.md` index grouped as Getting started / User guides / Reference / Examples / Developer docs, plus a separate heading for upstream Doorstop documentation. | planned |
| 4 | install instructions | They exist only in chapter 1 of the in-app guide (an HTML file inside the program) and in `docs/RELEASE.md`. Both assume a built release archive; no such archive is published, so a newcomer's real path (`pip install`) is not described anywhere. | High | New `docs/getting-started.md` that leads with `pip install` and has a worked example for the GUI and one for the command line. Tested in a clean venv. | planned |
| 5 | `rvs/examples/` | Two example projects (`minimal10`, `satellite300`) with no README: nothing says what they contain, that `satellite300` has seven seeded defects, how to open them or what the expected output is. | High | Add `examples/README.md`; every example command run and its real output recorded. | planned |
| 6 | user documentation | Organised by program part (the guide chapters), not by what a user wants to do. No short "How do I ..." pages. | Medium | Add `docs/user-manual/`: one task-oriented page per workflow, linking to the guide for the full reference. | planned |
| 7 | troubleshooting / FAQ | Spread over guide chapters 1 and 7 and `RELEASE.md`. | Medium | Add `docs/troubleshooting.md` (real errors from the clean-venv run and the likely ones) and `docs/faq.md`. | planned |
| 8 | glossary | Terms exist only as a table in guide chapter 1. Acronyms (ECSS, VCM, CR, SRR, NCR, SBOM, ReqIF, EPS/OBC/AOCS/TT&C, YAML) are used without a first-use explanation in the README, the specification and the architecture documents. | Medium | Add `docs/glossary.md`; define acronyms at first use in the README and getting-started and link to the glossary. | planned |
| 9 | tips and other tools | Nothing on shortcuts for power users in one place, and nothing on how RVS exchanges data with other tools. | Medium | Add `docs/tips.md`. Only describe exchange formats RVS really has (CSV, XLSX, ReqIF, DOCX, PDF, JSON). | planned |
| 10 | other tools of the owner (SpaceMissionStudio, Harness Design Studio, Requirements Studio, Budget Studio, AIT Logbook, ICD Studio) | The brief asks for import/export integration notes with these tools. Nothing in the code or the specification mentions any of them, so no integration is documented or known to exist. | Medium | Do not invent. State what exchange formats exist and list the question under "need your decision". | planned |
| 11 | `CONTRIBUTING.md`, `CHANGELOG.md` (root) | Upstream's files (Poetry, `make`, Doorstop release notes). Nothing for RVS, which has a different toolchain (`pip install -e ".[dev]"`, pytest, ruff, mypy, PyInstaller). | Medium | Add `rvs/CONTRIBUTING.md`, `rvs/CHANGELOG.md` and `docs/developer/`. Leave the upstream files alone. | planned |
| 12 | developer documentation | Only `CLAUDE.md` (instructions for the AI assistant), `ARCHITECTURE.md`, `RELEASE.md`. No human-oriented "set up, run the tests, lint, release, sync with upstream" page. | Medium | Add `docs/developer/README.md` including how to refresh the upstream README copy. | planned |
| 13 | `docs/guide/01-getting-started.md` | The `settings.json` table lists five keys; the file now also has `layout` (window state and column widths, added after the last documentation pass). | Medium | Add the key; rebuild the bundled guide (`scripts/build_guide.py`). | planned |
| 14 | `docs/SPEC.md` line 167 | Says ReqIF is "deferred past version 1"; ReqIF import and export shipped (decision D73). The other open decisions (standards text, operating systems, evidence storage, approval, licence, accreditation) are still unticked although defaults were taken. | Medium | Correct the ReqIF line and say where the answers recorded so far are; leave the genuinely open ones open and list them for the owner. | planned |
| 15 | `docs/demo/M0.md` ... `post-v1.md` | Point-in-time notes; correctly labelled, but unlinked from anywhere and containing old numbers (test counts, timings). | Low | List them in the docs index under "History", keep the banner. | planned |
| 16 | `docs/AUDIT.md` vs this file | Two documents with similar names. | Low | Cross-link; this file says it is about documentation, AUDIT.md about the code. | planned |
| 17 | screenshots | Seven images exist (items table in three variants, wizard, VCM, graph). Missing: Problems panel, Traceability tab, Changes and Baselines tabs, import preview. | Medium | Generate the missing ones from the real application (offscreen) and use them in the manual. | planned |
| 18 | duplicated content | Terms and install steps appear in the guide, `RELEASE.md` and (soon) the manual. | Medium | Rule: the in-app guide (`docs/guide/*.md`) is the reference; new pages are short, task-oriented and link to it instead of copying tables. | planned |
| 19 | operating systems | The docs are accurate (Windows installer and macOS never run) but the README-level reader is not told which OS is tested: Linux and Windows tests run in CI; the Windows installer, the Windows build and macOS were never run. | Medium | State it in the README and getting-started. | planned |
| 20 | links | Relative links and images in all 52 tracked Markdown files resolve (0 broken). Two external hosts (`doorstop.dev`, the Doorstop GitHub pages) cannot be reached from the sandbox used for this audit. | Info | Re-check online passes in a normal environment; recorded in the PR. | planned |
| 21 | CLI `--help` | All documented options exist and every real option is documented. Several positional arguments and a few options still have no help text (listed in `docs/AUDIT.md`). | Low | Out of scope for a documentation-only change (code); recorded for a follow-up. | deferred |
| 22 | upstream README (inside the new root README) | When moved below the RVS part its headings must be demoted one level so the table of contents stays clean; its relative links stay valid because the file stays at the repository root. | Info | Demote headings only; list changes in the "Upstream README changes" section below. | planned |

## Findability check (before the work)

Goal: from the README to *install → first result → user manual → examples → troubleshooting* in three clicks or fewer.

| Step | Before | Clicks |
|---|---|---|
| Install | Root README has no RVS content; `rvs/README.md` has two bullets; real steps are in the guide inside the program | not reachable |
| First result | In-app guide only | not reachable |
| User manual | In-app guide (HTML) | not reachable from the repository |
| Examples | `rvs/examples/` has no README | not reachable |
| Troubleshooting | Guide chapter 7, `RELEASE.md` | not reachable |

## Upstream README changes

*(filled in when the root README is restructured)*
