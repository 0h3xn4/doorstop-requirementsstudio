# CLAUDE.md — RVS (in `rvs/`; the repo root is an unrelated Doorstop 3.2 source clone, do not edit it)

Spec: `docs/SPEC.md`. Design: `docs/ARCHITECTURE.md`. Plan: `docs/PLAN.md`. Decisions/deviations: `docs/DECISIONS.md`, `docs/DEVIATIONS.md`.

## Commands (run in `rvs/`, venv with `pip install -e ".[dev]"`)
- Tests: `QT_QPA_PLATFORM=offscreen pytest`
- Lint/format/types: `ruff check . && ruff format --check . && mypy`
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
