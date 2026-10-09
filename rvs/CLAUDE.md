# CLAUDE.md — RVS (in `rvs/`; the repo root is an unrelated Doorstop 3.2 source clone, do not edit it)

Spec: `docs/SPEC.md`. Design: `docs/ARCHITECTURE.md`. Plan: `docs/PLAN.md`. Decisions/deviations: `docs/DECISIONS.md`, `docs/DEVIATIONS.md`.

## Commands (run in `rvs/`, venv with `pip install -e ".[dev]"`)
- Tests: `QT_QPA_PLATFORM=offscreen pytest`
- Lint/format/types: `ruff check . && ruff format --check . && mypy`
- Validate a project: `rvs validate examples/minimal10 [--format json] [--strict]`
- Regenerate reference project: `python scripts/gen_examples.py`; perf spike: `python scripts/perf_spike.py <dir>`
- Open the GUI on an example: `rvs-studio` then File > Open Project… `examples/satellite300` (has 7 seeded defects, plus matrices and graph)
- Export: `rvs export <project> --vcm|--trace SRC:DST[:up]|--coverage|--impact UID [--format json] [-o file]`; fast validate: `rvs validate --fast`
- Performance: `python scripts/gen_stress.py <dir>` then `RVS_STRESS_DIR=<dir> pytest -m perf -s`
- Package: `pyinstaller packaging/rvs.spec --noconfirm` → `dist/rvs-studio/`
- SBOM + licences (runtime install only): `sh scripts/sbom.sh`
- Offline wheelhouse: `sh scripts/build_wheelhouse.sh`
- Linux system libs for Qt: libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3

## Rules
- Tests first; one milestone per session; stop at its acceptance criteria.
- `rvs_core` has no GUI/network imports; only `rvs_core/adapter` may import `doorstop` (enforced by tests/test_layering.py).
- Dev/release tooling only in `[project.optional-dependencies] dev`.
- Never write project content to logs/temp outside the project; no timestamps in generated files.
- Never invent standards values: placeholders `TODO-STANDARD` in config.
- Python 3.11–3.13. Pin versions.
- Validation/IO must stay read-only and use Doorstop's API; see docs/DEVIATIONS.md V07–V12 before touching the adapter.
- No network-capable module may be imported in the RVS process (offline test enforces it; see adapter/_offline_guard.py). Don't add dependencies that import `socket`/`ssl`/`http`/`requests`.
- Typed links live in `config/links.yaml`; never read `link_*` attributes directly outside `rvs_core.trace`. Matrices are `MatrixTable`s; add formats by rendering that, not by recomputing.
- Item reads may be served from `.rvs-cache/` (D43); anything that edits item files outside the adapter must be at least 2 s old before re-reading in tests (see tests/test_cache.py).
