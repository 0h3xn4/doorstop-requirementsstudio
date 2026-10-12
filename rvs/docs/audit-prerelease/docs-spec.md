# Pre-release audit: Specification compliance and documentation truth

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

## Coverage
Files read in full: rvs/README.md; root README.md (RVS part); rvs/docs/{README,getting-started,faq,troubleshooting,glossary,tips,SPEC,ARCHITECTURE,DECISIONS,DEVIATIONS,PLAN,RELEASE,AUDIT,DOCS_AUDIT}.md; docs/guide/01..07; docs/user-manual/README + 01..10; docs/developer/README.md; examples/README.md; CONTRIBUTING.md; CHANGELOG.md; CLAUDE.md; docs/demo/*.md; config/defaults/*.yaml (9 files); src/rvs_core/rules/engine.py, validate.py (1-300), trace/validation.py, authoring.py, userconfig.py, diagnostics.py (crash part), rvs_cli/main.py (help, error paths), rvs_cli/changecontrol.py (baseline/cr part), rvs_gui/shortcuts.py, problems.py, app.py (menus), packaging/*.sh|ps1 (option names).

Probes run (scratch dir `audit/docs-spec/`, copies of the repo and examples only):
- Replayed Getting-started (init, import dry run + real, validate, VER import, VCM, baseline create/list, diff) and examples/README (minimal10 validate/VCM/trace/coverage/impact; satellite300 validate): all outputs match the docs (except where noted below).
- Replayed every "(real)" message of troubleshooting.md (nowhere, init inside project, broken YAML, unknown column, baseline already exists, bad name, no git, binary format without -o, reason needed): all match.
- `scripts/build_guide.py` run in a copy: guide.html byte-identical to the committed one. Link/anchor checker over all 47 Markdown files (GitHub slug rules): 0 broken links, 0 broken anchors.
- Dumped `rvs --help` and every subcommand help; compared with guide 06 / manual 08: options all match.
- GUI offscreen probe: menus, shortcuts, tab names, column list, status bar text ("339 items · 3 errors · 14 warnings") compared with docs.
- Determinism: 13 outputs (xlsx, docx, pdf, html, json, csv, reqif, spec) of satellite300 exported under 3 time zones and random PYTHONHASHSEED with SOURCE_DATE_EPOCH: byte-identical. Different LOGNAME: differs.
- strace of validate/export (xlsx, docx, pdf, reqif)/import/baseline/diff/cr: no file created outside project, output folder or user-config folder, except an empty probe file `/tmp/XXXXXXXX` created and removed by `import doorstop` (tempfile.gettempdir) and the documented `rvs selftest` scratch folder.
- Stress project (gen_stress.py 5,000 items) cold/warm open, matrix exports timed (machine load average 6-7 on 4 cores, so wall times are pessimistic; CPU times given).
- Plain `doorstop` + `doorstop publish all` on satellite300 and on an RVS-edited project: pass.
- Baseline tamper tests (edited manifest, deleted tag), schema-newer tests, missing config file, formula-injection and HTML-escape probes, flag import (`derived/active/level`), blank-ID import, round-trip import of CSV/XLSX/ReqIF (0 changes).
- Tests run: tests/test_guide.py, tests/test_repo_layout.py (13 passed); tests/test_satellite_example.py, test_examples.py, test_golden.py in the scratch copy (11 passed, also with `.rvs-cache` present). GitHub Actions: latest `rvs-ci` runs on develop are green (run 56).

## Job A: SPEC compliance table

Legend: C = compliant (verified by running), D = deviates (documented), D* = deviates, documentation incomplete, V = violated, N = not implemented but claimed.

| SPEC item | Result | Evidence / note |
|---|---|---|
| R1 offline, no telemetry/CDN/web fonts | C | `rvs`/GUI run with no network module loaded (checked sys.modules; `_socket` is loaded through subprocess/selectors, `socket` is not); exported HTML has no http refs/scripts; fonts are data URIs |
| R2 network only on user request | C (n/a) | no download feature exists |
| R3 offline test in CI | C | tests/test_offline.py in `pytest`, CI green. Judge: it does not ban `socket`/`_socket` import itself |
| R4 help/examples/templates bundled | C | guide.html, examples generators, `rvs init` templates |
| R5 deterministic rules, no LLM | C | engine.py, whole-word regex rules |
| R6 no admin, installers Win10/11 + Linux (RHEL/Rocky 8+, Ubuntu LTS) | D | Windows never run (V22/V25); bundle needs glibc 2.38 so RHEL 8/9 and Ubuntu 22.04 are excluded (V28); both documented |
| R7 permissive/LGPL, pinned, reproducible, SBOM + licence report | D | direct deps pinned, transitive not, no hashes (V27); SBOM + licences present in dist/ |
| R8 dev tooling outside runtime | C | pyproject: dev extra only; selftest imports without dev tools |
| R9 Python 3.11-3.13, tested on newest | C | CI matrix incl. 3.13 |
| R10 pure-Python preference | D | lxml, Pillow (V15) |
| R11 no project content in logs/temp/crash dumps | C | strace probe (see Coverage); crash report holds type + frames only |
| R12 plain-text YAML items | C | |
| R13 schema version in every file; older migrates, newer fails | D* | items/config/project/baselines/CRs carry it, newer refused (tested: item -> RVS-SCHEMA-NEWER error, config -> exit 3). `history/*.jsonl`, `settings.json`, cache carry none; only AUDIT.md section 3 admits it, DEVIATIONS does not |
| R14 byte-identical regeneration | C with caveats | verified for all formats with SOURCE_DATE_EPOCH; see DOCS-SPEC-05 for what is not guaranteed |
| R15 no invented standard values | C | placeholders; but TODO-COMPANY ones are only comments (DOCS-SPEC-03) |
| R16 fields for ECSS standards exist | C | standard_clause, verify_*, etc. |
| R17 IBM Carbon, Plex bundled | C | 8 font files, 27 theme tokens |
| R18 provenance on every output | D* | present in CSV/XLSX/DOCX/PDF/HTML/JSON matrices and diff csv/html/docx/pdf; ReqIF has no user name; `rvs diff --format json` has no provenance (DOCS-SPEC-06) |
| R19 user-language errors, jump link, no GUI tracebacks | C | CLI/GUI messages checked; location-only findings open the file location |
| R20 Monaco/web component packaged | C (n/a) | not used |
| R21 headless core + CLI | C | |
| R22 rules/naming/templates/export layouts in config with JSON Schema | D* | rules, numbering, templates, vocab, links, changes, glossary: yes. Export layouts: only VCM/trace column titles; spec/DOCX/PDF/HTML layouts are code; `provenance_fields` is ignored (DOCS-SPEC-07). The M4 note promised "M6 polish"; never done, not in DEVIATIONS |
| R23/R24 stack proposal, decisions recorded | C | ARCHITECTURE s.2, DECISIONS |
| R25 tests first, typing/lint in CI | C | CI runs ruff, mypy, pytest; `filterwarnings = error` |
| Doorstop mapping: valid Doorstop tree, `doorstop` and `doorstop publish` work | C | verified on satellite300 and on an RVS-edited project |
| Do not ship doorstop-server / Tk GUI | C | excluded in bundle |
| Review state via Doorstop review API | D* | RVS never reviews; documented as design (D25, guide) but there is no DEVIATIONS entry and the SPEC table row is not marked |
| Suspect links via fingerprints | C | status/priority/owner change: no suspect; title change: RVS-LINK-SUSPECT |
| Data model: requirement fields (type 7 values, status 5, method 4, level 3, free attributes) | C | vocab.yaml/templates.yaml match SPEC |
| Links: parent/child, satisfies, verifies, refines, conflicts-with | C | links.yaml; kind/direction validated |
| Link: generic reference to external documents (docno + revision) | D* | only the `link_refs` attribute (type ref-list) with type validation and import/export; no editor control, never mentioned in the guide; D13 even says it is a list of item UIDs (DOCS-SPEC-12) |
| Verification item fields | C | proc_id, method, level, v_status, evidence, executed_on, responsible, nonconformances |
| Baselines: named, immutable, bound to Git tag; diff added/removed/changed with before/after | C / overclaimed | RVS never rewrites or reuses; tampering detected; not tamper-proof (DOCS-SPEC-04) |
| Editor: form + Markdown + live preview | C | |
| Quality checks (7 listed + acronym) each a configured rule with finding + severity + jump | C | all 7 present; `no-implementation` ships with an empty list (documented) |
| Bulk import CSV/XLSX/ReqIF, export + DOCX/PDF/HTML; round trip leaves unchanged items untouched | C | satellite300 CSV/XLSX/ReqIF re-import: 339 unchanged, 0 files rewritten |
| Glossary + automatic highlighting of undefined acronyms | C | rule + editor underline |
| Traceability matrix any two levels, both directions, gaps | D* | direct links only (D39); non-adjacent documents give a matrix that flags everything (DOCS-SPEC-02) |
| VCM filterable and exportable, ECSS layout placeholder | C | placeholder note in every VCM |
| Impact analysis tree + list | C | |
| Coverage dashboard table | C | |
| Change control: who/when/why, why mandatory once baselined | C | history jsonl; import and EditService refuse without reason (verified for import, update, clear-suspect, set-parents in code) |
| Change requests, baseline refused while CRs open unless deferred | C | verified; exit code 1 not 2 (DOCS-SPEC-09) |
| Visual diff baseline/baseline and baseline/working | C | |
| Views: tree, table with column chooser/filters, graph, Problems panel sortable by severity and document | C | |
| Guided + expert mode | C | |
| Perf: open 5,000 items < 3 s | D | warm open 0.65 s CPU / 1.1 s wall; cold open 3.8-4.1 s CPU (4.9-6.3 s wall under load). Documented as 3-5 s cold in guide/RELEASE and "accepted" in V14, but D75 claims the target is met (DOCS-SPEC-10) |
| Perf: matrices < 5 s | C | `--vcm` csv 1.4 s, xlsx 1.9 s, trace 1.2 s, coverage 1.1 s total process time at 5,000 items (PDF VCM 5.5 s under load) |
| GUI responsive during exports | not measured here | tests/jobs exist |
| Hypothesis round-trip / byte-identical tests | C | present |
| Golden tests for every export on three reference projects | D | two reference projects have goldens; the 5,000 stress project is generated, no goldens (D45/D55) |
| CI test runs Doorstop CLI validation on every reference project | D* | only minimal10 (tests/test_examples.py:28); no `doorstop publish` test (DOCS-SPEC-11) |
| pytest-qt GUI tests | C | |
| User guide (offline) with both walkthroughs + developer docs for file format and rules config | C / partly | guide has both; developer README has no file-format/rules-configuration section (these live in guide ch.7 and ARCHITECTURE s.3) |
| M0..M6 deliverables | C | |
| ID format SYS-0012 | C | digits 4, sep "-" (schema forces "-") |
| YAML items | C | |

## Findings

### DOCS-SPEC-01 The documented way to retire an item (`active: no`) produces a false validation error
- Where: docs/guide/02-guided-walkthrough.md section 7, docs/faq.md "Can I delete an item?", user-manual 07; code: trace/graph + validate (`RVS-LINK-TARGET-MISSING`)
- Severity: medium
- Confidence: verified
- What is wrong: The docs tell users to retire an item by importing `active = no` ("traceability and baselines remain intact"). Any verification item that verifies the retired requirement then gets an ERROR `RVS-LINK-TARGET-MISSING ... which does not exist`, although the item exists (it is inactive). `rvs validate` exits 1 and a CI pipeline using it fails. The VCM silently drops the row, the trace matrix marks the parent "childless".
- Evidence:
  ```
  cp -r examples/minimal10 fl2; printf 'id,active\nEPS-0001,no\n' > a.csv
  rvs import fl2 a.csv --reason r      -> 0 created, 1 updated
  rvs validate fl2 | grep -E "^(ERROR|WARNING)"
  ERROR   RVS-LINK-TARGET-MISSING VER-0001 (VER/VER-0001.yml): VER-0001 has a 'verifies' link to EPS-0001, which does not exist.
  WARNING RVS-TRACE-NO-CHILD SYS-0002 ...   (exit 1)
  ```
- Why it matters: a documented workflow breaks a gate and the message is wrong (misleads users into "fixing" a link that is right).
- Proposed fix: treat links to inactive items as a distinct finding (warning "links to inactive item X") or ignore them; at least change the message. Document that verifiers of a retired item must be retired too.
- Test that would catch it: import `active=no` for an item that has a verifier; assert no `does not exist` finding.

### DOCS-SPEC-02 Traceability matrix for non-adjacent (or identical) documents silently flags every row as a gap
- Where: `rvs export --trace`, Traceability tab; SPEC "any two document levels"; D39 (direct only)
- Severity: medium
- Confidence: verified
- What is wrong: Only direct links count, so `--trace MIS:EPS` (grandparent to grandchild) lists all MIS items as `childless`, although each is traced through SYS. `--trace EPS:EPS` is accepted and flags all rows. Neither guide nor manual says "direct links only".
- Evidence: `rvs export satellite300 --trace MIS:EPS` -> every row `MIS-000n,...,,,childless`; `--trace EPS:EPS` exit 0, all `childless`.
- Why it matters: wrong "gap" results presented as fact in an audit matrix; SPEC wording says any two levels.
- Proposed fix: either follow links transitively between the two documents, or refuse non-adjacent/identical pairs with a message; state the rule in guide ch.2/5 and manual 03.
- Test that would catch it: trace between non-adjacent documents of satellite300 must not mark linked items childless.

### DOCS-SPEC-03 "TODO-COMPANY values are reported until replaced" is not true
- Where: guide 01 (terms) and 07 ("Configuration values to decide", configuration files), faq.md, glossary.md, DECISIONS D26; code `config/model.py:Standards.unresolved`, `validate.py:407`
- Severity: medium
- Confidence: verified
- What is wrong: `RVS-STD-PLACEHOLDER` lists only entries of `config/standards.yaml -> placeholders` whose `status != resolved`. The default list holds three TODO-STANDARD items and no company item. The TODO-COMPANY marks (priority scale, vague words, implementation terms, change-request statuses) are YAML comments only; nothing detects or reports them, and replacing them has no effect on the finding. The message says "standard/company value(s)".
- Evidence: `rvs validate examples/minimal10` -> `RVS-STD-PLACEHOLDER ... 3 standard/company value(s) ...: ecss-e-st-10-02c.vcm-annex-layout, ecss-e-st-10-06c.requirement-wording-rules, ecss-m-st-40c.baseline-naming`; grep shows no code reading "TODO-COMPANY".
- Why it matters: SPEC rule 15 wants open decisions listed; users are told RVS tracks company placeholders but it does not, so open company values can ship unnoticed (they appear only in PLAN "Open after v1").
- Proposed fix: add company placeholders as entries in standards.yaml (status TODO-COMPANY) or reword docs to "only the entries in standards.yaml are reported".
- Test that would catch it: a placeholder entry with status TODO-COMPANY appears in the finding; docs test for the claim.

### DOCS-SPEC-04 "Baselines can never be altered/changed/deleted" is stronger than the code
- Where: root README ("Git tags that can never be altered"), glossary, user-manual 06 ("can never be changed or reused"), GUI `PERMANENT_NOTE` ("cannot be edited or deleted"), guide 04 ("immutable"); the honest statement exists only in DEVIATIONS V24
- Severity: medium
- Confidence: verified
- What is wrong: What is guaranteed: RVS has no command to edit, delete, move or reuse a baseline; creation is atomic; a changed manifest is reported (`RVS-BASELINE-MODIFIED`), a deleted tag as `RVS-BASELINE-NOTAG`, tagged content that no longer matches as `RVS-BASELINE-CORRUPT` (deep verify only). Not guaranteed: anyone with file/Git access can delete or move the tag or delete the manifest. If tag and manifest are both removed the baseline vanishes silently and its items stop requiring reasons.
- Evidence: in a copy: `git tag -d rvs/baseline/PDR` succeeds; `rvs validate` then shows only `RVS-BASELINE-NOTAG`, `rvs baseline list` still lists PDR from the manifest. Editing the manifest works too and is only detected.
- Why it matters: users relying on "can never be altered" for configuration management evidence.
- Proposed fix: reword everywhere to "RVS never modifies a baseline and detects changes; protect the repository tags" and move V24's tag caveat into the guide.
- Test that would catch it: doc check; behaviour test that deleting tag + manifest is reported (not currently possible to detect).

### DOCS-SPEC-05 "Same input, same bytes" / "the same commit always gives the same file" omit the conditions
- Where: tips.md ("so the same commit always gives byte-identical files"), user-manual 07 and 08, guide 01/05, root README, SPEC R14
- Severity: low
- Confidence: verified
- What is wrong: Byte identity holds for the same OS login name, same tool and library versions, same project state (and baseline) and, for PDF, same platform (D55: PDF hashes only compared on Linux). The user name is part of the provenance in every format.
- Evidence: `SOURCE_DATE_EPOCH=1767225600 LOGNAME=alice rvs export minimal10 --vcm -o u1.xlsx` vs `LOGNAME=bob ... u2.xlsx` -> `differ: char 266`; same user twice: identical. Identical across TZ and PYTHONHASHSEED.
- Why it matters: a CI that builds on another account/machine cannot compare hashes; the doc promises it can.
- Proposed fix: add "same user (`--user`/login), same RVS version" to each statement; offer a way to pin the user (env var) for reproducible builds.
- Test that would catch it: doc statement vs test of different LOGNAME.

### DOCS-SPEC-06 Some outputs lack the provenance the docs promise
- Where: exporters/reqif.py header; `rvs diff --format json`; user-manual 07 ("Every file names the project, the baseline, the date and time, the user and the tool versions"); SPEC R18
- Severity: medium
- Confidence: verified
- What is wrong: The ReqIF file carries project, baseline, tool and creation time but not the user's name. The JSON diff has no provenance at all (keys: left, right, summary, changes). All other formats checked have it (CSV/XLSX/DOCX/PDF/HTML/JSON matrices, diff csv/html/docx/pdf).
- Evidence: `grep -c root reqif.reqif` -> 0 (user was root); `rvs diff . PDR working --format json | jq keys` -> left,right,summary,changes.
- Why it matters: SPEC R18 says every output; docs say every file.
- Proposed fix: add the user (e.g. `<COMMENT>`/`SOURCE-TOOL-ID` extension or a `Generated by` line) to ReqIF; add a `provenance` object to the diff JSON.
- Test that would catch it: provenance test over the 30 catalog outputs plus ReqIF and diff JSON.

### DOCS-SPEC-07 Configuration that does nothing, and a comment that is stale
- Where: config/defaults/exports.yaml (`provenance_fields`, comment "used from M3/M4"); guide 07 config table ("Column layouts ... provenance fields"); numbering.yaml / guide ("separator")
- Severity: low
- Confidence: verified
- What is wrong: `provenance_fields` is only validated by the schema, no code reads it (set it to `[user]`: provenance unchanged). `numbering.yaml` `sep` is documented as configurable but the schema allows only "-" (`data.sep must be one of ['-']`). The exports.yaml comment refers to milestones.
- Evidence: `sed -i 's/provenance_fields:.*/provenance_fields: [user]/' config/exports.yaml; rvs export --vcm` -> same 5 provenance lines. `sep: "_"` -> RVS-CONFIG-INVALID.
- Proposed fix: remove the key or implement it; say that the separator is fixed; rewrite the comment.
- Test that would catch it: a test that changes each documented config key and asserts an effect.

