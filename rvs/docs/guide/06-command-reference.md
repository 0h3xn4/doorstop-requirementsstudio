# Command reference

`rvs` is the command line of the application. All commands work offline and never change a project unless they are meant to (`init`, `import`, `cr`, `baseline create`). Exit codes: **0** success, **1** problems found, **2** wrong usage, **3** the project cannot be loaded.

## rvs validate

`rvs validate PROJECT [--format text|json] [--strict] [--fast]`

Checks a project: file format, configuration, links, quality rules, change requests and baselines. `--strict` counts warnings as errors. `--fast` skips Doorstop's own tree validation (RVS checks still run), which matters for very large projects. `--format json` lists each finding with code, severity, item, message and how to fix it.

## rvs init

`rvs init FOLDER [--name NAME] [--template minimal|satellite|software] [--git]` creates a new project from a template; `rvs init --list-templates` shows the templates and what they contain. `--git` also creates a Git repository in the folder.

## rvs export

`rvs export PROJECT (--vcm | --trace SRC:DST[:up|down] | --coverage | --impact UID | --items | --spec | --reqif) [--format csv|json|xlsx|html|docx|pdf] [-o|--output FILE] [--document PREFIX] [--method M] [--level L] [--status S] [--only-gaps] [--baseline NAME]`

See *Import and export*. Without `-o` text formats are written to standard output.

## rvs import

`rvs import PROJECT FILE [--dry-run] [--skip-errors] [--reason TEXT] [--cr CR-ID] [--user NAME] [--document PREFIX] [--map NAME=COLUMN]`

Imports a CSV or XLSX table of items, or a ReqIF file (`--document` and `--map` apply to ReqIF only; see *ReqIF exchange*). `--dry-run` shows the plan and writes nothing. Exit code 1 means rows had errors.

## rvs cr

Change requests.

- `rvs cr new PROJECT TITLE [-d|--description DESCRIPTION] [--item UID]… [--user NAME]` raises a change request.
- `rvs cr list PROJECT` lists them with their status.
- `rvs cr show PROJECT CR-ID` shows one, with its status log and the items edited under it.
- `rvs cr status PROJECT CR-ID STATUS [--note TEXT] [--user NAME]` moves it to another status.
- `rvs cr defer PROJECT CR-ID --reason TEXT [--user NAME]` defers it so it does not block baselines.

## rvs baseline

- `rvs baseline create PROJECT NAME -m|--message MESSAGE [--defer CR-ID=REASON]… [--init-git] [--user NAME]` creates a baseline.
- `rvs baseline list PROJECT [--format text|json]` lists baselines.
- `rvs baseline verify PROJECT NAME` checks a baseline against its manifest and tag.

## rvs diff

`rvs diff PROJECT LEFT RIGHT [--document PREFIX] [--format text|json|csv|html|docx|pdf] [-o|--output FILE]`

`LEFT` and `RIGHT` are baseline names or `working`.

## rvs selftest

`rvs selftest [--manifest FOLDER]` checks the installation; see *Installation and checks*.

## rvs guide

`rvs guide [-o|--output FILE]` prints where the offline user guide is, or copies it to `FILE`.

## rvs --version

Prints the RVS and Doorstop versions.
