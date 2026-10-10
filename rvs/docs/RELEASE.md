# Release checklist

Run on the release machine (Linux build shown; do the same on Windows, which has never been tested: DEVIATIONS V22).

1. `ruff check . && ruff format --check . && mypy`
2. `QT_QPA_PLATFORM=offscreen pytest` on Python 3.11, 3.12 and 3.13 (all three were green for 0.1.0)
3. Optional: `RVS_STRESS_DIR=<dir> pytest -m perf -s` (5,000 items: cold open 2 s, warm 0.6 s, one edit 0.6-0.7 s)
4. `python scripts/build_guide.py` if `docs/guide` changed (a test fails when the bundled guide is stale)
5. `sh scripts/build_release.sh`: guide, PyInstaller build, optional signing (`RVS_SIGN_CMD`), `MANIFEST.sha256`, `rvs selftest --manifest`, archive `dist/rvs-studio-<version>.tar.gz` + `.sha256`
6. `sh scripts/sbom.sh`: `dist/rvs-sbom.cdx.json`, `dist/rvs-licenses.json|txt` (runtime install only, 26 packages for 0.1.0)
7. Smoke test the archive in a clean HOME: `./install.sh` (verifies the manifest, runs the selftest), `rvs init`, `rvs validate`, start `rvs-studio`, `./uninstall.sh`. Done for 0.1.0 on Linux.
8. `pip-audit` needs the vulnerability database (network); run it on a connected build machine, never inside the product.

## Independent review (done for 0.1.0)
Five reviewers examined core data integrity, exporters/import, change control/Git, the GUI, and CLI/installer/security, each with reproducers; the findings and what was decided are in DECISIONS D79-D82 and DEVIATIONS V24. Repeat this pass before a major release.

## Licences to review (0.1.0)
- PySide6-Essentials / shiboken6: LGPL-3.0 (used under LGPL; the one-folder bundle keeps the Qt libraries as separate shared files, so users can replace them).
- Doorstop 3.2: LGPL-3.0. dulwich: Apache-2.0 (dual-licensed). Everything else is permissive; see `dist/rvs-licenses.txt`.
- Fonts: IBM Plex (SIL OFL), bundled with its licence.

## Open items before a customer release
- Windows build and scripts untested; no signing certificate configured.
- `TODO-COMPANY` / `TODO-STANDARD` values in `config/` (priority scale, word lists, change-request statuses, ECSS VCM layout).
