# Pre-release audit: Command line (every command run)

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

## Coverage
Files read in full: src/rvs_cli/main.py, output.py, changecontrol.py, __init__.py, __main__.py, packaging/launch.py, packaging/launch_cli.py, docs/guide/06-command-reference.md, docs/user-manual/08-command-line.md, docs/getting-started.md, docs/AUDIT.md, CLAUDE.md, DECISIONS/DEVIATIONS; tests test_cli, test_cli_validate, test_cli_export, test_offline (full), names/assertions of test_cli_import_export and test_cli_changecontrol.

Probes run (scratch dir: .../scratchpad/audit/cli/, table of all runs in table.md; mutation log in mut/mut.out):
- --version / `python -m rvs_cli` / launch_cli.py / no args / unknown command / --help of every command and sub-command.
- validate: text, json, --strict, --fast, missing path, a file, non-project folder, broken item YAML, binary item, broken config, broken project file, empty project file, duplicate level, link cycle, self link, document cycle, read-only folder (root with DAC caps dropped via setpriv), unreadable folder/config/item, symlink, trailing slash, `..`, cwd elsewhere, `~`, SOURCE_DATE_EPOCH.
- init: every template, --list-templates, --git (also in a git parent, in a folder that already has .git), existing/non-empty/file target, nested project, odd names (empty, spaces, newline, control char, 5000 chars, unicode, colon, CON), 300-char folder name.
- export: all 7 selectors x 7 formats (49 combos), every -o form (extension, no extension, upper case, mismatch, missing dir, directory, `-`), filters (--document/--method/--level/--status/--only-gaps/--baseline) on every selector, conflicting/no selector, unknown UID/doc, bad --trace forms, huge args, baseline export of all selectors, tampered baseline.
- import: csv/xlsx/reqif, dry-run, --skip-errors, --reason, --cr, --user, --document, --map, empty/zero-byte/random/semicolon/latin-1/UTF-16/NUL/unterminated CSV, DOCTYPE reqif, baselined item without reason, idempotency.
- cr new/list/show/status/defer, baseline create/list/verify (names, --defer, --init-git, no Git), diff (all formats, unknown baseline/document), selftest (--manifest ok/missing/tampered/garbage/binary), guide (-o forms).
- Environment: closed stdout, /dev/full, `| head -1` on large outputs, PYTHONIOENCODING=ascii/latin-1/cp437, LC_ALL=C (+PYTHONUTF8=0), RVS_DEBUG, SIGINT at start-up and mid-export, strace of writes/exec/sockets, timestamps/TZ/SOURCE_DATE_EPOCH variants and different USER.
- Every example command in guide/06, user-manual/08, getting-started.md (and the commands in the other user-manual pages and docs/demo) was executed.
- 46 mutation probes on main.py / changecontrol.py / output.py against the CLI-related test files (see "Checked and found correct").
Tests run: targeted CLI test files only (40 + subset) on a copy of src in scratch; all pass unmutated.

## Findings

### CLI-01 `export --reqif --format csv|json|html` silently writes ReqIF; `--format docx` is refused with a wrong reason
- Where: src/rvs_cli/main.py:151 (`_request`: `"reqif" if kind == "reqif" else args.format`), :166
- Severity: medium
- Confidence: verified
- What is wrong: for `--reqif` the requested format is overwritten with "reqif". An explicit `--format csv` (or json/html) is accepted and ignored, the output is XML. `--format docx|pdf|xlsx` is refused with "writes a binary file; give --output" although the real problem is that ReqIF cannot be written in that format; with `-o f.docx` it writes ReqIF into a file called f.docx. The guide (05-import-export) says "An explicit --format always wins over the file name".
- Evidence: `rvs export ex_min --reqif --format csv | head -c 40` -> `<?xml version='1.0' ...`, rc 0. `rvs export ex_min --reqif -o r3.xlsx` -> rc 0, `file r3.xlsx` = "XML 1.0 document". `rvs export ex_min --reqif --format docx` -> `--format docx writes a binary file; give --output FILE.` (rc 2). Compare `--vcm --format reqif` -> "vcm can be written as csv, ..., not reqif" (correct).
- Why it matters: an option accepted but ignored; a .xlsx/.docx file that is XML cannot be opened by the user's tool.
- Proposed fix: do not force the format; let `build_output` refuse non-reqif formats for `reqif` with the same "can be written as" message; for `--reqif -o x.csv` default to reqif only when the extension is not a known format (or refuse).
- Test that would catch it: `main(["export", p, "--reqif", "--format", "csv"]) == 2` and `main(["export", p, "--reqif", "-o", "x.xlsx"])` must not write XML.