### DOCS-SPEC-08 Troubleshooting mixes up two opposite warnings; documented Doorstop codes are never emitted
- Where: troubleshooting.md "A warning says `no links to parent document` / `RVS-TRACE-NO-CHILD`"; guide 07 "Finding codes" last paragraph; validate.py `_REPLACED_BY_RVS`
- Severity: low
- Confidence: verified
- What is wrong: "no links to parent document" means the item has NO PARENT (satellite300 TTC-0001); the page explains it as "nothing linked below it. Allocate it to a subsystem requirement". RVS-TRACE-NO-CHILD is the opposite. Also `DOORSTOP-NO-CHILD-LINKS` and `DOORSTOP-SUSPECT-LINK` are listed in the guide but are filtered out of validation and never appear; the real parent warning appears as generic `DOORSTOP-WARNING`, a duplicate of `RVS-RULE-HAS-PARENT`.
- Evidence: `rvs validate examples/satellite300` -> `WARNING DOORSTOP-WARNING TTC-0001: TTC: TTC-0001: no links to parent document: SYS`; `grep -n _REPLACED_BY_RVS src/rvs_core/validate.py`.
- Proposed fix: split the troubleshooting entry in two; classify "no links to parent document" (e.g. fold into HAS-PARENT or give it a code) and drop the dead codes from the guide.
- Test that would catch it: guide test that every documented DOORSTOP- code can be produced.

