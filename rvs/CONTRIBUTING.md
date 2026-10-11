# Contributing to RVS

This page explains how to propose a change to Requirements & Verification Studio (RVS). It covers the `rvs/` folder only; the rest of the repository is upstream [Doorstop](https://github.com/doorstop-dev/doorstop), and its own contributing guide is `CONTRIBUTING.md` at the repository root.

## Before you start

1. Read [Getting started](docs/getting-started.md) and use the tool for a few minutes.
2. Set up a development environment: [Developer guide](docs/developer/README.md#set-up).
3. Look at the rules below. They protect things users depend on.

## Making a change

1. Branch from `develop` (the default branch): `git switch -c my-change origin/develop`.
2. **Write the test first**, then the change. Tests are in `tests/`; the window is tested with `pytest-qt` in offscreen mode.
3. Run, in `rvs/`:

   ```
   QT_QPA_PLATFORM=offscreen pytest
   ruff check . && ruff format --check . && mypy
   ```

4. **Update the documentation in the same change**: the user guide (`docs/guide/*.md`, then `python scripts/build_guide.py`), the manual pages and examples that mention what you changed, `CHANGELOG.md`, and `docs/DECISIONS.md` or `docs/DEVIATIONS.md` if you decided something or departed from the specification. Run the commands you document.
5. Open a pull request into `develop`. Describe what changed and why, and what you tested. Continuous integration must pass on Linux and Windows for Python 3.11 to 3.13.

Keep commits small and their messages clear (`docs: ...`, `fix: ...`, `feat: ...`).

## Rules that protect users

- **Offline.** No code may import a module that can use the network. A test enforces it.
- **Layers.** `rvs_core` has no GUI or network imports; only `rvs_core/adapter` imports `doorstop`; the command line never prints a traceback.
- **Project data is plain text, and writes are whole-or-nothing.** Use the helpers in `rvs_core/atomicio.py` and the adapter; never write project content to logs or temporary files outside the project.
- **Never invent standard or company values.** Use the placeholders `TODO-STANDARD` and `TODO-COMPANY`.
- **Outputs are reproducible.** Take timestamps from the provenance object; never put the current time in a generated file.
- **Dependencies.** Runtime dependencies are pinned and need a licence review; development tools go only in the `dev` extra.
- Python 3.11 to 3.13.

## Reporting a problem

Open an issue with the command you ran, what you expected, what happened, the output of `rvs --version`, and your operating system. For a crash, the report in the `crash` folder next to `settings.json` contains only the error type and program locations, never project content, so it is safe to attach.

Next: [Developer guide](docs/developer/README.md) · [Architecture](docs/ARCHITECTURE.md) · [Documentation index](docs/README.md)
