# Developer guide

This page is for people who change RVS itself: how the repository is laid out, how to set up, test and lint, how the documentation is built, how a release is made, and how to keep the fork in step with upstream Doorstop.

**Contents:** [The repository](#the-repository) · [Set up](#set-up) · [Tests and lint](#tests-and-lint) · [Code layout](#code-layout) · [Documentation](#documentation) · [Continuous integration](#continuous-integration) · [Releases](#releases) · [Syncing with upstream](#syncing-with-upstream) · [Known side effects of the fork](#known-side-effects-of-the-fork)

## The repository

This repository is a **fork** of [doorstop-dev/doorstop](https://github.com/doorstop-dev/doorstop) (default branch `develop`; there is no `main`). The repository root is upstream Doorstop (`doorstop/`, `docs/`, `reqs/`, `mkdocs.yml`, ...) and should stay as upstream has it so that syncing stays easy. **All RVS work is in `rvs/`**, plus `.github/workflows/rvs-ci.yml`. RVS uses the released Doorstop 3.2 from PyPI as a library; it does not import the source in the repository root.

## Set up

```
git clone https://github.com/0h3xn4/doorstop-requirementsstudio.git
cd doorstop-requirementsstudio/rvs
python3 -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Python 3.11, 3.12 or 3.13. On Linux install the Qt system libraries listed in [Getting started](../getting-started.md#what-you-need). Development tools (pytest, ruff, mypy, PyInstaller, ...) are only in the `dev` extra; the runtime install has none of them.

## Tests and lint

Run these in `rvs/`:

```
QT_QPA_PLATFORM=offscreen pytest              # about 800 tests, 3 to 5 minutes
ruff check . && ruff format --check . && mypy
```

`QT_QPA_PLATFORM=offscreen` runs the Qt tests without a screen. Slow performance tests are skipped unless asked for: `python scripts/gen_stress.py /tmp/stress` then `RVS_STRESS_DIR=/tmp/stress pytest -m perf -s`. Write the test first; the checks above must pass on Python 3.11, 3.12 and 3.13 (CI runs all three, on Linux and Windows).

After an intentional change of an export, regenerate the golden files and review the difference: `PYTHONPATH=tests python scripts/gen_goldens.py`.

## Code layout

| Folder | What it holds | Rule |
|---|---|---|
| `src/rvs_core/` | the engine: project model, rules, matrices, change control, import/export | no GUI and no network imports; only `rvs_core/adapter` imports `doorstop` (a test enforces it) |
| `src/rvs_cli/` | the `rvs` command | never prints a Python traceback |
| `src/rvs_gui/` | the Qt window | background work goes through `jobs.run_in_background` |
| `tests/` | the tests | `test_layering.py` and `test_offline.py` guard the rules above |
| `examples/` | the two example projects | written by `scripts/gen_examples.py`; do not edit by hand |
| `scripts/` | generators and release scripts | |
| `packaging/` | installers and the PyInstaller spec | |
| `docs/` | documentation | see below |

The design is described in [ARCHITECTURE.md](../ARCHITECTURE.md); the decisions and deviations in [DECISIONS.md](../DECISIONS.md) and [DEVIATIONS.md](../DEVIATIONS.md). Offline is a hard rule: no module that can reach the network may be imported (see `adapter/_offline_guard.py`).

## Documentation

- **The user guide** is `docs/guide/*.md`. The program shows it offline (F1). After editing it, run `python scripts/build_guide.py`; a test fails if the built copy `src/rvs_core/guide/guide.html` is stale or if a command option or finding code is undocumented.
- **Everything else** in `docs/` is plain Markdown, linked from [the index](../README.md). Keep pages short, start each with one sentence on what it is for and end with "Next:" links.
- **Screenshots** of the guide: `QT_QPA_PLATFORM=offscreen python scripts/build_screenshots.py`. The pictures in `docs/images/` were made the same way from the satellite example; regenerate them when the look of the window changes.
- **Check the links** before a pull request. With Node installed: `npx markdown-link-check -c docs/developer/mlc-offline.json FILE.md` for each file (that config ignores `http` addresses, so it checks internal links and images only), or `lychee --offline .` for the whole tree. Anchors (`#heading`) are checked by neither of the offline checks in every case: open the page on GitHub to be sure.
- **Examples in the docs are real.** Run the commands you write, in a clean virtual environment, and paste the output you get.
- Record design decisions in `DECISIONS.md` and deviations in `DEVIATIONS.md`; mark old entries as superseded instead of deleting them.

## Continuous integration

| Workflow | What it does |
|---|---|
| `.github/workflows/rvs-ci.yml` | RVS: ruff, mypy and the tests on Linux and Windows for Python 3.11 to 3.13, a headless GUI start, and a packaging job. It runs only when something under `rvs/` changes. |
| `test-linux.yml`, `test-osx.yml`, `test-windows.yml`, `_common.yml` | Upstream Doorstop's own test suite. They run in the checked-out folder. |

## Releases

The checklist is in [RELEASE.md](../RELEASE.md): lint and tests on three Python versions, rebuild the guide, run `sh scripts/build_release.sh` (clean virtual environment, pinned PyInstaller, licences and SBOM, manifest, self-test, deterministic archive), install the archive somewhere clean and run `rvs selftest --manifest`. Record the version in `CHANGELOG.md`. The Windows build has never been run: see the open items in RELEASE.md.

## Syncing with upstream

Two things come from upstream and must be refreshed together: the rest of the repository (the `doorstop/` package, `docs/`, ...) and the original README that sits at the bottom of the repository's `README.md`.

1. Add the upstream remote once and fetch it:

   ```
   git remote add upstream https://github.com/doorstop-dev/doorstop.git
   git fetch upstream
   ```

2. Merge upstream's `develop` into a new branch and resolve conflicts (RVS lives in its own folder, so conflicts are rare; the likely ones are `README.md` and the two workflow files `test-linux.yml` and `test-osx.yml`):

   ```
   git switch -c sync-upstream origin/develop
   git merge upstream/develop
   ```

3. Refresh the untouched copy of upstream's README and the embedded block in `README.md`:

   ```
   git show upstream/develop:README.md > docs/upstream/README.upstream.md
   python rvs/docs/developer/refresh_upstream_readme.py
   ```

   The script copies `docs/upstream/README.upstream.md` between the markers `<!-- BEGIN UPSTREAM README -->` and `<!-- END UPSTREAM README -->` in `README.md` and demotes every heading by one level; nothing else changes. `--check` reports whether `README.md` is up to date. If upstream's README gained **relative** links or images (today it has none; all its links are absolute), fix them to point at the upstream URL, and list them in the documentation audit.

4. Update the note above the markers in `README.md` (the upstream commit the README was taken from, and the date the file last changed upstream):
   `git log -1 --format='%h %ad' --date=short upstream/develop -- README.md`.
5. Run the RVS checks above and open a pull request.

Upstream's own documentation (`docs/`, `CONTRIBUTING.md`, `CHANGELOG.md`, `mkdocs.yml`) is taken as it comes and is listed under *Upstream Doorstop documentation* in [the index](../README.md#upstream-doorstop-documentation).

## Known side effects of the fork

- **`rvs/.doorstop.skip-all`** hides the RVS folder from Doorstop's document tree. Without it, plain `doorstop` run at the repository root stops with "multiple root documents", because every example project has a root document of its own. A test (`tests/test_repo_layout.py`) checks it.
- **Do not run plain `doorstop` at the repository root casually.** It validates and may rewrite files of Doorstop's own `reqs/` folder (it removed trailing spaces from `reqs/tutorial/TUT017.yml` once).
- **`docs/index.md` is a link to the root `README.md`** (upstream's Makefile re-creates it with `ln -sf ../README.md index.md` when it builds the Doorstop site). The upstream documentation site would therefore show the RVS part first, and the relative links in the RVS part would not resolve there. This fork does not publish that site; if you ever do, point the link at `docs/upstream/README.upstream.md`.
- **The root `pyproject.toml` has `readme = "README.md"`.** That is upstream's package description; if you ever build upstream Doorstop from this repository, change it to `docs/upstream/README.upstream.md` first.

Next: [Contributing](../../CONTRIBUTING.md) · [Release checklist](../RELEASE.md) · [Architecture](../ARCHITECTURE.md)
