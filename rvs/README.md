# Requirements & Verification Studio (RVS)

Offline requirements management and verification tracking for engineering projects, built on [Doorstop](https://doorstop.dev)
3.2: traceability and verification matrices, quality rules, change requests, baselines (Git tags), reports in CSV, JSON,
XLSX, HTML, DOCX, PDF and ReqIF. A desktop application (`rvs-studio`) and a command line (`rvs`). Nothing in it uses the
network.

Licence: proprietary, internal use only (see `LICENSE`).

## Use

- Installed release: run `./install.sh` from the unpacked archive (per user, no administrator rights), then start
  *Requirements & Verification Studio* or run `rvs-studio`. Press **F1** for the user guide, or run `rvs guide`.
- From source (Python 3.11 to 3.13): `pip install -e ".[dev]"`, then `rvs --help` and `rvs-studio`.
  Qt needs a few system libraries on Linux; see `docs/RELEASE.md`.

## Develop

```
QT_QPA_PLATFORM=offscreen pytest
ruff check . && ruff format --check . && mypy
python scripts/build_guide.py        # after editing docs/guide/*.md
```

`CLAUDE.md` lists the commands and the rules for working on the code; `docs/` holds the specification, architecture,
decisions and deviations, and `docs/RELEASE.md` the release checklist.
