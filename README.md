> **This repository is Requirements & Verification Studio (RVS), a tool built on top of [Doorstop](https://doorstop.dev).**
> The first part of this README covers RVS. The original Doorstop README follows, unchanged, below the divider:
> [jump to it](#original-doorstop-readme).

# Requirements & Verification Studio (RVS)

*Offline requirements management and verification tracking for engineering projects.*

[![RVS CI](https://github.com/0h3xn4/doorstop-requirementsstudio/actions/workflows/rvs-ci.yml/badge.svg)](https://github.com/0h3xn4/doorstop-requirementsstudio/actions/workflows/rvs-ci.yml)
![Python 3.11 to 3.13](https://img.shields.io/badge/python-3.11%E2%80%933.13-blue)
![Licence: proprietary, internal](https://img.shields.io/badge/licence-proprietary%20(internal)-lightgrey)

![RVS: documents on the left, requirements in the middle, the editor on the right, problems at the bottom](rvs/docs/guide/images/items-guided.png)

## What is this?

RVS helps you write requirements, link them from the mission down to the subsystems, say how each one will be verified, and keep control of changes. Every requirement is a small text file in a folder, so a project can be kept in Git and read without RVS. It comes as a desktop application (`rvs-studio`) and a command line (`rvs`), and it **never uses the network**. It is aimed at space and other engineering projects that need traceability and ECSS-style verification control matrices (VCMs). It is built on [Doorstop](https://doorstop.dev), which this repository is a copy of.

## Quick start

You need Python 3.11, 3.12 or 3.13 (on Linux the window also needs a few system libraries: see [Getting started](rvs/docs/getting-started.md#what-you-need)).

```
git clone https://github.com/0h3xn4/doorstop-requirementsstudio.git
cd doorstop-requirementsstudio
python3 -m venv .venv && source .venv/bin/activate     # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install ./rvs                                       # install the rvs folder, not the repository root
rvs --version                                           # rvs 0.1.0 (doorstop 3.2)
rvs selftest                                            # ends with: All checks passed.
rvs validate rvs/examples/satellite300 | grep -E "^(ERROR|WARNING)"    # 3 errors and 15 warnings (7 of them planted on purpose)
rvs-studio                                              # open the window, then File > Open Example…
```

The full walk-through, including a first project built from the command line, is in [Getting started](rvs/docs/getting-started.md).

## Where to go next

| I want to ... | Go to |
|---|---|
| Install it and get a first result | [Getting started](rvs/docs/getting-started.md) |
| Learn the tasks one by one ("How do I ...?") | [User manual](rvs/docs/user-manual/README.md) |
| Try a ready-made project | [Examples](rvs/examples/README.md) |
| Fix an error | [Troubleshooting](rvs/docs/troubleshooting.md) · [FAQ](rvs/docs/faq.md) |
| Look up a word or acronym (ECSS, VCM, baseline ...) | [Glossary](rvs/docs/glossary.md) |
| Work faster, script it, exchange data with other tools | [Tips](rvs/docs/tips.md) |
| Read every field, rule and finding code | [User guide](rvs/docs/guide/01-getting-started.md) (also built into the program: press F1) |
| See every document at a glance | [Documentation index](rvs/docs/README.md) |
| Work on RVS itself | [Contributing](rvs/CONTRIBUTING.md) · [Developer docs](rvs/docs/developer/README.md) · [Changelog](rvs/CHANGELOG.md) |
| Read about Doorstop itself | [Original Doorstop README](#original-doorstop-readme) · [Upstream Doorstop documentation](rvs/docs/README.md#upstream-doorstop-documentation) |

## Features

- **Requirements as text files**, in documents that form a tree, with parent links and typed links (`satisfies`, `refines`, `verifies`, `conflicts-with`).
- **Quality rules** that check each requirement ("shall", one statement, no vague words, acronyms defined, has a parent, is verified) and say how to fix what they find.
- **Verification tracking**: verification items with method, level, status and evidence; a verification control matrix, a traceability matrix, coverage, impact analysis and a graph.
- **Change control**: change requests, **baselines** bound to Git tags that can never be altered, a reason for every change to a baselined item, and a word-by-word comparison between two states.
- **Import and export**: CSV and XLSX tables, ReqIF, and reports as DOCX, PDF, HTML and JSON, all with provenance and byte-identical when generated for the same time.
- **Guided and expert modes**, light and dark themes, keyboard-first, built-in offline help.
- **Offline by design**: no update check, no telemetry, no cloud; the tests check that no network library is loaded.

## Requirements

- Python 3.11, 3.12 or 3.13 and `pip`.
- Linux: a few system libraries for the window (listed in [Getting started](rvs/docs/getting-started.md#what-you-need)); the command line needs none.
- Tested on Linux and Windows (on every change). **macOS has not been tested**, and the Windows installer has never been run.
- No Git installation is needed: RVS has a built-in one for local use.

## Licence and status

Version **0.1.0**, first release. The `rvs/` folder is proprietary, for internal use (`rvs/LICENSE`). Everything else in this repository is [Doorstop](https://doorstop.dev), under the LGPL-3.0 (`LICENSE.md`). Values that depend on a standard or on your organisation are marked `TODO-STANDARD` and `TODO-COMPANY` in the project configuration: RVS never invents them. Open points are listed in the [release checklist](rvs/docs/RELEASE.md).

## What this fork adds to Doorstop

| | Upstream Doorstop | This repository |
|---|---|---|
| The `doorstop` package, its tests, `docs/`, `reqs/`, `mkdocs.yml`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE.md` | yes | **unchanged** |
| `rvs/`: the application (`rvs-studio`), the command line (`rvs`), the quality rules, matrices, change control, import/export, the user guide, the examples | no | **added** |
| `README.md` | the Doorstop README | this README on top, the original Doorstop README **verbatim** below (a copy of the original is in `docs/upstream/README.upstream.md`) |
| `.github/workflows/rvs-ci.yml` | no | **added**: tests, lint and type checks on Linux and Windows, plus a packaging job |
| `.github/workflows/test-linux.yml`, `test-osx.yml` | hard-coded the path `/home/runner/work/doorstop/doorstop` | **changed** to run in the checked-out folder (the path only exists in the upstream repository) |
| `rvs/.doorstop.skip-all` | no | **added** so that plain `doorstop` run at the repository root does not pick up the RVS example projects as part of Doorstop's own document tree |

The fork was made from upstream commit `c944c86` (Doorstop 3.2 development). RVS uses the released Doorstop 3.2 from PyPI as a library; it does not use the copy of the source in this repository's root.

## Related tools

- [Doorstop](https://doorstop.dev): the requirements tool RVS is built on (the original README is below).
- Any requirements tool that reads and writes **ReqIF**, and any spreadsheet program: see [Tips](rvs/docs/tips.md#working-with-other-tools).

---

# Original Doorstop README

> What follows is the README of the upstream project [doorstop-dev/doorstop](https://github.com/doorstop-dev/doorstop), reproduced verbatim from
> commit `c944c86` of its `develop` branch (the file itself last changed upstream on 2026-06-26, commit `b12f6d8`). The only change is that
> its headings are one level deeper so that this page's table of contents stays clean. An untouched copy is kept in
> [`docs/upstream/README.upstream.md`](docs/upstream/README.upstream.md); how to refresh it is described in the
> [developer docs](rvs/docs/developer/README.md#syncing-with-upstream).

<!-- BEGIN UPSTREAM README -->
[![Linux Tests](https://github.com/doorstop-dev/doorstop/actions/workflows/test-linux.yml/badge.svg)](https://github.com/doorstop-dev/doorstop/actions/workflows/test-linux.yml)
[![macOS Tests](https://github.com/doorstop-dev/doorstop/actions/workflows/test-osx.yml/badge.svg)](https://github.com/doorstop-dev/doorstop/actions/workflows/test-osx.yml)
[![Windows Tests](https://github.com/doorstop-dev/doorstop/actions/workflows/test-windows.yml/badge.svg)](https://github.com/doorstop-dev/doorstop/actions/workflows/test-windows.yml)
<br>
[![Coverage Status](https://img.shields.io/codecov/c/gh/doorstop-dev/doorstop)](https://codecov.io/gh/doorstop-dev/doorstop)
[![Scrutinizer Code Quality](https://img.shields.io/scrutinizer/g/doorstop-dev/doorstop.svg)](https://scrutinizer-ci.com/g/doorstop-dev/doorstop/?branch=develop)
[![PyPI Version](https://img.shields.io/pypi/v/Doorstop.svg)](https://pypi.org/project/Doorstop)
<br>
[![Gitter](https://badges.gitter.im/doorstop-dev/community.svg)](https://gitter.im/doorstop-dev/community)
[![Google](https://img.shields.io/badge/forum-on_google-387eef)](https://groups.google.com/forum/#!forum/doorstop-dev)
[![Best Practices](https://bestpractices.coreinfrastructure.org/projects/754/badge)](https://bestpractices.coreinfrastructure.org/projects/754)

## Overview

Doorstop is a [requirements management](https://alternativeto.net/software/doorstop/) tool that facilitates the storage of textual requirements alongside source code in version control.

<img align="left" width="100" src="https://raw.githubusercontent.com/doorstop-dev/doorstop/develop/docs/images/logo-black-white.png"/>

When a project leverages this tool, each linkable item (requirement, test case, etc.) is stored as a YAML file in a designated directory. The items in each directory form a document. The relationship between documents forms a tree hierarchy. Doorstop provides mechanisms for modifying this tree, validating item traceability, and publishing documents in several formats.

Doorstop is under active development and we welcome contributions.
The project is licensed as [LGPLv3](https://github.com/doorstop-dev/doorstop/blob/develop/LICENSE.md).
To report a problem or a security vulnerability please [raise an issue](https://github.com/doorstop-dev/doorstop/issues).
Additional references:

- Publication: [JSEA Paper](http://www.scirp.org/journal/PaperInformation.aspx?PaperID=44268#.UzYtfWRdXEZ)
- Talks: [GRDevDay](https://speakerdeck.com/jacebrowning/doorstop-requirements-management-using-python-and-version-control), [BarCamp](https://speakerdeck.com/jacebrowning/strip-searched-a-rough-introduction-to-requirements-management)
- Sample: [Generated HTML](https://doorstop-dev.github.io/doorstop/)

## Setup

### Requirements

- Python 3.10+
- A version control system for requirements storage

### Installation

Install Doorstop with pip:

```sh
$ pip install doorstop
```

or add it to your [Poetry](https://python-poetry.org/) project:

```sh
$ poetry add doorstop
```

After installation, Doorstop is available on the command-line:

```sh
$ doorstop --help
```

And the package is available under the name 'doorstop':

```sh
$ python
>>> import doorstop
>>> doorstop.__version__
```

## Usage

Switch to an existing version control working directory, or create one:

```sh
$ git init .
```

### Create documents

Create a new parent requirements document:

```sh
$ doorstop create SRD ./reqs/srd
```

Add a few items to that document:

```sh
$ doorstop add SRD
$ doorstop add SRD
$ doorstop add SRD
```

### Link items

Create a child document to link to the parent:

```sh
$ doorstop create HLTC ./tests/hl --parent SRD
$ doorstop add HLTC
```

Link items between documents:

```sh
$ doorstop link HLTC001 SRD002
```

### Publish reports

Run integrity checks on the document tree:

```sh
$ doorstop
```

Publish the documents as HTML:

```sh
$ doorstop publish all ./public
```
<!-- END UPSTREAM README -->