### DOCS-SPEC-09 Exit code of a refused baseline contradicts the documented exit codes
- Where: rvs_cli/changecontrol.py:127; guide 06, manual 08, `rvs --help` epilog
- Severity: low
- Confidence: verified
- What is wrong: docs: "2 wrong usage or a refused operation (message on stderr)", "1 problems found". `baseline create` refused because of open change requests returns 1 (every other refusal returns 2: bad name, no git, existing name).
- Evidence: `rvs baseline create nogit B2 -m x` with an open CR -> message "A baseline cannot be created while change requests are open ..." exit 1.
- Proposed fix: return 2, or document it.
- Test that would catch it: parametrised exit-code test for all refusals.

### DOCS-SPEC-10 DECISIONS D75 / V14 say the cold-open target is met; measurements and other documents say otherwise
- Where: DECISIONS D75 ("now also meets the 3 s target"), DEVIATIONS V14 (title "Resolved"), vs D83 (2.65 s), AUDIT s.3 (3.2-3.5 s), RELEASE.md and guide ("3 to 5 s cold")
- Severity: low
- Confidence: verified
- What is wrong: 5,000-item project, `.rvs-cache` removed: `validate_project(doorstop=False)` CPU 3.84-4.09 s (wall 4.9-6.3 s with load average 6-7 on 4 cores); warm 0.65-0.73 s CPU. SPEC target "open < 3 s" is met warm only. The guide wording is honest, D75/V14 are stale.
- Evidence: `python perf.py stress` -> `cold open+rules wall 4.88s cpu 4.09s ... warm wall 1.06s cpu 0.65s`.
- Proposed fix: correct D75 and V14 text; keep a single quoted figure.

