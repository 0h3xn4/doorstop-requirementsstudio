# Pre-release audit: Test-suite quality

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

(status: written early; mutation campaign is PARTIAL, 27 of 110 mutants run; section "Mutation probes" says exactly which. Appended to as more is confirmed.)

## Coverage
Files read in full: rvs/tests/conftest.py, golden_support.py, golden/ (manifests + sampled files), all 63 test_*.py (adapter ... yaml_loader, incl. all test_audit_*, test_gui_*, test_review_*, test_packaging, test_performance), pyproject.toml (pytest/ruff/mypy config), .github/workflows/rvs-ci.yml (+ the three upstream workflows), docs/AUDIT.md, CLAUDE.md, CONTRIBUTING.md. Source read for judging: changecontrol/baselines.py, changes.py, manifests.py, diff.py, authoring.py, atomicio.py, adapter/cache.py, adapter/doorstop_adapter.py, vcs/git.py, validate.py, rules/engine.py, trace/*.py, exporters/itemsio.py (all), rvs_cli/main.py, rvs_cli/changecontrol.py.

Tests run (own venv in scratch, `coverage` 7.16 branch+subprocess, fake HOME/TMPDIR, PYTHONPATH=src, one pytest at a time, `-p no:cacheprovider`, no `-m perf`):
- 826 tests collected, 6 deselected (all in tests/test_performance.py, marker `perf`), 820 run: ALL PASS on Linux / Python 3.13.16, 0 skips, 0 xfails, 0 warnings. (Groups: core1 180, core2 302, cli+misc 60, gui1 97, gui2 153, packaging 28; test_offline needs the package installed because it runs `python -I`, PYTHONPATH is ignored there - an artefact of my venv, passes once the src path is a .pth.)
- ruff check, ruff format --check, mypy (strict, src only): all clean.
- Hypothesis property tests (7 tests) re-run in-process with 25 different seeds (`hypothesis.seed(n)`), 175 runs x 12 examples: 0 failures.

Coverage of src/ (combined 7 runs, branch coverage on):
- ALL: 9455 statements, line 93.3 %, branch 85.8 % (2259/2632), combined 91.7 %.
- rvs_core: line 95.4 %, branch 90.9 %; rvs_cli: line 95.3 %, branch 90.9 %; rvs_gui: line 90.9 %, branch 76.0 %.
- Lowest modules: rvs_gui/crash.py 48 %, help_viewer 73 %, core/guide.py 75 %, gui/baselines_view 76 %, gui/app.py 80 % (branch 76 %), gui/diff_view 83 %, attrtypes 84 %, textcheck 84 %, vcs/git.py 86 %, config/loader 89 %, cache.py 91 %, diagnostics 91 %, doorstop_adapter 92 %, itemsio 93 %, cli/main 94 %, baselines 95 %, reqif 95 %, validate 96 %, authoring 98 %, atomicio 100 %. Full report: scratchpad/audit/tests/cov-report.txt and cov.json.

Probes run (non-pytest): XLSX typed cells (date/float/bool) import - works; ref-list `link_refs` CSV/XLSX round trip - works; two root documents -> RVS-TREE-INVALID exit 3 - works; non-ASCII/emoji/space project path with baseline create/verify/export + LANG=C - works; racy-file margin (0.03 s vs 2 s limit even at load 7) ; no-op edit on baselined item; git identity with machine git config.

## Findings

### TESTS-01 Manifest-name reservation race (O_EXCL) fix has no test that reaches it
- Where: src/rvs_core/changecontrol/baselines.py:193-198 (`path.open("x")` / `except FileExistsError`); tests/test_audit_core.py:113 (`test_a_reserved_name_is_not_overwritten_by_a_loser`)
- Severity: medium
- Confidence: verified (coverage: lines 195-196 never executed in 820 tests)
- What is wrong: AUDIT.md lists "two creators of the same baseline: manifest name reserved with an exclusive create" as fixed and tested by `...reserved_name_is_not_overwritten...`. That test pre-creates `baselines/R1.yaml`, so `create_baseline` stops at the earlier `manifest_path(...).exists()` check (line 158); the exclusive-create branch and the "loser must not delete the winner's manifest" logic are never run. Replacing `open("x")` by `open("a")` would not be noticed (mutant B17 not yet run, coverage proves the branch is dead to the suite).
- Evidence: `coverage report` missing lines for baselines.py: `195-196, 205-206, 259, 281, 323-324, 331-332, 432`.
- Why it matters: the only protection against two users/processes creating the same immutable baseline is untested.
- Proposed fix: test that monkeypatches `manifest_path(...).exists` to False for the first check (or creates the file between check and open via a patched `Path.open`) and asserts the winner's file is intact.
- Test that would catch it: as above.

### TESTS-02 Ctrl-C (BaseException) during baseline creation: roll-back untested
- Where: baselines.py:232 `except BaseException:`; tests/test_audit_core.py:66, tests/test_review_cc.py:102 (only raise GitError)
- Severity: medium
- Confidence: verified (mutant B02 `except BaseException` -> `except Exception`: 55 s run of test_baselines/audit_core/audit_gaps/review_cc/diff/cli_changecontrol, SURVIVED)
- What is wrong: no test raises KeyboardInterrupt/SystemExit inside create_baseline; the promotion of statuses, history entries, manifest and commit would stay behind after Ctrl-C and nothing would notice the regression. AUDIT claims "failures that raise are rolled back fully".
- Proposed fix / test: monkeypatch `GitRepo.create_tag` to raise KeyboardInterrupt, assert files, history and HEAD unchanged and the name reusable.

### TESTS-03 Baseline digest sensitivity to parents / normative / derived is untested; verify compares a function with itself
- Where: baselines.py:86-94 (`item_digest`), tests/test_baselines.py:193 (`test_manifest_is_deterministic_for_identical_content`), 201
- Severity: medium
- Confidence: verified (mutants B03 `"parents": []` and B04 `"normative": True` SURVIVED; B05 attrs dropped was killed)
- What is wrong: `test_manifest_is_deterministic_for_identical_content` creates ONE baseline and compares its manifest with `item_digest()` of the same items (expectation built by the function under test; it never creates the "identical content" twice). Deep verify (`verify_baseline`) compares manifest digests with digests of the tagged tree computed by the same function, so a digest that silently ignores parent links or the normative flag would let a re-parented or de-normativised item pass as "intact". No test changes a parent link / normative / derived / level / header and expects a different digest.
- Proposed fix: extend `test_item_digest_changes_with_content...` with one change per payload field (parents, normative, derived, active, header, ref, level, document, text).

### TESTS-04 More surviving baseline mutants (edge checks)
- Where: baselines.py: line 158 tag-exists check (B01 SURVIVED), 241 manifest required in committed tree (B06 SURVIVED), 416 `(root/CACHE).is_symlink()` (B07 SURVIVED, only the `snapshots` link is tested), 304 digest check in the renamed-folder fallback (B08 SURVIVED: two projects with the same baseline name in one repo are never tested), 321 `"/" not in ...` nested-project tags in `orphan_tags` (B09 SURVIVED), 31 name length 64 vs 65 (B10 SURVIVED, only 80 chars tested).
- Severity: low-medium
- Confidence: verified (mutation, tests listed above stay green)
- B11 (whitespace-only deferral reason) also survived but is an equivalent mutant: `ChangeRequestStore.defer` repeats the check.
- Proposed fix: one test each (name reused after manifest deletion with tag present; commit lacking manifest; `.rvs-cache` symlink; two projects with baseline PDR, rename one; nested project tags; 64/65 char names).

### TESTS-05 atomicio.py's own contract (permissions, symlinks) is not tested; AUDIT's "keeps_permissions_and_symlinks" tests the other writer
- Where: src/rvs_core/atomicio.py:233, 225; tests/test_audit_core.py:276
- Severity: medium-low
- Confidence: verified (mutants O01 chmod removed and O02 `realpath` removed both SURVIVED in test_audit_core/small_findings/review_io/cli_export/cli_import_export/userconfig/guide/diagnostics)
- What is wrong: `test_saving_an_item_keeps_permissions_and_symlinks` goes through the adapter's `_atomic_write_text`. `atomicio.write_bytes` (CLI exports, guide copy, GUI exports, user settings) loses the mode of an existing file and replaces a symlink with a regular file - untested. Only the failure path (`test_a_failed_atomic_write_keeps_the_old_file`) is tested.
- Proposed fix: copy the permissions/symlink test for `atomicio.write_bytes` and `write_text` (CRLF -> LF).

### TESTS-06 Authoring history details unprotected
- Where: authoring.py:85 `why.strip()` (A01 SURVIVED), 183 whitespace-only text change (A03 SURVIVED), 171 `"links"` in create history (A04 SURVIVED), 168 template defaults merge (A08 SURVIVED because Doorstop document defaults supply the same values)
- Severity: low
- Confidence: verified (mutation)
- Proposed fix: assert stored `why` is trimmed; edit with whitespace-only difference leaves no history; create history lists `links`.

### TESTS-07 Module-scoped golden fixtures run before the autouse "isolated user config" fixture
- Where: tests/conftest.py:28 (`_isolated_user_config`, function scope) vs tests/test_golden.py:16-23 (module-scoped `minimal_outputs`, `satellite_outputs` call `validate_project`, which creates the signing key via `cache._key()`)
- Severity: medium (test isolation)
- Confidence: likely (after the run `fakehome/.config/rvs/cache.key` existed although every test sets RVS_CONFIG_DIR; module-scoped fixtures are instantiated before function-scoped autouse ones). I could not attribute it to a single test while the lead's full suite was running; to confirm run `HOME=<empty> pytest tests/test_golden.py` and look at `$HOME/.config/rvs`.
- Why it matters: the suite writes into the developer's real `~/.config/rvs` (cache.key) - the thing conftest says no test may do; on a read-only HOME CI the golden tests would behave differently.
- Proposed fix: make the isolation fixture session/module scoped as well (set RVS_CONFIG_DIR in `pytest_configure`), or depend on it from the golden fixtures.

### TESTS-08 Tests write `.rvs-cache` into the repository's examples/
- Where: tests/golden_support.py:20 (`validate_project(EXAMPLES/name)`), tests/test_offline.py:75 (probe validates `examples/minimal10` in place)
- Severity: low
- Confidence: verified (`find rvs -newer stamp` after the run lists examples/minimal10/.rvs-cache/*.json and examples/satellite300/.rvs-cache/*.json; git-ignored, so `git status` stays clean)
- Why it matters: a read-only checkout, or running the tests from an unpacked sdist, writes into the source tree; the cache signed with the developer key is later copied by tests that `copytree(EXAMPLES/..)` without ignoring `.rvs-cache` (test_gui_authoring.py:28, test_gui_io.py:139, test_gui_matrices.py:447).
- Proposed fix: copy examples to tmp_path first.

### TESTS-09 Assertions that cannot fail or hardly can (file:line)
- Severity: medium (test quality) / Confidence: verified by reading (AST scan + manual)
- tests/test_audit_gui_dialogs.py:280 `A and B or A` (B irrelevant)
- tests/test_audit_gui_editor.py:59 `a is not b or c is not None` (second operand always true); :141 `"1 error" not in t or "1 errors" not in t`; :142 `"1 warning" in s or "warnings" in s`; :144 `" errors" in s or "1 error," in s`; :162 assertion only inside `if button.isEnabled()`; :221 `assert ItemChange` and the test (`test_diff_rows_navigate`) only checks an empty index does nothing
- tests/test_audit_gui_theme.py:87 `... or name == "light"` (light never checked)
- tests/test_review_gui.py:111 `if before:` conditional assert; :488 `... and Qt`; :429 `kind in ("info","error")`
- tests/test_small_findings.py:152 `"Odd" in str(x) or isinstance(x, Exception)` (always true); :194 `X in html or "color:" in html`
- tests/test_reqif.py:304 `"3 created" in out or "create" in out`; :228 `FOREIGN.replace(a, a)` no-op; :275 `root is not None`
- tests/test_review_cc.py:248 `x == [..] or "SYS-0001" in x`; :249 `read_history(...) is not None` (always a list); :262 `assert hashlib and json`; :84 `"x.lock.y"[:0] + "WORKING"` dead expression
- tests/test_review_core.py:393 `exit_code in (0,1,3)` also accepts the RVS-VALIDATION-FAILED crash path; :443 `in (0,1)`; :542 `depth["X"] == 2 and load_project_config` (second operand tautology, unused import)
- tests/test_audit_gaps.py:291 `assert fresh.uid`; :229 (K11) only reads configuration, runs no rule
- tests/test_audit_core.py:525 `sys.version_info >= (3, 11)`; :163 `exit_code != 3`; :191 commit_directory timing bound 20 s for 3000 files cannot detect the quadratic regression it names; :369 deep-chain test only counts
- tests/test_review_io.py:286 `test_stdout_text_survives_a_legacy_console_encoding` never sets a legacy encoding (`monkeypatch` unused) and ends with `assert EditService`; :163 `len(rows) <= 2`
- tests/test_links.py:361 `test_satisfies_from_verification_item_is_rejected` asserts only configuration; tests/test_graph_layout.py:21 `test_siblings_in_a_layer_are_spread_horizontally` compares y coordinates only
- tests/test_itemsio.py:124 name promises "excel_style_numbers", only CRLF is tested
- tests/test_baselines.py:193 (see TESTS-03), :305 name says "tampered tree", tests only the manifest (tree tampering is test_audit_gaps B16, via monkeypatch)
- tests/test_packaging.py:96 Windows installers are "tested" by `read_text().startswith("#")`; :357/:355 are substring checks of the .ps1 text
- tests/test_adapter.py:89, :97 (no assertion except "no exception"), tests/test_performance.py:61 prints only
- tests/test_diff.py:195 "reused" snapshot only compares item dicts, not that extraction is skipped
- tests/test_audit_gaps.py: expectations built from src (`SEEDED_DEFECTS` in tests/test_satellite_example.py:276 comes from `rvs_core.examples.satellite`)
- Exception classes without `match=` (accept any message of that class): test_audit_core.py:75,117,452; test_review_cc.py:78,87,112; test_review_core.py:145.

### TESTS-10 Untested behaviour (from coverage: lines never executed) that matters
- Severity: medium; Confidence: verified (coverage)
- validate.py: `RVS-SCHEMA-MISSING` (149), `RVS-SCHEMA-OLDER` (163), the doorstop "no child"/"suspect link" translators (244, 259), "no repository -> skip baseline checks" (382-383); `RVS-TREE-INVALID` never asserted anywhere (works when probed).
- baselines.py: 157 invalid tag name, 205 deferral error, 259 rollback of a history file that did not exist before, 281, 323-324 damaged Git swallowed, 331 unparseable `created`, 432.
- git.py: `.tmp`/`.git` file skip (121; mutant G01 not yet run), `undo_commit` "HEAD moved" no-op (156), all GitError wrappers (165, 187-195, 212, 236-239, 253, 267, 327-330), lightweight tags (277), `_login` fallback (45-48).
- itemsio.py: XLSX typed cells date/float/bool (192-198; works when probed), int decode error (341-344), the whole ref-list decode (366-369), `free_attributes` columns (51-52), CSV rows with extra cells in `plan_import` (441-442), malformed ID (450), numbering-mismatch clean-up (664-665), creating inactive items / items with `ref` (doorstop_adapter 429, 431).
- doorstop_adapter.py: tree cannot load (220), item file unreadable on edit (290), oversized/odd item files (91-96), create_document failure.
- cli: `rvs init` without name, `rvs guide` without -o / guide missing, BrokenPipe, `_unexpected` for known error kinds / YAMLError / `RVS_DEBUG` (main.py 269, 315-321, 333, 349, 362-366), `--fast` never passed to the CLI in any test, "not an RVS project" exit 3 for baseline/cr/diff, "No baselines yet.", empty `-m`.
- diff.py: `diff_doc` for added/removed items (192-195) and the MAX_DIFF_TOKENS fallback (62-64): `test_diffing_very_long_statements_stays_fast` takes the head/tail-trim shortcut.
- config/loader.py: 5 consistency errors (144, 150, 182, 189) and non-mapping config (44) - no negative tests.
- cache.py: no key / unwritable folder (48-49, 128, 133-137).
- changes.py: no-hard-link fallback race (142), retry exhaustion (163), non-mapping CR file (65).
- reqif.py: inline `i/em/code/br` XHTML import, parse-failure fallback (79-81), executed_on datetime truncation (592).
- docx_out/pdf_out: Entry rationale and bullet lists in spec documents.
- Not tested at all: Windows path handling (only monkeypatched `sys.platform` in test_userconfig), read-only project folder (cannot be done as root; cache.save OSError path is dead), real SIGINT/SIGTERM of the CLI, huge inputs beyond the few bounded cases, concurrent GUI+CLI writers, case-insensitive file systems.

### TESTS-11 Flakiness / environment dependence
- Severity: low; Confidence: mix (see each)
- tests/test_cache.py:140 `test_recently_modified_files_are_never_cached` depends on < 2 s between building the project and the second open (verified by delaying 2.2 s: hits 10 instead of 0). Margin measured 0.03 s at load average 7, so only a stalled VM/CI runner would trip it (likely-low).
- tests/test_gui_io.py:137 `test_window_stays_responsive_while_exporting`: asserts tick count and max gap < 0.5 s while a worker thread renders a PDF (GIL contention) - machine speed dependent (reading-only; not yet repeated 10x).
- Pixel/geometry/font-metric tests (test_audit_gui_theme.py focus ring, disabled colour at pixel (4,4)/(6,6); test_audit_gui_layout.py window/wizard sizes, column widths; test_gui_editor_layout.py `visible >= 8`) depend on the Qt style/fonts and screen of the platform (reading-only).
- Timing bounds: test_audit_core.py:191 (<20 s), :272 (<10 s), :433 (<30 s), test_review_cc.py:260 (<5 s) - generous.
- test_audit_gui_dialogs.py:309/317 click a modal box from a 100 ms `QTimer.singleShot`; if the box is not up in time the AssertionError is raised inside the timer and `exec()` blocks forever (no pytest-timeout is configured) - hang risk (reading-only).
- Hypothesis: no seed / derandomize / database setting, `deadline=None`; tests re-seed every run (CI may red on a rare real counterexample that cannot be reproduced without `.hypothesis`). 175 extra seeded runs found nothing.
- Global state: test_gui_theme.py:281 `theme.TOKENS == theme.LIGHT` depends on every earlier test restoring the theme (restore fixtures exist in 3 files; I have not yet run the reversed order).
- Environment: tests do not clear SOURCE_DATE_EPOCH / TZ / LANG; test_authoring.py:78 needs a resolvable OS user (getpass) ; test_userconfig.py:261 writes to `/proc/definitely/not/writable` (would create `C:\proc\...` on Windows when run as admin); test_examples.py:19 and test_review_cc.py use the `git` executable and the developer's global git config.
- Isolation: no leftover files in the fake TMPDIR except pytest-of-root; no writes to the real HOME found in the repo-local runs except TESTS-07.

### TESTS-12 CI parity
- Severity: medium-low; Confidence: verified by reading rvs-ci.yml + docs
- Run on every push/PR touching `rvs/**`: ubuntu + windows, py 3.11/3.12/3.13: `pip install -e .` + `--version`, headless GUI start, `pip install -e .[dev]`, ruff check, ruff format --check, mypy, `pytest` (= `-m "not perf"`). So: the 6 perf tests (open 5,000 items < 3 s, matrices < 5 s, GUI responsiveness) NEVER run in CI; macOS is not tested (docs say so); on Windows the whole of tests/test_packaging.py (28 tests) and all symlink/permission tests are skipped, PDF goldens are skipped off Linux (test_golden.py:23).
- dev dependencies are `>=` only (pytest, pytest-qt, hypothesis, mypy, ruff, pypdf, fonttools): with `filterwarnings=["error"]` any new deprecation warning in a new tool release turns CI red and `ruff format --check` output changes with ruff versions; no lock for dev tools, no `pytest-timeout`, no coverage measurement or threshold anywhere in the repo (no `[tool.coverage]`), no random-order run, no `rvs selftest` step.
- The three upstream workflows (test-linux/osx/windows.yml, `_common.yml`) run on every push of this fork and are documented as failing (AUDIT.md section 4); `package` job only builds Linux.
- pytest config itself is sound: `--strict-markers`, `-ra`, `testpaths`, `-m "not perf"` overridable with `-m perf`.

### TESTS-13 (product, untested branch) Git identity mixes the given user name with the machine's e-mail
- Where: src/rvs_core/vcs/git.py:222-233 (`_identity`); test tests/test_vcs_git.py:85 only checks the name
- Severity: low; Confidence: verified
- Evidence: with a global git config `user.name=Bob Machine, user.email=bob@corp.example`, `GitRepo._identity("alice")` -> `b'alice <bob@corp.example>'`. If only `user.email` is configured the e-mail is ignored (KeyError on `user.name` aborts the lookup).
- Why it matters: the baseline commit/tag is the audit evidence; it attributes alice with bob's address.
- Proposed fix: take the e-mail from config only when the name is also taken from config, else `name@localhost`.

## Mutation probes (PARTIAL: 27 of 110 prepared mutants run; campaign was cut off)
Harness: scratchpad/audit/tests/{mutations.py,run_mut.py,mut/results.jsonl}; mutants applied to a COPY of the whole rvs tree (PYTHONPATH trick), `pytest -x` on the covering files. Killed (11): B05 attrs dropped from digest, B12 baselines listed alphabetically, B13 unsigned snapshot trusted, B14 commit not taken back, B15 Windows device names, B16 deep verify never reports corrupt, A02 whitespace reason accepted, A05 history appended to unterminated line, A06 set_parents no-op writes history, A07 baselined items need no reason, A09 CR closed accepted.
SURVIVED (16, i.e. tests stay green): B01, B02, B03, B04, B06, B07, B08, B09, B10, B11 (equivalent), A01, A03, A04, A08 (equivalent-ish), O01, O02 - see TESTS-02..06.
Prepared but not yet run (110 total): cache (C01-C08), git (G01-G10), validate (V01-V13, incl. severity changes), rules (R01-R08), trace (T01-T08), itemsio (I01-I17), cli (CL01-CL12), diff/CR (D01-D05, CH01-CH04), baselines B17-B19, atomicio O03-O04. Predicted survivors from coverage: C03, G01, G04, G06, G08, V02/V03/V08, R01, T02, T03, I01/I02/I05-I07/I14-I17, CL01-CL04/CL06/CL07, D01, D04, D05.

## Checked and found correct
- The suite is green and deterministic on this platform: 820/820 on three groupings, 0 skips, 0 warnings under `filterwarnings=error`; ruff, ruff format, mypy strict clean.
- Golden tests compare against committed files/hashes and do not regenerate on run; PDF bytes compared on Linux only; outputs of the golden projects are byte-stable.
- No hidden `pytest.raises(Exception)`, no `assert True`, no `x >= 0`, no try/except swallowing AssertionError, no test without any assertion except test_adapter.py:89 (intentional "no temp file").
- Property tests: 175 extra seeded executions, no counterexample.
- Non-ASCII/emoji/space project path works for validate, baseline create/list/verify, xlsx export, also under LANG=C.
- XLSX typed cells, ref-list round trip, two-root tree error all behave correctly although untested.
- The racy-cache test has a >50x timing margin on a loaded 4-core machine.

## Questions about intended behaviour
- Should editing a baselined item with an unchanged value (no-op edit, `clear_suspect` with nothing suspect) require a reason? Today `EditService.update_item/clear_suspect/set_parents` raise ReasonRequiredError before the "nothing changed" shortcut (verified).
- Is the 100 ms `QTimer` + modal `exec()` pattern in test_audit_gui_dialogs.py acceptable without a pytest timeout?


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
