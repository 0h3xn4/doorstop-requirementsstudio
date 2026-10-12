# Pre-release audit: Packaging, dependencies, installers, CI, licences

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

## Coverage
Files read in full: rvs/pyproject.toml, MANIFEST.in, LICENSE, CHANGELOG.md, .gitignore, .gitattributes, packaging/* (install-linux.sh, uninstall-linux.sh, install-windows.ps1, uninstall-windows.ps1, rvs.spec, launch.py, launch_cli.py, keep), scripts/* (all 14 files), docs/RELEASE.md, docs/developer/* (README.md, refresh_upstream_readme.py, mlc-offline.json), .github/workflows/* (all 5) and dependabot.yml, tests/test_packaging.py (28 tests), test_packaging_metadata.py, test_repo_layout.py, docs/AUDIT.md, DEVIATIONS.md, DECISIONS.md (skimmed), guide chapter 1 install section. dist/: tarball, .sha256, licences, SBOM, listing of the bundle.

Probes run (scratch dir only, repo untouched):
- `python -m build` from a COPY of rvs/ -> wheel + sdist; listed wheel and sdist contents.
- Fresh venvs for Python 3.11, 3.12, 3.13: `pip install` wheel; 3.13 and 3.11 also the sdist. `pip check`, `rvs --version`, `rvs selftest` (all checks passed everywhere), from a cwd outside the repo. Wheel vs sdist-built install: identical file hashes for rvs_*.
- `rvs init/validate/export` (vcm xlsx, spec html/docx/pdf) on a new project with the wheel install; `rvs guide`.
- `rvs-studio` offscreen: starts, and exits with 0 when the event loop is quit (QTimer); `rvs-studio --version` and `--help` start the GUI instead.
- Imports of all modules + GUI window with `sys.modules` scan: no ssl/http/urllib3/requests/QtNetwork; bottle/plantuml_markdown are the inert placeholders; `_socket`, `select`, `urllib.parse` present (no `socket`, no `ssl`).
- AST scan of all imports in src/ vs declared dependencies: every import is declared (PySide6, docx, doorstop, dulwich, fastjsonschema, markdown, openpyxl, reportlab, yaml); no undeclared; no unused declared dependency. lxml, Pillow, et_xmlfile, typing_extensions, six, verchew, python-frontmatter, python-markdown-math, requests, urllib3, certifi, idna, charset-normalizer, bottle, plantuml-markdown arrive transitively and float.
- pip-audit on the installed environment (network): no known vulnerabilities. `pip list --outdated`: nothing relevant (note PyPI project `rvs` 2.1.1 belongs to someone else).
- `pip install --dry-run "rvs[dev]"` on 3.11 and 3.13: resolves (pyinstaller 6.22.3, cyclonedx-bom 7.5.0, ...).
- `scripts/build_wheelhouse.sh` run in a copy; offline `pip install --no-index --find-links` into 3.13 works, into 3.11 fails.
- `scripts/sbom.sh` run in a copy twice: byte-identical outputs; licence txt equals the THIRD-PARTY-LICENSES.txt inside the dist tarball; SBOM component set equals the bundle SBOM.
- Extracted dist tarball (own dir): file modes, symlinks, no traversal, MANIFEST count, GLIBC-MIN 2.38, bundle contents listing (libs, plugins, lib-dynload), installed it with dash into a temp HOME, ran its selftest, started rvs-studio offscreen from the launcher link, uninstalled.
- Installer scenarios with dash and a fake release: first install, second install, uninstall, uninstall twice, spaces in release/HOME/prefix, foreign launcher file, non-empty foreign prefix, HOME/`/`/empty prefix, symlink prefix, tampered file, extra file, missing manifest, garbage manifest, unreadable-looking symlink to /etc/passwd, missing sha256sum, HOME unset, read-only prefix parent and read-only ~/.local/bin (as user nobody), TERM/HUP during copy and during the swap with an existing install.
- Mutation probes (copies): 7 mutations of install/uninstall script (all caught by test_packaging); dropping package-data entries (fonts, schemas, images) -> NOT caught; `__version__` changed to 9.9.9 -> NOT caught; removing ruff/mypy/pytest steps from rvs-ci.yml -> NOT caught.
- `ruff check` and `ruff format --check` on the whole rvs/ tree: clean. `sh -n`/`dash -n` on all shell scripts: ok. Scripts' `--help` behaviour checked in copies.
- Hygiene: git ls-files --eol, modes, case collisions, non-ASCII names, big files, secrets regex, binary types, TODO/FIXME/print()/commented-out code/hard-coded paths grep over src, scripts, packaging.
- Windows PowerShell scripts: NOT run (no pwsh here, never run on Windows); static review only.
Tests run: tests/test_packaging.py, test_packaging_metadata.py, test_repo_layout.py (33 passed); from the unpacked sdist: test_guide, test_examples, test_layering, test_offline, test_packaging_metadata, test_cli, test_repo_layout (30 passed, 1 skipped).

## Findings

### RELEASE-01 Bundle ships GNU Readline (GPL-3.0) inside a proprietary bundle
- Where: packaging/rvs.spec (excludes list), dist bundle `_internal/libreadline.so.8`, `_internal/python3.13/lib-dynload/readline.cpython-313-x86_64-linux-gnu.so`
- Severity: medium
- Confidence: verified (file listing of the built bundle); the cause (no `readline` exclude) is reading-only
- What is wrong: the PyInstaller bundle contains the Python `readline` module and Ubuntu's `libreadline.so.8` (GPL-3.0-or-later). RVS never imports `readline` (grep src: nothing). It is not in THIRD-PARTY-LICENSES.txt or the SBOM. Shipping a GPL-3 library linked by a bundled module next to software licensed "proprietary, no redistribution" is a licence conflict, and it is unneeded weight.
- Evidence: `find tarx/rvs-studio-0.1.0/rvs-studio/_internal -name '*readline*'` -> `./libreadline.so.8` and `./python3.13/lib-dynload/readline.cpython-313-x86_64-linux-gnu.so`; `ldd` of that module lists libreadline.
- Why it matters: licence compliance of the release (D10 says dependencies were deliberately limited to permissive and LGPL).
- Proposed fix: add `"readline"` to `excludes` in rvs.spec (and `_is_unused` filter for `libreadline`); add a build step that fails if a GPL-only library name appears in the bundle.
- Test that would catch it: a release-build check listing bundle libraries against an allow-list (or a spec test asserting "readline" in excludes).

### RELEASE-02 Licence report and SBOM omit what the bundle really contains (LGPL system libraries, Python, PyInstaller)
- Where: scripts/make_licences.py, scripts/build_release.sh (report taken from the build venv), packaging/rvs.spec
- Severity: medium
- Confidence: verified (bundle listing vs THIRD-PARTY-LICENSES.txt)
- What is wrong: THIRD-PARTY-LICENSES.txt and sbom.cdx.json describe the pip packages of the throwaway venv only. The bundle also contains copies of system libraries picked up from the build machine because Qt's `libqgtk3.so` platform theme links GTK3: libgtk-3, libgdk-3, libglib/gio/gobject, libcairo, libpango, libgdk_pixbuf, libatk, libgcrypt, libgpg-error, libsystemd, libmount/libblkid, libkrb5/libgssapi, libicu*, libharfbuzz, libfreetype, libcrypto (OpenSSL) ... (mostly LGPL-2.1+, ICU, Apache-2.0), the CPython runtime (PSF) and the PyInstaller bootloader (GPL-2 with exception). None has a licence text, notice or source offer in the bundle; the SBOM lists none of them. The report also lists packages that are only in the PYZ (typing_extensions, six, verchew ...) correctly, but says nothing of the above.
- Evidence: `ls _internal | grep -E 'gtk|glib|cairo|pango|gcrypt|icu'` in the extracted dist tarball; `grep -c 'gtk' THIRD-PARTY-LICENSES.txt` has no entry; `_internal/PySide6/Qt/plugins/platformthemes/libqgtk3.so` present and `ldd` shows libgtk-3.
- Why it matters: LGPL and notice obligations when the archive is given to others; also GTK3/libgio inside an "offline only" product (loaded only when the GTK theme plugin is selected, but shipped).
- Proposed fix: prune `platformthemes/libqgtk3.so` (and the GTK chain) in rvs.spec or add the system libraries to the report (dpkg-query licence files at build time); add PSF and PyInstaller licence entries.
- Test that would catch it: release check comparing bundle `.so` names against report entries.

### RELEASE-03 The "relinking" statement does not hold for Doorstop (LGPL-3.0)
- Where: scripts/make_licences.py HEADER, docs/RELEASE.md "Licences to review"
- Severity: medium (legal; needs a decision)
- Confidence: likely
- What is wrong: the statement says users can replace the LGPL parts because they are "separate shared files". True for Qt/PySide6, not for Doorstop: the bundle has only `_internal/doorstop-3.2.dist-info`; the Doorstop modules are compiled into the PYZ archive inside the `rvs`/`rvs-studio` executables (no `doorstop/` folder anywhere in the bundle). A user cannot swap in a modified Doorstop without rebuilding the bundle. LGPL-3 section 4 needs a way to run a modified library with the application (shared-library mechanism or relinkable application code).
- Evidence: `find tarx/.../rvs-studio -path '*doorstop*'` lists only dist-info files; `grep -a -c doorstop/core/item rvs` -> 0 (modules sit compressed in the archive).
- Proposed fix: ship Doorstop as loose files (`noarchive` for it, or `--collect-all` into `_internal`), or ship the source and build instructions and say so in the report; get legal sign-off.
- Test that would catch it: release check that `_internal/doorstop/` exists.

### RELEASE-04 install.sh silently overwrites a foreign `~/.local/bin/rvs`; uninstall then deletes it
- Where: packaging/install-linux.sh:105-106 (`ln -sfn`), uninstall-linux.sh:205-209
- Severity: medium
- Confidence: verified
- What is wrong: the launchers are made with `ln -sfn`, which replaces any existing file. A user who ran `pip install --user ./rvs` (the documented route in the README) has a regular script `~/.local/bin/rvs`; the installer replaces it without a word, and uninstall removes the link, leaving no `rvs` at all. The install script otherwise promises never to touch what it did not create.
- Evidence: HOME with `~/.local/bin/rvs` = script printing "mine"; `dash install.sh --no-selftest` rc=0; `ls -l` shows `rvs -> .../opt/rvs-studio/rvs`; after `uninstall.sh` the bin folder is empty (`total 0`).
- Why it matters: silent loss of a user's own file/command.
- Proposed fix: if the target exists and is not a symlink into the prefix, keep it, print a warning (or refuse), and do not create the link.
- Test that would catch it: install with a pre-existing regular `~/.local/bin/rvs`; assert content unchanged.

### RELEASE-05 `rvs-studio --version` and `--help` open the GUI (and hang headless)
- Where: src/rvs_gui/app.py:1392 (`main`), entry point `rvs-studio`
- Severity: low
- Confidence: verified
- What is wrong: `main()` ignores its arguments; `rvs-studio --version` / `--help` start a full window and never return (the first one had to be killed). Documented tools (`rvs-studio` in CI, install smoke tests, scripts) cannot ask the version. The release build's only check of the GUI is "still running after 10 s".
- Evidence: `QT_QPA_PLATFORM=offscreen rvs-studio --version` -> only Qt notices, ran until killed; `--help` same.
- Proposed fix: parse `--version/--help` before creating QApplication (argparse, then pass `[argv[0]]` to Qt).
- Test that would catch it: subprocess `rvs-studio --version` with timeout 10; assert output and exit 0.

### RELEASE-06 No test or CI step looks at the built wheel: package data can be dropped unnoticed
- Where: pyproject.toml `[tool.setuptools.package-data]`; tests/test_packaging.py::test_sdist_contains_what_is_needed_to_run_the_tests; .github/workflows/rvs-ci.yml (`pip install -e .`)
- Severity: medium (test gap on an important behaviour)
- Confidence: verified (mutation)
- What is wrong: all tests and CI use an editable install, so a missing package-data entry is invisible. The one sdist test asserts only `guide.html`. The PyInstaller `package` job would catch missing schemas/fonts through `rvs selftest`, but not guide images.
- Evidence: in a copy, `rvs_core = ["config/defaults/*.yaml", "guide/*.html"]` and `rvs_gui = []` (drops schemas, export fonts, guide images, GUI fonts) -> `pytest tests/test_packaging.py tests/test_packaging_metadata.py -k "not install and not uninstall"` -> `17 passed`. (Dropping `guide/*.html` too fails the sdist test, the only catch.) A real wheel built from the unmutated tree does contain all of them (verified by listing).
- Proposed fix: a test that builds the wheel (`setuptools.build_meta.build_wheel` in a copy) and checks for config defaults, schemas, fonts, guide.html, guide images, OFL files; CI step `pip install dist/*.whl` in a clean venv + `rvs selftest` from another cwd.
- Test that would catch it: the above.

### RELEASE-07 Wheelhouse works only for the Python and platform that built it; docs say otherwise (and RHEL 8 is impossible)
- Where: scripts/build_wheelhouse.sh, docs/RELEASE.md, docs/guide/01-getting-started.md ("RHEL 8 or 9, Ubuntu 22.04 ... Python 3.11, 3.12 or 3.13"), docs/troubleshooting.md
- Severity: medium (documented install route for older systems fails)
- Confidence: verified
- What is wrong: `pip download` fetches wheels for the running interpreter only. A wheelhouse built with 3.13 contains cp313 wheels (lxml, Pillow, PyYAML, dulwich, charset_normalizer). PySide6-Essentials 6.12.0 and shiboken6 are `manylinux_2_34` wheels, so any system with glibc older than 2.34 (RHEL 8: 2.28) cannot install them at all; the guide names RHEL 8 as a target of the wheelhouse route.
- Evidence: wheelhouse listing: `pyside6_essentials-6.12.0-cp310-abi3-manylinux_2_34_x86_64.whl`, `pyyaml-6.0.3-cp313-cp313-...`. Offline install into a 3.11 venv: `ERROR: Could not find a version that satisfies the requirement PyYAML==6.0.3 (from versions: none)`. Into a 3.13 venv: works.
- Proposed fix: script option to run per target (`--python-version`, `--platform`, `--only-binary=:all:`) or one wheelhouse per Python; remove RHEL 8 from the docs, state glibc 2.34 for the wheelhouse route.
- Test that would catch it: docs/script test asserting the wheelhouse file tags cover each supported Python.

### RELEASE-08 uninstall.sh / uninstall.ps1 are not installed
- Where: packaging/install-linux.sh, scripts/build_release.sh (stage), docs/guide/01-getting-started.md
- Severity: low
- Confidence: verified
- What is wrong: after `install.sh` the prefix contains no uninstaller (listing of the installed prefix: GLIBC-MIN, LICENSE, MANIFEST.sha256, THIRD-PARTY-LICENSES.txt, _internal, rvs, rvs-studio, sbom.cdx.json). The guide says to run `./uninstall.sh` from the unpacked folder; if that folder is deleted (usual), nothing documents manual removal (prefix, two links, the .desktop file).
- Proposed fix: copy uninstall.sh into the app folder (and list it in the manifest) or document the manual removal.

### RELEASE-09 The earlier build in `rvs/dist/` is stale and its stand-alone licence/SBOM files differ from what the scripts now produce
- Where: rvs/dist/ (untracked, gitignored)
- Severity: low (must not be shipped as it is)
- Confidence: verified
- What is wrong: (a) `dist/rvs-studio-0.1.0` bundle (10 Oct 10:43) predates HEAD: `user-guide.html` differs from `src/rvs_core/guide/guide.html`; the bundled `rvs diff --help` lacks the new help texts; (b) `dist/rvs-licenses.txt/json` and `dist/rvs-sbom.cdx.json` (9 Oct 22:25) are from an older generator: JSON keys `License/Name/Version` instead of `licence/name/version/url`, SBOM without `rvs:in-bundle` properties, 27 components vs 26 in the bundle's own SBOM. `sh scripts/sbom.sh` today produces a different, consistent set (licence text identical to the bundle's THIRD-PARTY-LICENSES.txt, 165548 bytes). The tarball and its `.sha256` do match (433e3805...).
- Evidence: `cmp dist/rvs-studio-0.1.0/user-guide.html src/rvs_core/guide/guide.html` differ; `head dist/rvs-licenses.json`.
- Proposed fix: rebuild the release from the final commit; delete the old stand-alone files.

### RELEASE-10 sdist/wheel details: CHANGELOG.md and CONTRIBUTING.md missing from the sdist, CLAUDE.md included, LICENSE points at files that are not there
- Where: MANIFEST.in; LICENSE
- Severity: low
- Confidence: verified
- What is wrong: sdist root holds `.gitattributes .gitignore CLAUDE.md LICENSE MANIFEST.in PKG-INFO README.md pyproject.toml setup.cfg` but not `CHANGELOG.md`/`CONTRIBUTING.md`, while `docs/` (grafted) links to `../CHANGELOG.md` and `../../CONTRIBUTING.md`. The AI-agent instruction file CLAUDE.md is shipped. LICENSE refers to `THIRD-PARTY-LICENSES.txt` ("every release bundle contains") and to `docs/DECISIONS.md`: neither is in the wheel.
- Evidence: `tar tzf out/rvs-0.1.0.tar.gz | sed -n 's|^rvs-0.1.0/||p' | grep -v '^\(examples\|src\|tests\|docs\)/'`.
- Proposed fix: add the two files to MANIFEST.in; decide on CLAUDE.md; mention in LICENSE that the wheel/sdist carry no third-party text, or add it.

### RELEASE-11 Dev scripts without argument handling do destructive work on `--help`
- Where: scripts/gen_examples.py, gen_goldens.py, build_screenshots.py, gen_stress.py, sbom_post.py
- Severity: low
- Confidence: verified (copy)
- What is wrong: `gen_examples.py --help` deletes and rewrites `examples/minimal10` and `satellite300` (output `wrote .../examples/minimal10`); `gen_stress.py --help` writes a project into a folder named `--help`; `sbom_post.py --help` raises FileNotFoundError traceback; `gen_goldens.py`/`build_screenshots.py` likewise regenerate. (The regenerated examples were byte-identical to the committed ones: good determinism evidence.)
- Proposed fix: argparse (or at least refuse extra arguments) in these scripts.

### RELEASE-12 `sbom.sh` writes a 1970 timestamp outside a Git checkout
- Where: scripts/sbom.sh:16
- Severity: low
- Confidence: verified
- What is wrong: `SOURCE_DATE_EPOCH=${...:-$(git log ... || echo 0)}` silently yields 0 when there is no history (unpacked sdist); build_release.sh refuses in that case, sbom.sh does not.
- Evidence: SBOM from a copy without .git: `metadata.timestamp = 1970-01-01T00:00:00+00:00`.
- Proposed fix: fail like build_release.sh.

### RELEASE-13 `trap ... EXIT INT TERM` in sbom.sh and build_wheelhouse.sh does not stop the script on Ctrl-C
- Where: scripts/sbom.sh:12, scripts/build_wheelhouse.sh:29
- Severity: low
- Confidence: verified (shell semantics)
- What is wrong: the handler only runs `rm -rf "$work"`; in POSIX sh the script then continues after INT/TERM (dash: `trap "echo handler-ran" INT; kill -INT $$; echo continues` prints both lines). The following commands run against a deleted work folder and fail with confusing errors, and `dist/` may be left half written (sbom.sh removed the old files before generating).
- Proposed fix: `trap 'rm -rf "$work"' EXIT; trap 'exit 130' INT TERM` (as install-linux.sh does with `cleanup; exit 1`).

### RELEASE-14 build_release.sh: misleading and inconsistent behaviour
- Where: scripts/build_release.sh:59, :64-66; CLAUDE.md claim
- Severity: low
- Confidence: verified
- What is wrong: (a) with no `python` on PATH (only `python3`) the message is "cyclonedx-bom is missing; install the dev extra" (verified in an env with a PATH without python); `_common.sh` also hard-codes `python -m venv`. (b) `rm -rf build` removes any `build/` of the project and the script leaves `build/release` (venv, PyInstaller work dir, a full second copy of the bundle) in the working tree, contradicting CLAUDE.md ("All release scripts work in temporary folders and leave no `build/`"). (c) the archive is made from the working tree (not from `git archive`), so a dirty tree is bundled while `SOURCE_DATE_EPOCH` claims the last commit. (d) not run by me: PyInstaller not to be rebuilt.
- Proposed fix: check `command -v python`; clean `build/release` on success; refuse a dirty tree or build from `git archive`.

### RELEASE-15 Windows installer/uninstaller: robustness gaps (static review, never run)
- Where: packaging/install-windows.ps1:55-67, uninstall-windows.ps1:90-95
- Severity: medium (reading-only; scripts were never run on Windows)
- Confidence: reading-only, moderate
- What is wrong:
  1. Ctrl-C during the copy/swap: Windows PowerShell does not run `catch` for a stopped pipeline (only `finally`), so the `.new` staging folder stays behind, or, in the swap window, the previous installation stays in `<prefix>.<token>.old` with no installation in place. The Linux script handles INT/TERM.
  2. Uninstall while the program is running: `Remove-Item -Recurse -Force` deletes in enumeration order and fails on the locked exe, possibly after `.install-prefix` is gone; the folder is then neither reinstallable (install refuses "not empty and not installed by this script") nor removable by uninstall.ps1 ("not an installation made by install.ps1"). The marker should be deleted last, and running processes checked.
  3. uninstall.ps1 is not idempotent (second run throws) unlike uninstall.sh; it deletes the Start-menu shortcut by name even when it belongs to another prefix; it does not check that `$Prefix` is a folder or a junction (PS 5.1 `Remove-Item -Recurse` on junctions has followed them).
  4. The `.ps1` files are copied into the Linux tarball, where they can only fail ("rvs-studio.exe not found"); there is no Windows bundle at all.
  5. Group-policy execution policy (AllSigned) overrides `-ExecutionPolicy Bypass`; scripts are unsigned; documented nowhere.
  6. The only test is a string grep (`"NewGuid" in text`); changing a `-ne` to `-eq` in the hash check would pass all tests.
  Checked and looks right: -LiteralPath everywhere (brackets, spaces, non-ASCII), ASCII-only source, manifest compared case-insensitively with extra-file check, fresh GUID staging names, prefix guards (`C:\`, profile), balanced braces/quotes.
- Proposed fix: try/finally cleanup, delete marker last, make uninstall idempotent, run on a real Windows machine before any Windows release.

### RELEASE-16 CI: gaps in what the package job verifies and in hygiene
- Where: .github/workflows/rvs-ci.yml, test-*.yml, _common.yml, dependabot.yml
- Severity: low
- Confidence: verified by reading (+ mutation for the test of the workflow)
- What is wrong: no `permissions:` (token gets repository default), actions pinned by tag (checkout@v4, setup-python@v5, upload-artifact@v4), no `timeout-minutes`, no pip cache, no concurrency. The `package` job builds the bundle but never runs `install.sh` on the produced tarball, never checks the `.sha256`, never builds or installs the wheel/sdist, never runs pip-audit, and only on Linux. The test that guards the workflow (`test_ci_workflow_runs_three_pythons...`) checks matrix, QT var and the GUI step only: deleting the ruff, mypy and pytest steps passed it (verified). The path filter `rvs/**` means a change to the root README, root docs or `docs/upstream/` runs nothing from RVS (`refresh_upstream_readme.py --check` exists but is never run; it passes today). The upstream workflows (test-linux/osx/windows, `_common.yml`, matrix includes 3.14, codecov condition tests 3.9 which is not in the matrix) run on EVERY push without path filter and need `CODECOV_TOKEN`; dependabot watches only the root pip manifest, not `rvs/pyproject.toml`.
- Proposed fix: add `permissions: contents: read`, timeouts, SHA pins, a job that installs the wheel in a clean venv and the tarball into a temp HOME, and make the workflow test assert the lint/test steps.

### RELEASE-17 Version string is duplicated and unchecked; CHANGELOG ordering
- Where: pyproject.toml:7, src/rvs_core/__init__.py:3, CHANGELOG.md
- Severity: low
- Confidence: verified
- What is wrong: the version is typed twice; no test compares them (setting `__version__ = "9.9.9"` in a copy: test_cli, test_packaging_metadata still pass). All current places agree (0.1.0 in pyproject, `__version__`, README, getting-started, `rvs --version`, wheel/sdist names, bundle dir). CHANGELOG has `[Unreleased]` (CLI help text, docs) above `[0.1.0] - 2026-10-10`, so the 0.1.0 tag would contain changes the changelog lists as unreleased.
- Proposed fix: `dynamic = ["version"]` from `rvs_core.__version__`, or a one-line test; move the Unreleased items under 0.1.0 before tagging.

### RELEASE-18 No application icon or application name
- Where: src/rvs_gui (no `setWindowIcon`, `setApplicationName`, `setDesktopFileName`), packaging/install-*.{sh,ps1}
- Severity: low
- Confidence: verified (grep; the bundle has no icon; the .desktop file written has no `Icon=`)
- What is wrong: the menu entry, task bar and window show a generic icon; Wayland app-id is not set. Cosmetic for a release.

### RELEASE-19 install.sh: partial result when the launcher step fails; Exec escaping incomplete
- Where: packaging/install-linux.sh:102-118
- Severity: low
- Confidence: verified (ro case); reading-only (escaping)
- What is wrong: with a read-only `~/.local/bin` the program is installed, then `ln` fails with a raw message and `exit 1` ("ln: failed to create symbolic link ... Permission denied") and no hint that the program is installed but unlinked. The `Exec=` line escapes `%`, `\` and `"` but not `$` and backtick, which the Desktop Entry specification also requires inside quotes; a prefix containing `$` gives a broken menu entry.
- Proposed fix: check the link step and print where the program is; escape `$` and backtick.

### RELEASE-20 Smaller repository and dependency hygiene items
- Where: rvs/.gitignore, docs/DEVIATIONS.md V27, PyPI name
- Severity: low
- Confidence: verified
- What is wrong: (a) .gitignore has no `.DS_Store`, `*.swp`, `*.log`, `node_modules/` (the developer guide recommends `npx markdown-link-check`) at rvs level (root .gitignore covers some). (b) V27 names `defusedxml` as a floating transitive dependency; it is not installed by `pip install rvs` (it only comes with the dev extra via cyclonedx-bom). (c) Runtime transitive packages float (installed today: lxml 6.1.3, Pillow 12.3.0, typing_extensions 4.16.0, six, verchew...), so two installs a month apart differ; known (V27). (d) The PyPI project name `rvs` is owned by someone else (`pip list --outdated` reported rvs latest 2.1.1): every documented command uses `pip install ./rvs` or `--no-index --find-links`, which is safe, but `pip install rvs` without `--no-index` would install a stranger's package. (e) OFL working-tree files (OFL.txt etc.) are CRLF on disk, LF in the index. (f) Seven working-tree `__pycache__` folders exist under src (ignored, untracked): fine.

## Checked and found correct
- Wheel and sdist build from a copy; no `build/` or egg-info in the repo; the wheel contains defaults (9 yaml), schemas (9 json), export fonts (ttf+woff+OFL), GUI fonts (+2 OFL files), guide.html, 7 guide images, `licenses/LICENSE`, entry points `rvs` and `rvs-studio` (gui-script). sdist holds tests, docs, examples, packaging, scripts as MANIFEST.in intends; no caches or .rvs-cache; tests/guide/examples/layering/offline pass from the unpacked sdist.
- Clean install from wheel on 3.11, 3.12, 3.13 and from sdist on 3.13 and 3.11: `pip check` clean, `rvs --version` = `rvs 0.1.0 (doorstop 3.2)`, `rvs selftest` all ok from a foreign cwd; installed rvs_* files identical between wheel and sdist routes.
- `rvs init --git`, validate, export (xlsx/html/docx/pdf), guide work after a wheel install; rvs-studio starts offscreen and exits 0 on quit.
- Import audit: no undeclared and no unused direct dependency; PySide6 only QtCore/QtGui/QtWidgets; no socket/ssl/http/urllib3/requests/QtNetwork module is loaded after importing everything and opening the main window; spec excludes match.
- pip-audit (network): no known vulnerabilities in the installed set; every pin exists and installs; dev extra resolves on 3.11 and 3.13.
- Version 0.1.0 consistent across pyproject, `__version__`, README, getting-started, selftest/CLI, artefact names, CHANGELOG.
- sbom.sh / licences: deterministic (two runs identical); SBOM component set equals the one inside the dist bundle; the licence text equals the bundle's THIRD-PARTY-LICENSES.txt; excluded network packages are marked `rvs:in-bundle=false`; GLIBC-MIN present.
- dist tarball: sha256 matches the .sha256 file; no absolute/.. names; root-owned, sorted; 24 relative symlinks; installs with dash into a temp HOME, its selftest `--manifest` passes, launcher runs, uninstall leaves the project folder.
- install-linux.sh/uninstall-linux.sh (dash): spaces in every path; second install replaces; uninstall twice (second exits 0 "Nothing to remove"); refuses non-empty foreign prefix, HOME, `/`, empty prefix, symlink prefix; refuses tampered file, extra file, missing/garbage manifest, symlink-to-/etc/passwd extra entry; missing sha256sum needs `--skip-verify`; TERM/HUP during the copy and during the swap leave the previous install intact and no leftovers; read-only parent gives a clear message and changes nothing; uninstall never touches a foreign prefix or foreign links. Seven mutations of these scripts were all caught by tests/test_packaging.py.
- Repo hygiene: no secrets (regex scan), no build output, `__pycache__`, editor files or large binaries tracked (largest 204 KB), no case collisions, no non-ASCII names, executable bits on the six shell scripts, `.gitattributes` effective (ps1 crlf, sh/py lf, goldens/examples/guide.html byte-exact). ruff check and ruff format are clean for the whole tree.
- src/scripts/packaging: no TODO/FIXME/XXX/HACK (apart from intended TODO-STANDARD placeholders), no debug prints (print() only in CLI/crash output), no commented-out code, no hard-coded user names or paths.

## Questions about intended behaviour
- Is the release archive ever given to people outside the owning organisation? RELEASE-01/02/03 matter much more if yes (LICENSE says internal only). A decision is needed on whether GTK3 platform-theme libraries and GNU Readline are wanted in the bundle at all.
- IBM Plex is under the OFL with Reserved Font Name "Plex". The shipped TTF conversions and subset WOFFs are modified versions that keep the family name "IBM Plex ..." (subsets also lack the licence name record). Is that accepted?
- The LICENSE says the software may not be copied/distributed and has no carve-out for the LGPL parts (LGPL-3 section 4 wants terms that allow modification for own use and reverse engineering for debugging). Is legal review planned?
- Should the Linux archive contain `install.ps1`/`uninstall.ps1` when no Windows bundle exists?
- Is a Windows release in scope for 0.1.0? If so, the PowerShell scripts and a Windows PyInstaller build must be run once on Windows.


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
