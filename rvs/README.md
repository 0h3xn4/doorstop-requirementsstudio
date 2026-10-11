# Requirements & Verification Studio (RVS)

*Offline requirements management and verification tracking for engineering projects.*

[![RVS CI](https://github.com/0h3xn4/doorstop-requirementsstudio/actions/workflows/rvs-ci.yml/badge.svg)](https://github.com/0h3xn4/doorstop-requirementsstudio/actions/workflows/rvs-ci.yml)
![Python 3.11 to 3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue)

![RVS: documents on the left, requirements in the middle, the editor on the right, problems at the bottom](docs/guide/images/items-guided.png)

This is the `rvs/` folder of the repository [doorstop-requirementsstudio](https://github.com/0h3xn4/doorstop-requirementsstudio), a fork of [Doorstop](https://doorstop.dev). The repository's top-level README explains how the two parts fit together; this page is the README of the tool.

## What is this?

RVS helps you write requirements, link them from the mission down to the subsystems, say how each one will be verified, and keep control of changes. Every requirement is a small text file in a folder, so a project can be kept in Git and read without RVS. It is a desktop application (`rvs-studio`) and a command line (`rvs`) and **never uses the network**. It is built on Doorstop 3.2 and aimed at space and other engineering projects that need traceability and ECSS-style verification control matrices (VCMs).

## Quick start

You need Python 3.11, 3.12 or 3.13. From the repository root:

```
python3 -m venv .venv && source .venv/bin/activate     # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install ./rvs
rvs --version                                           # rvs 0.1.0 (doorstop 3.2)
rvs selftest                                            # ends with: All checks passed.
rvs validate rvs/examples/satellite300 | grep -E "^(ERROR|WARNING)"    # 3 errors and 15 warnings (7 planted on purpose)
rvs-studio                                              # open the window, then File > Open Example…
```

Inside the `rvs/` folder use `pip install .` and `examples/satellite300`. Linux needs a few system libraries for the window: see [Getting started](docs/getting-started.md#what-you-need).

## Where to go next

| I want to ... | Go to |
|---|---|
| Install it and get a first result | [Getting started](docs/getting-started.md) |
| Learn the tasks one by one | [User manual](docs/user-manual/README.md) |
| Try a ready-made project | [Examples](examples/README.md) |
| Fix an error | [Troubleshooting](docs/troubleshooting.md) · [FAQ](docs/faq.md) |
| Look up a word or acronym | [Glossary](docs/glossary.md) |
| Work faster, script it, exchange data | [Tips](docs/tips.md) |
| Look up a field, rule or finding code | [User guide](docs/guide/01-getting-started.md) (press F1 in the program) |
| See every document | [Documentation index](docs/README.md) |
| Work on RVS | [Contributing](CONTRIBUTING.md) · [Developer docs](docs/developer/README.md) · [Changelog](CHANGELOG.md) |

## Features

- Requirements as text files, in a tree of documents, with parent links and typed links.
- Quality rules with a hint on how to fix each finding.
- Verification items, a verification control matrix, traceability, coverage, impact and a graph.
- Change requests, immutable baselines bound to Git tags, and a word-by-word comparison of two states.
- CSV, XLSX and ReqIF import; CSV, XLSX, ReqIF, DOCX, PDF, HTML and JSON export with provenance.
- Guided and expert modes, light and dark themes, built-in offline help.

## Requirements

Python 3.11 to 3.13 and `pip`. Tested on Linux and Windows on every change; macOS is untested, and the Windows installer has never been run. Git does not need to be installed.

## Licence and status

Version 0.1.0. Proprietary, internal use only (see `LICENSE`). Placeholders for values that depend on a standard or your organisation are marked `TODO-STANDARD` and `TODO-COMPANY`.

## Related tools

[Doorstop](https://doorstop.dev) (the library RVS is built on), and any tool that reads or writes ReqIF, CSV or XLSX: see [Tips](docs/tips.md#working-with-other-tools).