### CLI-02 Filter options are accepted and silently ignored for selectors they do not apply to; typos in filter values give an empty matrix with exit 0
- Where: src/rvs_cli/main.py:62-76 (argparse), `_request`
- Severity: medium
- Confidence: verified
- What is wrong: `--document`, `--method`, `--level`, `--status`, `--only-gaps` are only honoured by some selectors (help text says "VCM: ..."), but nothing is refused for the others. `export P --items --document SYS` outputs ALL documents (the output is re-importable, so a user may believe they got a subset); `--trace/--coverage/--impact --document X`, `--coverage --method test`, `--items --only-gaps` are ignored too. Values are not validated: `--method zzz`, `--method TEST` (case), `--status zzz --level zzz` print an empty matrix with only the header and exit 0. `--baseline ""` is treated as "no baseline". `import --document/--map` with csv/xlsx are ignored as well (documented "ReqIF only", still silent).
- Evidence: `rvs export ex_min --items --document SYS` -> rows of SYS, EPS and VER; `rvs export ex_min --vcm --method TEST` -> header only, rc 0; `rvs export ex_min --impact SYS-0001 --document EPS` identical to without `--document`; `rvs import q upd.csv --map foo --dry-run` rc 0.
- Why it matters: silent wrong output; a CI check built on "empty matrix = no gaps" would pass on a typo.
- Proposed fix: parser/`_export` error (exit 2) when a filter is given with a selector that ignores it; validate --method/--level/--status/--document against the configured vocabulary (unknown value -> message listing the valid ones).
- Test that would catch it: `export --items --document SYS` returns 2 (or only SYS rows); `export --vcm --method nope` returns 2.