### DOCS-SPEC-11 SPEC items about CI coverage are only partly met
- Where: tests/test_examples.py:28; SPEC "A CI test runs the Doorstop CLI's own validation on every reference project"; PLAN ("doorstop CLI validation of reference projects in CI")
- Severity: low
- Confidence: verified
- What is wrong: only minimal10 is validated with plain Doorstop; satellite300 and the stress project are not, and `doorstop publish` ("still works") has no test. I ran both manually on satellite300: pass, so no defect, only a gap and a plural in PLAN.
- Proposed fix: parametrise the test over satellite300 and add `doorstop publish all <tmp>`.

### DOCS-SPEC-12 SPEC rules/rows deviated from without a DEVIATIONS entry
- Where: SPEC R13, "Review state" row, "generic reference link" row, R22 export layouts; DECISIONS D13
- Severity: low
- Confidence: verified
- What is wrong: (a) `history/*.jsonl`, `settings.json` have no schema version (only AUDIT.md s.3). (b) RVS never writes Doorstop review stamps; the SPEC table row says "set only through Doorstop's review API"; only D25 and the guide describe the choice. (c) `link_refs` is a list of `{docno, revision}` (attrtypes.py) but D13 says it is a list of item UIDs; there is no editor control and no user documentation. (d) export layouts (R22) promised "M6 polish" in demo/M4.md, not delivered, not listed.
- Proposed fix: add V32-V35 to DEVIATIONS; correct D13.

