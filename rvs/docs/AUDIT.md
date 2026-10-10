# Full audit of RVS (post-v1) — findings, fixes and what remains

Scope: everything in `rvs/` at commit `6eff710` (v1 plus the post-v1 items). Eight independent read-only audits were run
in parallel, each by a separate agent that had not seen the others' reports; the findings were then triaged here and fixed
test-first. Two audits did not finish (the test-suite audit and the performance audit were cut off by a usage limit);
what they had produced by then is included below and marked as partial.

| # | Audit | Report status |
|---|---|---|
| 1 | Spec compliance (every SPEC rule, data model item, milestone) | complete |
| 2 | Regression / second-order review of the earlier review fixes | complete |
| 3 | Test-suite quality (coverage, mutation probes, hygiene, flakiness) | **partial** (mutation probes and three full runs finished; no written report) |
| 4 | Documentation fact-check (guide, engineering docs, messages) | complete |
| 5 | Supply chain, packaging, repository hygiene, security posture | complete |
| 6 | GUI usability and accessibility (screenshots, keyboard, contrast) | complete |
| 7 | Performance, scale, robustness, concurrency, determinism | **partial** (measurements finished; report cut off before its closing summary) |
| 8 | Architecture and code quality | complete |

Verification status of the fixes: the full suite passes on Python 3.13 on Linux; ruff and mypy (strict) are clean. The
Windows CI job could not be checked from here (see "Not verified"). Numbers below that say "measured" were measured on a
shared 4-core Linux machine.

## 1. Fixed

### Data integrity and change control
| Finding | Fix | Test |
|---|---|---|
| A `.gitignore` entry (`VER/`, `baselines/`, `history/`) silently dropped project data from an immutable baseline; the name was then burned | Project data files (`.yml`, `.yaml`, `.jsonl`) are never left out; stray `*.tmp` files are never committed; after the commit the tree is checked to hold the manifest and every item, otherwise the baseline is refused and rolled back | `test_audit_core::test_gitignore_cannot_drop_project_data…`, `…commit_that_leaves_out…` |
| A failed tag left an orphan "Baseline" commit; a rollback that failed on one file skipped the rest | Each file restored on its own; the commit is taken back (`GitRepo.undo_commit`); the empty `baselines/` folder is removed | `…failed_tag_takes_the_commit_back`, `…one_unrestorable_file…` |
| History entries of the status promotion were written after the commit | Written before it, restored on failure | `…history_of_the_promotion…` |
| Two creators of the same baseline: the loser deleted the winner's manifest | The manifest name is reserved with an exclusive create before anything else; only the creator removes it | `…creating_the_same_baseline_twice…`, `…reserved_name_is_not_overwritten…` |
| Change-request creation hung when a file's `id` differed from its name; crashed on file systems without hard links; a corrupt file crashed several commands | Numbers come from ids and file names, retries are capped, exclusive-create fallback, YAML errors become `ChangeRequestError` | `…foreign_id…`, `…without_hard_links`, `…corrupt_change_request…` |
| Damaged Git metadata (tag pointing at a missing object) made the project unopenable | `orphan_tags` and `_tag_info` tolerate it | `…damaged_tag_objects…` |
| A tagged tree with a submodule entry crashed diff/verify/export; `assert` used as runtime check on dulwich data | Gitlinks and symlinks are skipped, assertions replaced by `GitError` | `…gitlink_in_a_tagged_tree…` |
| Quadratic stale-file scan in `commit_directory` | Set built once | `…commit_directory_stays_fast…` |
| `list_baselines` ignored the digest fallback after a folder rename; folder names containing `..` could never be baselined | Shared `_tag_for`; `..` handled by `_ref_safe` | `…follows_a_renamed_project_folder`, `…dots_in_its_name…` |
| Baseline names `BL1`/`bl1` and Windows device names (`CON`, `nul`, …) accepted | Refused with a plain message | `…windows_device_names…`, `…differing_only_in_case…` |
| A corrupt `baselines/*.yaml` raised raw parser errors from edit, export and list | Reads as empty; `rvs validate` reports `RVS-BASELINE-MODIFIED` | `…corrupt_manifest_is_reported…` |
| Import: a row for an inactive item's id was planned as "create" and failed half-way leaving an empty item | Plan refuses it ("inactive item"); numbering considers inactive items; a mis-numbered stray item is deleted | `…inactive_item_blocks…`, `…discard_item…` |
| XLSX rows after a gap of 1,000 empty rows were silently dropped; an unterminated CSV quote swallowed all following rows | Whole sheet read to the row limit; strict CSV parsing with a clear error | `…rows_after_a_long_gap…`, `…unterminated_csv_quote…` |
| Edits skipped type checks (`executed_on: next tuesday`, malformed `link_verifies` persisted) | `EditService` uses the same type rules as `rvs validate` (`rvs_core/attrtypes.py`); item IDs no longer accept a trailing newline or non-ASCII digits | `…type_checks_apply_to_edits`, `…item_ids_with_a_trailing_newline…` |
| Item files could be saved with the wrong permissions or replace a symbolic link by a regular file | Atomic write keeps the mode and follows links | `…keeps_permissions_and_symlinks` |
| Project files written with CRLF on Windows (Doorstop follows the OS default) | LF pinned in the adapter | `…unix_line_endings_on_every_system` |

