# Command reference

`rvs` is the command line of the application. All commands work offline and never change a project unless they are meant to (`init`, `import`, `cr`, `baseline create`). `rvs --help` and `rvs COMMAND --help` list the options.

Exit codes: **0** success, **1** problems found (or an internal error), **2** wrong usage or a refused operation, **3** the project cannot be loaded, **130** interrupted with Ctrl+C. The command line never prints a Python traceback: an unexpected error gives a one-line message and exit code 1 (and a crash report without project content, see *Where RVS keeps its own settings*); set the environment variable `RVS_DEBUG=1` to see the traceback.

Commands that read a project (`validate`, `export`, `diff`) create a folder `.rvs-cache/` inside it to speed up the next run. It is ignored by Git and by Doorstop and can be deleted at any time.

## rvs validate

`rvs validate PROJECT [--format text|json] [--strict] [--fast]`

Checks a project: file format, configuration, links, quality rules, change requests and baselines. `--strict` counts warnings as errors. `--fast` skips Doorstop's own tree validation (RVS checks still run), which matters for very large projects. `--format json` prints `{"exit_code": N, "findings": [...]}`; each finding has the keys `code`, `severity` (`error`, `warning` or `info`), `message`, `hint` (how to fix it), `location` (a file path relative to the project, or empty) and `uid` (the item, or empty).

## rvs init

`rvs init FOLDER --name NAME [--template minimal|satellite|software] [--git]` creates a new project from a template. `FOLDER` and `--name` are both required (except with `--list-templates`). `rvs init --list-templates` shows the templates and what they contain. `--git` also creates a Git repository in the folder, which baselines need; without it the project is not under Git.

## rvs export

`rvs export PROJECT (--vcm | --trace SRC:DST[:up|down] | --coverage | --impact UID | --items | --spec | --reqif) [--format csv|json|xlsx|html|docx|pdf|reqif] [-o|--output FILE] [--document PREFIX] [--method M] [--level L] [--status S] [--only-gaps] [--baseline NAME]`

See *Import and export*. Without `--format` the format follows the extension of the `-o` file, else it is `csv` (`html` for `--spec`, `reqif` for `--reqif`). Without `-o` text formats are written to standard output; the binary formats (`xlsx`, `docx`, `pdf`) need `-o`. `--document`, `--method`, `--level` and `--status` can be repeated.

## rvs import

`rvs import PROJECT FILE [--dry-run] [--skip-errors] [--reason TEXT] [--cr CR-ID] [--user NAME] [--document PREFIX] [--map NAME=COLUMN]`

Imports a CSV or XLSX table of items, or a ReqIF file (`--document` and `--map` apply to ReqIF only; see *ReqIF exchange*). `--dry-run` shows the plan and writes nothing: it lists the rows that would be created or updated and the rows with errors, and counts the unchanged ones. Exit code 1 means rows had errors.

## rvs cr

Change requests.

- `rvs cr new PROJECT TITLE [-d|--description DESCRIPTION] [--item UID]… [--user NAME]` raises a change request.
- `rvs cr list PROJECT` lists them with their status.
- `rvs cr show PROJECT CR-ID` shows one, with its status log and the items edited under it.
- `rvs cr status PROJECT CR-ID STATUS [--note TEXT] [--user NAME]` moves it to another status.
- `rvs cr defer PROJECT CR-ID --reason TEXT [--user NAME]` defers it so it does not block baselines.

## rvs baseline

- `rvs baseline create PROJECT NAME -m|--message MESSAGE [--defer CR-ID=REASON]… [--init-git] [--user NAME]` creates a baseline. The project must be under Git; `--init-git` creates the repository first if there is none.
- `rvs baseline list PROJECT [--format text|json]` lists baselines. The JSON is a list of objects with `name`, `description`, `created_by`, `created`, `commit`, `tag`, `items`, `deferred` and `manifest_sha256`.
- `rvs baseline verify PROJECT NAME` checks a baseline against its manifest and tag (the only command that re-reads the tagged content: it reports `RVS-BASELINE-CORRUPT`). Exit code 1 when something is wrong.

## rvs diff

`rvs diff PROJECT LEFT RIGHT [--document PREFIX] [--format text|json|csv|html|docx|pdf] [-o|--output FILE]`

`LEFT` and `RIGHT` are baseline names or `working`. In the default `text` output a deleted word is written `[-old-]` and an inserted word `{+new+}`; `docx` and `pdf` need `-o`.

## rvs selftest

`rvs selftest [--manifest FOLDER]` checks the installation; see *Installation and checks*.

## rvs guide

`rvs guide [-o|--output FILE]` prints the path of the offline user guide (an HTML file), or copies it to `FILE`.

## rvs --version

Prints the RVS and Doorstop versions.