### DOCS-SPEC-13 Wording in the guide that does not match the window
- Where: guide 02 section 2 step 5 ("Click *Finish*"; button text is "Create requirement"); getting-started and guide ("File > Open Example…" then pick a folder; the menu is `File > Open Example` with sub-entries "Minimal (10 items)" / "Small satellite (about 300 items)", the folder dialog comes after); guide 02 section 4 says each Problems row "has a code" but the Code column is hidden by default and `View > Show problem codes` is not documented anywhere; export dialog text for coverage says "how many requirements ... are traced and verified" (the table is per status/verification state)
- Severity: low
- Confidence: verified (GUI probe, strings in wizard.py:102, app.py:281-285, problems.py:57)

### DOCS-SPEC-14 Small stale facts
- Where: DECISIONS D74 and ARCHITECTURE 5g say 26 theme tokens (LIGHT and DARK each have 27); AUDIT.md s.4 says the Windows CI job could not be checked (the latest rvs-ci runs on develop are green, so the README claim "tested on Linux and Windows on every change" holds); demo/M0..M6 are labelled snapshots (fine); CHANGELOG 0.1.0 is dated 2026-10-10 while "no release archive has been published".
- Severity: low
- Confidence: verified

### DOCS-SPEC-15 Baseline-name error message is wrong for names starting with `_`, `-` or `.`
- Where: baselines.py `_check_name` / troubleshooting.md ("Use 1 to 64 letters, digits, `.`, `_` or `-`")
- Severity: low
- Confidence: verified
- Evidence: `_x`, `-x`, `.x` refused with "Use 1-64 letters, digits, '.', '_' or '-' (no spaces or slashes)" although all characters are in that list; the real rule (first character letter or digit) appears only in guide 04.
- Proposed fix: mention the first-character rule in the message and troubleshooting.

