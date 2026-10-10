# CLAUDE.md — RVS (in `rvs/`; the repo root is an unrelated Doorstop 3.2 source clone, do not edit it)

Spec: `docs/SPEC.md`. Design: `docs/ARCHITECTURE.md`. Plan: `docs/PLAN.md`. Decisions/deviations: `docs/DECISIONS.md`, `docs/DEVIATIONS.md`.

## Commands (run in `rvs/`, venv with `pip install -e ".[dev]"`)
- Tests: `QT_QPA_PLATFORM=offscreen pytest`
- Lint/format/types: `ruff check . && ruff format --check . && mypy`
- Validate a project: `rvs validate examples/minimal10 [--format json] [--strict]`
- Regenerate reference project: `python scripts/gen_examples.py`; stress project: `python scripts/gen_stress.py <dir>`
- Open the GUI on an example: `rvs-studio` then File > Open Project… `examples/satellite300` (has 7 seeded defects, plus matrices and graph)
- Fast validate: `rvs validate --fast`; JSON findings have the keys code, severity, message, hint, location, uid (+ exit_code)
- Performance: `python scripts/gen_stress.py <dir>` then `RVS_STRESS_DIR=<dir> pytest -m perf -s`
- Export: `rvs export <project> --vcm|--trace SRC:DST[:up|down]|--coverage|--impact UID|--items|--spec|--reqif [--format csv|json|xlsx|html|docx|pdf|reqif] [-o FILE]`. Without `--format` it follows the `-o` extension, else csv (html for `--spec`, reqif for `--reqif`); xlsx/docx/pdf need `-o`. Import: `rvs import <project> items.xlsx [--dry-run] [--reason ...]`. `SOURCE_DATE_EPOCH` pins the generated time (byte-identical outputs)
- Goldens: `PYTHONPATH=tests python scripts/gen_goldens.py` after an intentional output change (review the diff)
- Change control: `rvs cr new|list|show|status|defer`, `rvs baseline create|list|verify`, `rvs diff <project> <baseline|working> <baseline|working> [--format ...]`, `rvs export --baseline NAME`, `rvs import --cr CR-0001`
- Package: `sh scripts/build_release.sh` (clean venv, pinned PyInstaller, licences + SBOM + `GLIBC-MIN` in the bundle, manifest, selftest, offscreen start, deterministic archive). Do not run `pyinstaller` by hand from a dev environment: the bundle would contain dev packages
- SBOM + licences (runtime install only, in a temp venv): `sh scripts/sbom.sh`; offline wheelhouse: `sh scripts/build_wheelhouse.sh`; lock file (needs network): `sh scripts/make_lock.sh`. All release scripts work in temporary folders and leave no `build/` or `*.egg-info` behind (`scripts/_common.sh`)
- Linux system libs for Qt: libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1 libxcb-util1; the prebuilt bundle needs glibc 2.38+ (docs/RELEASE.md)

- ReqIF: `rvs export <project> --reqif [--document P] -o f.reqif`; `rvs import <project> f.reqif [--document P] [--map NAME=COLUMN] --dry-run` (rows go through the same `plan_import`)
- Guide: edit `docs/guide/*.md`, then `python scripts/build_guide.py` (tests fail if `rvs_core/guide/guide.html` is stale or an option/code is undocumented)
- Release: `sh scripts/build_release.sh` (optional `RVS_SIGN_CMD`). Installers: `packaging/install-linux.sh` / `uninstall-linux.sh` (become `install.sh` / `uninstall.sh` in the archive; per user, staged with `mktemp`, delete only folders they created, warn about missing libraries and old glibc) and `install-windows.ps1` (never run on Windows). Test installer changes with `dash` in a temp HOME incl. paths with spaces (tests/test_packaging.py)
- Modes: guided (wizard, help) and expert (dense, in-place edit); user settings in `rvs_core/userconfig.py`, never project data

## Rules
- Tests first. Keep the guide in step: edit `docs/guide/*.md` with the code, rebuild, and keep DECISIONS/DEVIATIONS current (mark superseded entries instead of deleting them).
- `rvs_core` has no GUI/network imports; only `rvs_core/adapter` may import `doorstop` (enforced by tests/test_layering.py).
- Dev/release tooling only in `[project.optional-dependencies] dev`.
- Never write project content to logs/temp outside the project (write temporary files next to their target, via `rvs_core/atomicio.py`); no timestamps in generated files except the provenance time (`SOURCE_DATE_EPOCH` pins it).
- Never invent standards values: placeholders `TODO-STANDARD` in config.
- Python 3.11–3.13. Pin versions.
- Validation/IO must stay read-only and use Doorstop's API; see docs/DEVIATIONS.md V07–V12 before touching the adapter.
- No network-capable module may be imported in the RVS process (offline test enforces it; see adapter/_offline_guard.py). Don't add dependencies that import `socket`/`ssl`/`http`/`requests`.
- Typed links live in `config/links.yaml`; never read `link_*` attributes directly outside `rvs_core.trace`. Matrices are `MatrixTable`s; add formats by rendering that, not by recomputing.
- Item reads may be served from `.rvs-cache/` (D43); anything that edits item files outside the adapter must be at least 2 s old before re-reading in tests (see tests/test_cache.py).
- Outputs: build a `MatrixTable` or `Doc` and render it; never hand-write XLSX/DOCX/PDF bytes elsewhere. Set cells with `xlsx_out.set_text` (no formulas). Anything that must be reproducible takes its timestamp from `Provenance`.
- Background work in the GUI goes through `rvs_gui/jobs.run_in_background`.
- Git access only through `rvs_core/vcs/git.py` (dulwich; never signs, never touches remotes). Doorstop's own git calls are disabled (V18); do not re-enable `ADDREMOVE_FILES`.
- Anything under `.rvs-cache/` must stay invisible to Doorstop (`.doorstop.skip-all`) and to Git (`.gitignore`).
- CLI: no tracebacks (short message, exit 1; `RVS_DEBUG=1` shows it). Editing `derived`/`normative`/`level`/`header`/`ref`/`active` is only via CSV/XLSX import (V31).