### Security and offline guarantee
| Finding | Fix | Test |
|---|---|---|
| `!include` guard was a substring test: a `%TAG` handle read local files into findings | `.doorstop.yml` is composed and any non-standard tag refused | `…include_cannot_be_smuggled…` |
| YAML alias bomb hung validation for more than 60 s | Item files are scanned (linear, memoised) and refused above 2 million expanded nodes or 64 MB | `…alias_bomb…` |
| ReqIF DOCTYPE guard bypassed by UTF-16BE without a byte-order mark | Replaced by an expat probe that refuses any DOCTYPE or ENTITY in any encoding | `…reqif_doctype_is_refused_in_every_encoding` |
| `.rvs-cache` trusted blindly (a forged cache showed false requirement text); snapshot folders trusted on a marker file | Cache files and snapshot markers are signed with a per-user key kept next to the user's settings; unsigned or foreign ones are ignored | `…cache_that_this_computer_did_not_write…`, `…unsigned_snapshot_folder…` |
| Formula injection through configured matrix column titles | CSV headers protected, XLSX headers written with `set_text` | `…matrix_headers_cannot_carry_formulas` |
| XLSX export wrote requirement text to `/tmp/openpyxl.*` (spec rule 11) | Sheet XML kept in memory (documented patch of openpyxl's writer) | `…xlsx_export_writes_no_temporary_files` |
| Exports and user settings overwritten in place (a full disk truncated the previous file) | `rvs_core/atomicio.py` used by the CLI, the GUI and settings | `…failed_atomic_write_keeps_the_old_file` |
| Installer: Ctrl-C during the swap left no installation; a pre-existing `<prefix>.new` folder was deleted | Unique staging folder, restore on failure, INT/TERM handled | `tests/test_packaging.py` (several) |

### Errors and robustness
| Finding | Fix |
|---|---|
| Raw tracebacks from the CLI (`diff`, `baseline create`, Ctrl-C, unexpected errors) | One catch-all in `main()`: known error kinds print a message (exit 2 or 3), anything else saves a content-free crash report and exits 1; Ctrl-C exits 130; `RVS_DEBUG=1` shows the traceback (test: `…never_prints_a_traceback`) |
| The validation safety net lost the traceback and told users to "send the crash report" that was never written | It saves the report and names its path; `RVS_DEBUG=1` re-raises; an unreadable item names its file |
| Impact analysis overflowed the stack on a chain of about 1,000 links (CLI traceback; GUI Graph/Impact panels blank) | Iterative `flat()`; iterative tree building in the GUI |
| `rvs export --spec` failed with the default format; `--vcm -o x.xlsx` silently wrote CSV into a `.xlsx` file | The format follows the `-o` extension (csv by default, html for `--spec`, reqif for `--reqif`) |
| `exports.yaml` without `vcm` crashed export and the GUI tab; ragged `traceability.columns` | The schema requires `vcm.columns` and exactly five traceability names |

### Performance
| Finding | Measured before → after |
|---|---|
| `export --spec --format docx` quadratic (python-docx scans the whole body per paragraph) | 5,000 items 47 s → linear (1,000 items 1.7 s, 4,000 items 6.0 s) |
| `export --spec --format pdf`, one very long statement (cubic in ReportLab) | 200 KB statement 124 s → 0.2 s (long text is laid out in 4,000-character pieces) |
| Quadratic stale-file set in `commit_directory` | 20,000 files 21.9 s → milliseconds |
| Import dialog re-read every manifest on each keystroke | read once per dialog |

### GUI (audit 6)
All five blockers and the major findings that could be done safely: keyboard users are no longer trapped in tables or text
boxes (Tab moves on; explicit tab order; new **F4** "Focus editor"; Enter on a row opens the editor); a visible focus ring
and disabled/secondary button styles; the window can shrink to a laptop screen (≤ 1100 × 640); Revert, wizard Cancel and
the glossary no longer discard input silently; baselines can be created from example projects (the dialog offers to turn
on version control, says a baseline is permanent, and refuses edits while one is being created); notifications name their
severity in words; contrast failures fixed (warning text, selected rows, placeholders, checkbox indicators); the Problems
panel opens tall enough and rows activate with Enter; every input and table has an accessible name; matrix, change and
diff rows open their item; dialogs validate before closing; plain-language open errors, labels and counts; empty states;
Ctrl+S keeps keyboard focus; full validation and File > Open run in the background; window layout and column widths are
remembered; an unset required choice no longer opens an item as "modified". About 90 new tests in
`tests/test_audit_gui_*.py` and `tests/test_gui_*.py`.

### Documentation, packaging and repository (audits 4, 5)
Guide rewritten where it was wrong (baselines and Git, coverage tab, VCM shading, reasons after a baseline, Doorstop
"needs initial review" info, shortcuts, install prerequisites, performance wording) and extended (Doorstop introduction,
glossary, recording verification results, retiring an item, adding a document, settings and shortcut IDs, rule parameters,
exit codes). Engineering docs corrected (superseded decisions marked, ARCHITECTURE as built, DEVIATIONS V26–V31 added).
Release build now runs in a clean virtual environment with a pinned PyInstaller, deterministic archive, licences and SBOM
inside the bundle, pruned Qt plugins (204 → 179 MB), installer checks for missing xcb libraries and old glibc; `sdist`
complete; `license` metadata modernised; `.gitattributes`/`.gitignore` completed; CI matrix 3.11–3.13 with a headless GUI
smoke step. Many message texts made actionable (reason prompts, change-request statuses, baseline hints, glossary hint).

## 2. Test-suite audit (partial) and what we did with it

About 225 mutation probes (one-line defects injected into the source, each run against the tests that should catch it):
147 caught, 57 survived, 19 hit code no test reached. The survivors were re-examined against the new tests
(`tests/test_audit_gaps.py`): 43 of the 54 re-runnable probes are now caught. The other 11:
- 4 are equivalent mutants (a second check on the same path catches the same case: B03, B15, V27, K18);
- 3 are redundant checks that cannot fail alone through the public API (I03, I12, I14);
- 4 are GUI probes that this core-only harness does not exercise (J04, J05, E02, P01); GUI tests cover that code.

One real flake was found and fixed: `test_small_stress_project_is_valid_and_deterministic` compared a folder that the
item cache writes into, failing whenever the machine was slow enough for the 2-second "racy file" rule to trigger.
One intermittent interpreter crash (Python 3.11, garbage collection inside a worker thread during the export test) was
seen once in four full runs and not reproduced; as a mitigation, garbage is now collected on the GUI thread when the
last background job ends. This is a hypothesis, not a confirmed root cause.

## 3. Not fixed (deliberate, with reason) — see also DEVIATIONS V24, V26–V31

- **No locking between concurrent writers** (V29): two editors changing different fields of the same item can lose one
  write (4 of 60 in the stress test); files stay valid. A multi-user lock was out of scope.
- **Kill during `baseline create` or `import`** (SIGKILL, power loss) leaves partial state: a manifest without a tag
  (`RVS-BASELINE-NOTAG`, recoverable by hand) or a partly applied import (re-running completes it). Failures that raise
  are rolled back fully; a hard kill cannot be.
- **`apply_import` is not transactional** across rows (it plans completely first, so errors are rare after that).
- **Git line-ending filters** (`core.autocrlf`, `.gitattributes eol=`) apply to files staged for a baseline commit;
  item digests are computed from parsed content so verification is unaffected, but non-YAML attachments inside a
  project can differ in a snapshot.
- **Snapshot cache is never cleaned** (one project copy per baseline viewed; V30).
- **Doorstop's own full validation is super-linear** (5,000 items 4.7 s, 20,000 items 52 s; 400 documents 6.5 s); RVS's
  own checks (`--fast`) are linear. The cold open of 5,000 items was measured at 3.2–3.5 s under load against the
  "under 3 s" target (warm: 0.65 s).
- **Linux bundle portability** (V28): built on Ubuntu 24.04 it needs glibc 2.38 and the xcb helper libraries; the
  installer now warns, the docs say so, but a manylinux/RHEL 8 build was not made. Use the wheelhouse on older systems.
- **No hashed lock file** (V27): `scripts/make_lock.sh` is provided (needs network); hashes were not fabricated.
- **Editing `derived`, `normative`, `level`, `header`, `ref`, `active`, adding a document, recording Doorstop review**
  are only possible through CSV/XLSX import or by hand (V31).
- **Evidence has no format check**, generic `ref-list` links have no editor control, `no-implementation` ships with an
  empty term list, schema version is not stored in `history/*.jsonl` and `settings.json`.
- **Architecture items** (audit 8) judged too large for this pass and left as recommendations: a common `RvsError`
  hierarchy (only the CLI catch-all was added), link roles in `links.yaml` instead of hard-coded link names in about
  14 places, one attribute-type codec for validation/import/editing/widgets (partly done: `attrtypes.py`), splitting
  `itemsio.py`, `reqif.py`, `validate.py`, `app.py`, internal import-cycle contracts, `session.refresh()` on a worker
  thread, a documents-only dock, a tick glyph in checkboxes.
- **Cannot be done offline here:** ReqIF XSD validation, `pip-audit` against OSV, code signing, a real Windows run.

## 4. Not verified

- **Windows.** The first CI run on Windows (before this pass) failed 7 tests; the run after the audit fixes failed 78,
  and the log showed why: (1) item paths came back with backslashes, so the new "baseline commit holds every item"
  check refused every baseline (56 tests) and several path assertions failed; (2) DOCX/XLSX bytes differed from the
  goldens because ZIP members record a "created on" byte that is 0 on Windows and 3 elsewhere; (3) Doorstop wrote CRLF.
  All three are fixed (item paths are POSIX, `create_system` is pinned, LF is pinned) and covered by Linux tests; the
  Windows run itself has to be re-checked in CI. The Windows installer and build scripts have never been run.
- Real screen readers, native file dialogs, a real 1366 × 768 desktop, macOS.
- Python 3.14 (not supported by the pins).
- The root-level Linux/macOS/Windows workflows of the bundled Doorstop clone hardcode the upstream repository path and
  fail on every commit; they are outside `rvs/` and were not changed.
