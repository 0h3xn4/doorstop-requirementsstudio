# Pre-release audit: Validation, rules, links, matrices

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

Summary: 18 findings, 0 critical, 0 high, 5 medium (01-05), 13 low. 48 mutation probes: ~25 survived (ANALYSIS-18).
Tests run: 12 targeted files, 133 passed. Repo not modified.

### ANALYSIS-01 Parent links not validated for structure
- Where: src/rvs_core/trace/validation.py:36-47 (`if e.type == PARENT: continue`), validate.py:288 (`_REPLACED_BY_RVS`)
- Severity: medium | Confidence: verified
- A parent link to an item of the same document, the VER document, or from the root document into its own child passes `rvs validate --fast --strict` (exit 0; `--fast` is what the GUI uses). Full mode gives only an INFO from Doorstop, nothing for root->child. Link to a non-normative heading flagged only in full mode; typed links to headings never flagged.
- Evidence: `DoorstopProject.open(copy).link("SYS-0001","EPS-0001"); link("EPS-0002","EPS-0003"); link("EPS-0003","VER-0001")`; `rvs validate pl --fast --strict` -> `0 errors, 0 warnings, 1 info`.
- Why: spec says links are typed, directional and validated; matrices/impact use these edges; has-parent satisfied by a parent in the wrong place. Reachable by hand edits / Git merges.
- Fix: in `validate_links` require a parent link's target document to be the declared parent document of the source document (new error code); warn on links to non-normative targets.

### ANALYSIS-02 Link to an inactive item is reported as "does not exist"
- Where: trace/graph.py:50, trace/validation.py:21-30 (graph built from active `items()` only; `all_uids()` exists)
- Severity: medium | Confidence: verified
- Same root cause as DOCS-SPEC-01. `active: false` is a documented retirement route; every linker gets `RVS-LINK-TARGET-MISSING ... which does not exist`, hint "Correct the ID".
- Fix: use `all_uids()`; message "X is inactive (retired); link to a live item or remove the link". Test: inactive target -> message contains "inactive".

### ANALYSIS-03 "obsolete" requirements stay in every gap analysis
- Where: trace/validation.py `_missing_children`, matrices/vcm.py, matrices/traceability.py (test only `normative and active`)
- Severity: medium | Confidence: verified
- Guide says retire with status `obsolete` or `active: no`. Obsolete items still show "not verified" in VCM/`--only-gaps`, `childless`/`unverified` in trace, and raise `RVS-TRACE-NO-CHILD`; the other route causes -02. Retired requirements keep failing `--strict`.
- Fix: skip a configurable list of statuses (default `obsolete`) in gap checks, or document how to retire. Test: obsolete requirement without child -> no NO-CHILD.

### ANALYSIS-04 Verification status names hard-coded although vocab.yaml makes them configurable
- Where: trace/status.py:6-23, matrices/tables.py:16-17, trace/coverage.py
- Severity: medium | Confidence: verified
- Renaming a status in `config/vocab.yaml` (documented as allowed): no error; `aggregate_status` knows only failed/passed/waived/planned -> passed verification shown "in-progress"; Coverage table drops counts (VER row Items=3 but columns sum to 2).
- Fix: validate at config load that the vocabulary contains the five known names, or make aggregate/coverage vocabulary-driven. Test: columns sum to Items.

### ANALYSIS-05 CSV injection through the provenance block
- Where: matrices/render.py:28-34 (`# {line}` unprotected), matrices/provenance.py:22-27
- Severity: medium | Confidence: verified
- A project `name` (rvs-project.yaml, comes from the repo) or login name containing a newline ends the `#` comment line; the rest becomes a real CSV row. Excel does not treat `#` as comment, so a row starting `=` is a formula.
- Evidence: `name: "Evil\n=HYPERLINK(\"http://x\",\"click\")"`; `rvs export pn --vcm | head -9` shows a bare `=HYPERLINK(...)` line. `LOGNAME=$'evil\n=cmd|calc'` likewise.
- Fix: replace CR/LF by space in provenance/notes/title and protect a leading trigger; reject newlines in project name at config load. Test: every line before the header starts with `#`.

### ANALYSIS-06 Matrix CSVs have no BOM; items CSV has one (low)
- Where: matrices/render.py `to_csv`, rvs_gui/matrix_views.py:218, CLI export path
- Trace CSV first line contains arrows/non-ASCII; Excel likely shows mojibake (Excel behaviour reading-only). Fix: write BOM for matrix file outputs like itemsio.

### ANALYSIS-07 `rvs export --trace` crashes (TypeError) on wrong-typed `status` (low)
- Where: matrices/traceability.py:66 (`item.attrs.get("status") in approved`, a set)
- `status: [a]` -> "unexpected error (TypeError)" + crash report; fuzz of 14 attrs x 18 values found only this. Fix: `str(item.attrs.get("status") or "") in approved`.

### ANALYSIS-08 Invalid/empty SOURCE_DATE_EPOCH silently falls back to now (low)
- Where: matrices/provenance.py:48-57
- `-5`, `1e9`, huge, `²`, empty -> now() silently; docs/tips.md recommends `SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)` which is empty if git fails -> CI believes outputs are reproducible. Pinned time is UTC, fallback local, no zone printed. Fix: if set and invalid, exit 2.

### ANALYSIS-09 Rule parameters not validated (low)
- Where: rules/engine.py:62-100, config/schemas/rules.schema.json (`params` = object)
- `words: ['']` -> vague-words fires everywhere; `keyword:` null -> "None"; `keyword: ''` -> shall-present never fires; `max: two` ignored; misspelled param silently disables; duplicate rule ids double findings. Fix: per-rule param checks as RVS-CONFIG-INVALID; reject duplicate ids.

