# Release checklist

Run on the release machine (Linux build shown; Windows has never been tested: DEVIATIONS V22, V25). The Linux bundle must be built on the oldest distribution you want it to run on, because it needs the glibc of its build machine (V28); the CI package job uses Ubuntu 24.04 (glibc 2.39, the bundle then needs 2.38 or newer).

1. `ruff check . && ruff format --check . && mypy`
2. `QT_QPA_PLATFORM=offscreen pytest` on Python 3.11, 3.12 and 3.13 (CI runs all three on Linux and Windows; all three were green for 0.1.0)
3. Optional: `RVS_STRESS_DIR=<dir> pytest -m perf -s` (5,000 items on a 4-core machine: cold open 3-5 s, warm under 1 s, one edit 0.6-0.7 s)
4. `python scripts/build_guide.py` if `docs/guide` changed (a test fails when the bundled guide is stale; the release build refuses a stale guide)
5. `sh scripts/build_release.sh` (needs the `dev` extra for `cyclonedx-bom`, and the package index or `RVS_PIP_ARGS="--no-index --find-links wheelhouse"`). It:
   - creates a throwaway clean venv with only the runtime dependencies, installed from a clean copy of the project (no `build/` or `*.egg-info` in the working tree);
   - writes `THIRD-PARTY-LICENSES.txt` (every package's own licence files, the LGPL-3.0 note and the relinking statement) and a reproducible CycloneDX `sbom.cdx.json` from that venv;
   - installs the pinned PyInstaller (`RVS_PYINSTALLER`, default `pyinstaller==6.22.3`) and builds `rvs-studio` and `rvs` with `packaging/rvs.spec` (unused Qt parts and stdlib network servers pruned);
   - writes `GLIBC-MIN` (the glibc the bundle needs, from its binaries), runs the optional signing hook (`RVS_SIGN_CMD`, passed the file as its last argument), then writes `MANIFEST.sha256`, which covers the licences, the SBOM and `GLIBC-MIN`;
   - runs `rvs selftest --manifest` and starts the GUI offscreen for ten seconds;
   - writes `dist/rvs-studio-<version>.tar.gz` and `.sha256`, plus `dist/rvs-studio/`.
   It exports `PYTHONHASHSEED=0` and `SOURCE_DATE_EPOCH` (default: the time of the last commit); the archive is sorted by name, owned by root and compressed with `gzip -n`. Built twice from one checkout on one machine, the archive is byte-identical. Not pinned: the transitive dependencies (V27), the system libraries PyInstaller copies from the build machine, and the absolute path of the checkout (it appears in some compiled files), so identical bytes across machines are not promised. The 0.1.0 bundle is about 180 MB as a folder and 77 MB as an archive.
6. `sh scripts/sbom.sh`: `dist/rvs-sbom.cdx.json`, `dist/rvs-licenses.txt|json` for the runtime install, without the packages the bundle excludes (the SBOM marks those with `rvs:in-bundle=false`). Also works in a throwaway venv.
7. Smoke test the archive in a clean HOME: `./install.sh` (verifies the manifest, runs the selftest, warns about missing system libraries), `rvs init`, `rvs validate`, start `rvs-studio`, `./uninstall.sh` (twice: the second says *Nothing to remove*). Done for 0.1.0 on Linux.
8. `pip-audit` needs the vulnerability database (network); run it on a connected build machine, never inside the product.

## Linux system requirements

The bundle contains Python and Qt. The user needs: glibc 2.38 or newer, and the libraries `libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1 libxcb-util1` (Debian/Ubuntu package names; CI installs the same list). `install.sh` checks both and only warns. For older distributions install from the wheelhouse with Python 3.11-3.13: on a connected machine `sh scripts/build_wheelhouse.sh`, copy `wheelhouse/` over, then `pip install --no-index --find-links wheelhouse rvs` (the system libraries are still needed for `rvs-studio`).

## Lock file (requirements-lock-README)

Today only the direct dependencies are pinned and nothing is hash-checked (V27). The plan:

1. On a connected machine run `sh scripts/make_lock.sh`. It uses `uv pip compile --universal --generate-hashes` or `pip-compile --generate-hashes` and writes `requirements-lock.txt`: every runtime package, transitive ones included, each with the hashes the package index reports. Nothing is typed in or copied by hand.
2. Review the diff against the previous lock (new packages, new licences), commit it, and run the SBOM and `pip-audit`.
3. Build with it: `RVS_PIP_ARGS="--require-hashes"` does not fit `pip install .`, so the release script will install `pip install --require-hashes -r requirements-lock.txt` first and then `pip install --no-deps .`. This change to `scripts/_common.sh` is not made yet, because no lock file has been generated and reviewed.
4. PySide6 6.12.0 was pinned two days after publication; let a pin age (a few weeks, with the changelog read) before the first customer release, or move to the previous minor version.

## Signing

Signing is optional: `RVS_SIGN_CMD="signtool sign /fd SHA256 /a"` (Windows) or `RVS_SIGN_CMD="gpg --detach-sign --armor"`. The command line is run by `sh -c` with the file name as its last argument, then the manifest is written, so the signed files are the ones that are hashed. No certificate is configured.

## Independent review (done for 0.1.0)
Five reviewers examined core data integrity, exporters/import, change control/Git, the GUI, and CLI/installer/security, each with reproducers; the findings and what was decided are in DECISIONS D79-D83 and DEVIATIONS V24. A later audit of documentation and packaging produced D84, D85 and V26-V31 (see `AUDIT.md`). Repeat this pass before a major release.

## Licences to review (0.1.0)
- PySide6-Essentials / shiboken6: LGPL-3.0 (used under LGPL; the one-folder bundle keeps the Qt libraries as separate shared files, so users can replace them; the statement is in `THIRD-PARTY-LICENSES.txt`).
- Doorstop 3.2: LGPL-3.0. dulwich: Apache-2.0 (dual-licensed). Everything else is permissive; see `THIRD-PARTY-LICENSES.txt` in the bundle.
- Fonts: IBM Plex (SIL OFL), bundled with its licence.
- RVS itself: proprietary, internal (`LICENSE`, D10).

## Open items before a customer release
- Windows build and scripts untested; no signing certificate configured.
- No hashed lock file (V27).
- `TODO-COMPANY` / `TODO-STANDARD` values in `config/` (priority scale, word lists, change-request statuses, ECSS VCM layout).