### DOCS-SPEC-16 CLI inputs that are silently accepted
- Where: rvs export `--method/--level/--status`, `--impact`, rvs import
- Severity: low
- Confidence: verified
- What is wrong: `--method Test` or `--status bogus` give an empty matrix with exit 0 (no vocabulary check, case-sensitive); `--impact sys-0002` is refused although the GUI "Go to" accepts lower case; an empty CSV or one with only an unknown header and no rows is reported as `Dry run: 0 to create, 0 to update, 0 unchanged, 0 errors.` (exit 0).
- Proposed fix: validate filter values against vocab.yaml; case-fold UIDs; treat a file without rows as an error.

### DOCS-SPEC-17 "Contains no project content / user name from the OS login" has small exceptions
- Where: guide 01 (settings.json "never contains project content"; user name from OS login), vcs/git.py:86-96
- Severity: low
- Confidence: verified
- What is wrong: `settings.json` stores the full paths of the last eight projects (`recent`); the baseline commit's author email is read from the user's global Git config (`user.email`), not from the OS login, and the commit message carries an `RVS-Baseline: NAME` trailer (D14 says there are no commit trailers; that sentence is about history, but it reads as a general statement).
- Evidence: baseline commit author `root <noreply@anthropic.com>` (global git config of the sandbox).
- Proposed fix: say so in guide 01/04.