### CLI-03 Error messages for I/O failures name the internal temp file, not the path the user gave
- Where: src/rvs_cli/main.py:335-337 (`except OSError`), rvs_core/atomicio
- Severity: low
- Confidence: verified
- What is wrong: the message prints `exc.filename`, which is the atomic-write temp name (`.NAME.PID.ID.tmp` in the target's folder).
- Evidence: `rvs export ex_min --vcm -o o` (o is a folder) -> `rvs: Is a directory (/.../cli/.o.8785.140501761036416.tmp)`; `-o o/nodir/sub/vcm.csv` -> `rvs: No such file or directory (/.../o/nodir/sub/.vcm.csv.8764.140111144845440.tmp)`; read-only target -> `Permission denied (.../.out.csv.23454....tmp)`; `guide -o .` same.
- Why it matters: misleading, and the user cannot tell that the folder is missing / the target is a folder.
- Proposed fix: catch in `emit`/`atomicio.write_bytes` and re-raise with the requested path ("rvs: cannot write NAME: the folder X does not exist / is a folder / is read-only").
- Test that would catch it: assert the target name (not `.tmp`) appears in stderr for `-o <dir>` and `-o missing/x.csv`.

### CLI-04 Unreadable project folder / config file is reported as "Validation stopped unexpectedly ... A file with content RVS cannot interpret" and writes a crash report
- Where: validate path reached from main.py `_validate/_export/_import`; message text from rvs_core.validate (RVS-VALIDATION-FAILED); hint for unreadable items is "Fix the YAML syntax"
- Severity: medium
- Confidence: verified
- What is wrong: a permission or path-length problem is presented as a content/YAML problem, with a hint to run `git diff`, plus a crash report file in ~/.config/rvs/crash for a plain permission error.
- Evidence: `chmod 000 proj; rvs validate proj` -> `ERROR RVS-VALIDATION-FAILED: Validation stopped unexpectedly (PermissionError). A file with content RVS cannot interpret is the usual cause. A crash report ... saved` rc 3. Same for `chmod 000 proj/config/rules.yaml`, and for a 300-character folder name (`OSError`, ENAMETOOLONG) in validate/export/import, while `cr list`, `baseline list`, `diff` print "File name too long" for the same input (inconsistent). An unreadable item file (chmod 000) gives RVS-ITEM-UNREADABLE with the hint "Fix the YAML syntax of the file named above".
- Why it matters: misleading advice; a crash report is created for a user error.
- Proposed fix: catch `OSError` in the loader and report "Cannot read X: Permission denied" (code RVS-PROJECT-UNREADABLE, exit 3) without a crash report; make the item hint depend on the cause.
- Test that would catch it: validate on a folder with an unreadable config must not mention "crash report".

### CLI-05 `selftest --manifest` with a non-UTF-8 manifest crashes (UnicodeDecodeError)
- Where: src/rvs_core/diagnostics.py:234 (`verify_manifest`, called from main.py:296)
- Severity: low
- Confidence: verified
- What is wrong: `path.read_text(encoding="utf-8")` is not guarded; the command prints "unexpected error (UnicodeDecodeError)" and writes a crash report instead of "FAIL file integrity: MANIFEST.sha256 is unreadable". Exit code 1 either way.
- Evidence: `head -c 100 /dev/urandom > mf/MANIFEST.sha256; rvs selftest --manifest mf` -> `rvs: unexpected error (UnicodeDecodeError). A crash report ...`; with `RVS_DEBUG=1` traceback ends in codecs decode.
- Why it matters: the integrity check meant for broken installations crashes on a damaged manifest; also relative paths such as `/etc/passwd` or `../..` in a manifest are digest-checked outside the folder (benign but unexpected).
- Proposed fix: catch `UnicodeDecodeError/OSError`, return a problem string; refuse manifest entries that are absolute or contain `..`.
- Test that would catch it: manifest of random bytes -> exit 1 and "unreadable" in output, no crash report.

### CLI-06 `init --git` into a folder that already contains `.git` fails after the project files were already written
- Where: src/rvs_cli/main.py:281 / rvs_core/project_templates (create_from_template)
- Severity: medium
- Confidence: verified
- What is wrong: an empty freshly-cloned/`git init`-ed folder is accepted as "empty" (the .git is ignored by the emptiness check) but `--git` then fails with a raw errno message and exit 2; the template files are left behind, so the project exists but the command reported failure, and a rerun answers "already an RVS project; a project cannot be created inside another".
- Evidence: `git init ge; rvs init ge --name G --git` -> `rvs init: [Errno 17] File exists: 'ge/.git'` rc 2; `ls -a ge` -> `.git SUB SYS VER config rvs-project.yaml`.
- Why it matters: the natural workflow (clone empty repo, `rvs init . --name X --git`) fails halfway; non-atomic.
- Proposed fix: with `--git`, reuse an existing repository (no init) or refuse before writing anything; clean up on failure.
- Test that would catch it: init --git in a folder holding an empty git repo returns 0 (or 2 with no files created).

### CLI-07 `import --dry-run` does not check `--cr`; `cr defer` can re-open a closed CR and `cr status ... deferred` bypasses the required reason
- Where: main.py:238-242 (dry run returns before `apply_import`); changecontrol.py `_cr` (status/defer branches)
- Severity: low
- Confidence: verified
- What is wrong: (a) `import --cr CR-0099 --dry-run` prints the plan and exits 0, the real run fails with exit 2 "Change request CR-0099 does not exist" after printing the plan. (b) `rvs cr defer P CR-0003 --reason x` on a CR in status `closed` sets it to `deferred` (reopens a finished CR); defer twice just logs again. (c) `rvs cr status P CR-0004 deferred` (no reason) is accepted although `cr defer` requires `--reason`. (d) `cr new --item NOPE-0001` accepts an item that does not exist. (e) a CR title may contain newlines, which breaks the one-line-per-CR `cr list` output.
- Evidence: see commands above, e.g. `rvs cr status gs/demo CR-0003 closed; rvs cr defer gs/demo CR-0003 --reason x` -> "CR-0003 deferred." and `cr show` shows closed -> deferred; `rvs cr new demo T --item NOPE-0001` -> "CR-0003 created (open)." and `cr show` lists `items: NOPE-0001`.
- Why it matters: change-control state can be changed in ways the guide does not describe; dry run gives a false OK.
- Proposed fix: validate `--cr` (and `--reason` for baselined items) in the dry run; refuse defer for closed/rejected CRs; require a reason for the deferred status; validate item ids; reject newlines in titles.
- Test that would catch it: dry-run with unknown --cr returns 2; defer on a closed CR returns 2.

### CLI-08 Several messages are written for the GUI, or are misleading, on the command line
- Where: main.py:200-205, 217, 227-229; rvs_core messages
- Severity: low
- Confidence: verified
- What is wrong: (1) `import P .` (a folder) -> "the file . does not exist." (2) `--map foo` usage error is reported as "items.reqif could not be read (--map needs NAME=COLUMN...)". (3) A semicolon-delimited CSV (default "CSV" of Excel in many locales) gives `Unknown column(s): id;document;level;...  Use the column names of an exported file` and a cp1252 CSV gives `'utf-8' codec can't decode byte 0xe9 ...`; neither mentions delimiter or "save as CSV UTF-8" (the guide does not mention it either). (4) Import of baselined items without --reason says "Enter why you are importing these changes." (no `--reason`). (5) NUL message ends with ".." ("terminal.."). (6) `validate` on a file or `rvs-project.yaml` says "Project folder X does not exist"; on a non-project folder the hint is "Fix the file named above." (7) An unreadable item says "...then open the project again" (GUI wording). (8) `init` on a regular file prints `[Errno 20] Not a directory: 'afile'`; init on the existing project folder itself says "cannot be created inside another".
- Evidence: commands in table.md (imp-dir, imp-reqif-map-bad, imp-bad-semi.csv, imp-bad-latin.csv, val-file, init-onfile).
- Why it matters: users cannot tell what to do; the Excel CSV case is common.
- Proposed fix: specific messages (is a folder; detect `;`/tab delimiter and cp1252 and say how to save as CSV UTF-8; mention --reason).
- Test that would catch it: import of a `;`-delimited and a latin-1 CSV return 2 with "UTF-8"/"comma" in stderr.

### CLI-09 Reproducibility claim: same SOURCE_DATE_EPOCH does not give identical files across users; invalid SOURCE_DATE_EPOCH is silently ignored
- Where: rvs_core/matrices/provenance.py:_now/now; docs/user-manual/08-command-line.md:41 ("the same commit always gives the same file"), CLAUDE.md ("byte-identical")
- Severity: low
- Confidence: verified
- What is wrong: the provenance block contains `by <login name>`; two accounts (e.g. CI runners) exporting the same commit with the same SOURCE_DATE_EPOCH get different bytes (verified with USER=LOGNAME=alice: `# Generated: 2023-11-14 22:13:20 by alice` vs `by root`; getpass uses the account, env is honoured on Linux). Also `SOURCE_DATE_EPOCH=abc`, empty, `-5`, `1e5`, `99999999999999` are silently ignored (current time used) instead of an error; timestamps are local time without zone when unpinned and UTC when pinned.
- Why it matters: the documented CI recipe does not guarantee reproducibility.
- Proposed fix: reword the docs (same user) or omit/pin the user when SOURCE_DATE_EPOCH is set; warn on an invalid value.
- Test that would catch it: two exports with different LOGNAME and the same SOURCE_DATE_EPOCH compared.

### CLI-10 Ctrl-C during start-up prints a raw traceback; closed stdout crashes `export`
- Where: console script imports `rvs_cli.main` (module level imports ~0.4 s) before `main()` installs its handler; main.py `main()`; output.py:14
- Severity: low
- Confidence: verified
- What is wrong: SIGINT within the first ~0.5 s (import of reportlab/openpyxl via rvs_cli.changecontrol) gives a Python traceback although the docs say the CLI never prints one. With stdout closed (`>&-`), `export --vcm` fails with "unexpected error (AttributeError)" plus a crash report (`sys.stdout.buffer` on None) while `validate` silently returns 0 without output. `--help > /dev/full` returns 0.
- Evidence: `rvs --version & sleep 0.25; kill -INT` (earlier runs with `timeout -s INT 0.3 rvs export ...` printed `Traceback ... KeyboardInterrupt` from `rvs_cli/changecontrol.py` import chain); `rvs export ex_min --vcm >&-` -> `rvs: unexpected error (AttributeError)...`.
- Why it matters: minor; contradicts "never prints a Python traceback".
- Proposed fix: import heavy modules lazily inside the command handlers (also speeds up `--version` from 0.53 s) and wrap the entry point's import; guard `sys.stdout is None` in `emit`.
- Test that would catch it: subprocess with stdout closed.

### CLI-11 `-o` can overwrite project files; `-o -` writes a file called "-"
- Where: output.py `emit` / main.py
- Severity: low
- Confidence: verified
- What is wrong: `rvs export P --vcm -o P/SYS/SYS-0001.yml` replaces an item (project then fails with RVS-ITEM-UNREADABLE), `-o P/rvs-project.yaml` or `guide -o P/config/rules.yaml` destroys configuration; exports into a document folder or the project root leave stray files that `git status` shows (`?? SYS/out.csv`). `-o -` creates a file named `-`.
- Why it matters: data loss in a non-Git project from a typo.
- Proposed fix: refuse targets inside the project that are existing `*.yml/*.yaml` or `rvs-project.yaml`; optionally treat `-` as stdout.
- Test that would catch it: export with -o pointing at an item file returns 2 and leaves it unchanged.

### CLI-12 Minor CLI-surface inconsistencies
- Where: main.py `_main`, parser
- Severity: low
- Confidence: verified
- What is wrong: `rvs` without a command prints help and exits 0 while `rvs cr` / `rvs baseline` exit 2; long options may be abbreviated (`--vc`, `--co`, `--only`), so adding an option later breaks scripts; `diff --document NOPE` exits 0 with "0 changed" whereas `export --document NOPE` exits 2; `--trace SYS:SYS` is accepted and gives a meaningless matrix; option values starting with `-` (`--reason -x`, `-m -m`) fail with "expected one argument" (argparse); `--version` with a subcommand ignores the subcommand; `~` in a quoted path is not expanded (also `init '~/x'` creates a folder named `~`); with `PYTHONUTF8=0 LC_ALL=C` a non-ASCII `--name` is stored in rvs-project.yaml as lone surrogates (`name: "N\uDCC3\uDCA4me"`); the manual's `docs/demo/M6.md` example `rvs init my-project --template satellite --git` lacks the required `--name` (exit 2).
- Why it matters: small, but each is a script-visible difference.
- Proposed fix: `allow_abbrev=False`; required subparsers; unknown `--document` in diff -> exit 2; fix the demo doc.
- Test that would catch it: parser tests for each.

### CLI-13 Tutorial item file creates a Doorstop warning that the tutorial does not mention
- Where: docs/getting-started.md step 4 (ver.csv)
- Severity: low
- Confidence: verified
- What is wrong: `ver.csv` has no `derived` column, so VER-0001 is created with derived=false and the next `rvs validate demo` gives `WARNING DOORSTOP-WARNING VER-0001: no links to parent document: SYS` (2 warnings) and the GUI Problems panel shows it. Everything else in the tutorial (outputs of steps 1-6, `0 errors, 1 warning, 5 info`, baseline line formats) matched exactly.
- Proposed fix: add `derived` = yes (as in the examples) to ver.csv or mention the warning.
- Test that would catch it: a test that executes the tutorial commands and validates at the end.

### CLI-14 Test gaps in the CLI layer (mutation probes that no test catches)
- Where: tests/test_cli*.py, test_audit_core.py; code in src/rvs_cli/main.py, changecontrol.py, output.py
- Severity: medium
- Confidence: verified (mutations applied to a copy of src in scratch; the whole CLI-related test selection incl. test_audit_core, test_audit_gaps, test_review_io, test_reqif, test_diagnostics, test_guide, test_project_templates was run; baseline = all pass)
- What is wrong: these one-line defects SURVIVE (125/177 tests pass):
  - `--fast` ignored (`doorstop=True` instead of `not args.fast`)
  - `--level` and `--status` filters ignored (`tuple(args.level)` -> `()`; only `--method`, `--document`, `--only-gaps` are tested)
  - `import --skip-errors` not passed on (`skip_errors=False`)
  - `validate --format json`: `"exit_code"` always 0
  - `-o` extension -> format mapping disabled (`_default_format` never returns the suffix)
  - `rvs cr status ... --note` dropped (note never asserted); `baseline create --defer` reason parsing replaced by a constant
  - `baseline create -m ""` check removed; `cr`/`baseline`/`diff` on a non-project folder returning 2 instead of 3; `ConfigError` -> 3 mapping in changecontrol.run changed to 2
  - `diff --document` filter removed; `diff --format docx|pdf` without `-o` check removed
  - `emit` stdout flush removed; `stream.reconfigure(utf-8)` removed (no test runs the CLI with a non-UTF-8 stdout); BrokenPipe devnull replacement removed (no `| head` test); `ProjectError` -> exit 3 in `_unexpected`
  (Mutations that were caught: binary-needs-output, dry-run exit code, import exit with skipped rows, --strict, init nested check, document check, trace direction, --only-gaps, --method, --document, --reason/--user/--cr, --map, selftest --manifest, guide -o, baseline verify exit, cr --user/defer reason/new items, --init-git, list json, export baseline label, unloadable-project exit 3 for export and import, init --git/--template, Ctrl-C 130, OSError exit 2.)
  Also: no test exercises `init` output text, `selftest` failure path beyond exit code, SIGINT, closed stdout, or `export` of all selector x format combinations through the CLI parser; test_offline only imports the `rvs_cli` package (an empty __init__), so it never proves that the CLI process itself stays offline (I checked: no network module besides the standard-library `email`/`urllib.parse`/`selectors`/`subprocess` imports is loaded and no socket is opened by any command).
- Why it matters: the documented flags `--fast`, `--level`, `--status`, `--skip-errors`, the JSON `exit_code` that CI relies on, and the diff filters can break unnoticed.
- Proposed fix: add tests asserting each of the above (e.g. `--level` filters rows; JSON exit_code equals the process code for a project with errors; `--skip-errors` applies valid rows and returns 1; `--fast` omits DOORSTOP-* findings; `diff --document`; subprocess test for `| head -1` and a non-UTF-8 `PYTHONIOENCODING`).
- Test that would catch it: the mutations above are the tests to write.

## Checked and found correct
- Exit codes match the epilog and the guide table for every command probed (0/1/2/3/130); no traceback for any bad-input probe except the start-up Ctrl-C and CLI-04/05 crash-report cases; RVS_DEBUG=1 re-raises.
- `| head -1` on validate, export (items, vcm, spec, reqif), help, selftest: exit 0, nothing on stderr. Non-UTF-8 stdout encodings (ascii, latin-1, cp437, LC_ALL=C): output is always UTF-8 and never crashes.
- All 49 selector x format combinations behave consistently (valid ones succeed, invalid ones exit 2 with a clear "can be written as" message), apart from CLI-01; binary formats to stdout are refused with exit 2; unknown UID/document/baseline give clear exit-2 messages; huge (100 KB) arguments handled.
- Export, validate, diff, baseline list/verify, cr list write nothing outside `.rvs-cache/` in the project (strace); the temp file in /tmp is Doorstop's `tempfile.gettempdir()` probe; the AF_UNIX connect is glibc's nscd lookup; no network socket, no subprocess execution.
- Relative / absolute / trailing-slash / symlink / `..` / other-cwd project paths all work; `python -m rvs_cli`, `packaging/launch_cli.py` and the `rvs` script give the same exit codes.
- Read-only project folder: validate/export/diff/dry-run work; import/cr/baseline/init fail with exit 2 and a message; no partial files left behind (atomic temp files cleaned up) when a write fails or on SIGINT mid-export.
- Import: dry-run writes nothing (item files byte-identical, checked by hash), second import of exported file is a no-op for all three formats, error rows block the import unless --skip-errors, baselined items need a reason (dry-run says so too), corrupt/empty xlsx/reqif/DOCTYPE reqif give exit 2 with a plain message.
- Baseline names (empty, spaces, slashes, `..`, `.lock`, CON, unicode, 300 chars, `working`) refused with exit 2; duplicate name refused; baseline verify detects a tampered manifest (exit 1); --init-git works; deferral needs a reason; `export --baseline` shows old text and names the baseline for all 7 selectors.
- Getting-started tutorial output lines match the real tool (see CLI-13 for the one gap); the command reference options match the parser (all options exist and are documented, including `-d`, `-m`, `--init-git`).
- Mutation probes: 46 one-line defects in main.py/changecontrol.py/output.py were run against the CLI-related tests (a first pass had a harness flaw - a missing examples folder in the scratch copy made one unrelated test fail and counted as "caught" - so the doubtful ones were re-run; results in CLI-14: about 24 are caught, about 17 survive).

## Questions about intended behaviour
- `rvs export --baseline B` on a baseline whose manifest was tampered (`baseline verify` fails) exports silently with exit 0; should export warn/refuse?
- `-o -`: should it mean standard output?
- Should a link from an item of a parent document to an item of a child document, or a real item-level cycle (SYS-0002 -> EPS-0001 -> SYS-0002), be reported by `validate`? Today only RVS-LINK-SUSPECT is shown, no cycle/direction finding.
- `import` of the same id-less CSV rows creates duplicates every run (not idempotent) - intended?
- Should `rvs` with no command exit 2?


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