### ANALYSIS-10 A verification item that verifies nothing is invisible (low)
- `link_verifies: []` -> no finding, not in VCM. Fix: warn "VER-0001 verifies no requirement".

### ANALYSIS-11 Terminal escape sequences from project data printed raw (low)
- Where: validate.py messages embed raw values; findings.py `format`
- `status: "\e]0;PWNED\a\e[2J"` echoed raw by `rvs validate` text mode: untrusted clone can retitle terminal/clear screen (OSC 52 clipboard on some terminals); newline in link target splits the line. Fix: escape control chars in `Finding.format`.

### ANALYSIS-12 Crash report keeps folder names after an earlier `src/` in the path (low)
- Where: diagnostics.py:34-40
- `/home/alice/src/ACME-Satellite-Secret/rvs/src/rvs_core/x.py` -> `ACME-Satellite-Secret/rvs/src/rvs_core/x.py:2 in f` (source checkout only; also Windows paths). One crash file per failure, no limit. Fix: cut at `rvs_core`/`rvs_cli`/`rvs_gui`.

### ANALYSIS-13 `selftest --manifest` crashes on non-UTF-8 manifest; temp-dir failure not a FAIL line (low)
- Where: diagnostics.py:234 (`read_text(encoding="utf-8")`), :80 (`mkdtemp` outside try)
- Damaged MANIFEST.sha256 -> "unexpected error (UnicodeDecodeError)"; no usable tmp -> exit 2 message; entries with `..`/absolute paths hashed outside folder; uppercase digests "changed". Fix: catch into problem list, compare lower case.

### ANALYSIS-14 Unvalidated VCM filter values and column keys (low)
- Where: matrices/vcm.py:35-50
- `--method bogus` -> empty valid-looking matrix exit 0 (same as DOCS-SPEC-16); typo in `exports.yaml vcm.columns[].key` raises only at first row of an export. Fix: check against vocabulary at config load / exit 2.

### ANALYSIS-15 Doorstop `true` link stamp shown as suspect (low)
- Where: trace/validation.py:57
- In Doorstop `true` = manually confirmed; RVS string-compares, so hand-edited `true`/null/''/false all suspect and never rewritten. Fix: document or treat True as matching.

### ANALYSIS-16 Documentation / dead-code mismatches (low)
- Guide code table lists DOORSTOP-WARNING/ERROR but validate.py emits `DOORSTOP-INFO`; `provenance_fields` never read; unused `matrices/render.py:render`, `trace/graph.py:doc_of`, `by_uid`.

### ANALYSIS-17 Acronym rule noise and blind spots (low)
- Where: glossary.py:11 (`(?!-\d)`), rules/engine.py:139
- `SHALL`/`MUST` in capitals reported as undefined acronyms; lookahead meant for item IDs hides `UTF-8`, `ISO-26262`, `RS-422`, `STD` in `MIL-STD-1553`; glossary entry `CAN-FD` can never match (tokens CAN, FD); `A4`, `CO2`, `S2` flagged.

### ANALYSIS-18 Test gaps: surviving mutations (medium for the important ones)
48 one-line mutations over 12 test files (others may cover some). Survived: word-end boundary in `_word` (M02); acronym scan of title/rationale removed (M08, M09); blank v_status ignored (M19); impact BFS->DFS (M21); impact `related` filter (M22); coverage counts inactive (M24); VCM `--level` filter (M26); VCM level_key ordering (M27); trace orphan exemptions for derived/root (M29, M30); symmetric links excluded (M31); trace row order (M32); SOURCE_DATE_EPOCH parsing (M33); neighbourhood symmetric layer (M35); NO-CHILD document kind and satisfies/refines counting (M37, M38); findings sort order (M40); CSV protection of data rows (M41); crash-report path hiding (M42); vague words on non-requirements (M45); self-link suspect (M15). Weak assertions: `test_impact_survives_cycles` asserts only count >= 1; no diamond test; `test_aggregate_status_convention` lacks passed+waived/blank.

## Checked and found correct
Rules (marshall, case, phrases across line breaks, hyphenated vague words, 200k text linear, empty text, severity/enable overrides, RVS-RULE-UNKNOWN, null params); suspect-link fingerprint (status/owner/priority/rationale/level/header/normative/derived/typed-link/whitespace do not; title/type/verify_*/text/ref/references do; clearing works); coverage = independent hand count for all 10 satellite300 documents; VCM/trace on edited minimal10 as coded; impact on cycles/diamonds/20k chain/30k fan-out < 0.3 s, unknown UID exit 2; determinism across PYTHONHASHSEED; validate exit codes 0/1/3, --strict, --fast, JSON keys; every RVS-* code present in guide table except DOORSTOP-INFO; config robustness; selftest passes and cleans up.

## Questions about intended behaviour
- Should a non-normative item count as a verifier in VCM/aggregate_status? (currently yes; Coverage VER row excludes it).
- passed + waived verifiers give `in-progress` (D38): intended when all closed?
- A requirement whose only verifier is failed/waived and status approved raises no `verified-when-approved` (existence only): intended?
- A verifier with blank `v_status` is ignored; requirement can read `passed` or `not verified` although a verifier exists.
- Link names (`verifies`, `satisfies`, `refines`, `link_verifies`) hard-coded in rules/engine.py vs links.yaml: renaming makes rule and VCM disagree.
- Not checked: read-only project folder behaviour of item cache (root ignores permissions).
- Reading-only: `rvs selftest` validates with doorstop=False, so Doorstop's full validation path is never exercised in the frozen build (missing hidden import would not be caught by release selftest). One extra selftest step would cover it.


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