## Checked and found correct
- Every command in getting-started.md, examples/README.md (minimal10 and satellite300), the "real" troubleshooting messages, README quick start (`rvs --version`, `selftest`, "3 errors and 15 warnings", 339 items, GUI bar "339 items · 3 errors · 14 warnings"), item-file example in user-manual 10, ID format, baseline name rules (all cases in guide 04 incl. Windows device names, case clash, `..`, `.lock`).
- guide.html is current (rebuilt in a copy: identical); all 47 Markdown files have no broken relative link or anchor; every CLI option in `--help` is documented and vice versa; keyboard-shortcut table, menu paths (except DOCS-SPEC-13), tab names/order, Ctrl+1..8, recent-projects limit (8), settings.json keys and per-OS locations.
- Rule list, severities, parameters, hints, finding codes (except the two dead DOORSTOP- codes), status/method/level/verification vocabularies, config file list, default CR statuses and blocking statuses, `promote_on_baseline`.
- Suspect-link behaviour (status/owner/priority no, title yes), reason-for-change enforcement, baseline create/verify/diff/CR gate/defer flows, tamper detection of manifest and tag, newer-schema refusal, missing config fallback.
- Round trip: CSV, XLSX and ReqIF export then import of satellite300 changes nothing; flags `derived/active/level/normative/ref` import; blank-ID rows create items; formula-leading text is apostrophe-protected in CSV and stored as string cells in XLSX; HTML export escapes script/img/javascript: links and has no external references.
- Offline/privacy: only the empty tempfile probe by `import doorstop`, otherwise all writes next to their targets; `rvs` (CLI) never loads PySide6; plain `doorstop` and `doorstop publish` work on the RVS projects.
- Provenance (tool, framework, baseline, date, user) in CSV/XLSX/DOCX/PDF/HTML/JSON matrices, byte-identical across time zones and hash seeds with SOURCE_DATE_EPOCH.
- CI exists as documented (Linux + Windows x 3.11-3.13, GUI start, package job) and is green on develop; test count "about 800" (820 collected); dist sizes (179 MB folder, 77 MB archive); installer option names (Linux and Windows); `rvs init` templates and messages.

## Questions about intended behaviour
1. Should the traceability matrix follow links transitively (SPEC "any two levels") or only show adjacent levels? (DOCS-SPEC-02)
2. Should links to inactive items be errors at all? And should verifiers of a retired item be auto-ignored? (DOCS-SPEC-01)
3. Is the open-CR refusal meant to be exit 1 (gate result) rather than 2? (DOCS-SPEC-09)
4. Is the ReqIF header meant to omit the user for privacy, or is it an oversight? (DOCS-SPEC-06)
5. Should RVS-LINK-METHOD-MISMATCH fire when a requirement is verified by several methods (legitimate in ECSS)? Not a docs matter, noticed while reading trace/validation.py.


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
