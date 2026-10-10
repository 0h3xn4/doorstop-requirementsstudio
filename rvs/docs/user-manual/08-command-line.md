# The command line

This page shows how to use `rvs` in scripts and build pipelines. Everything the window does is also a command.

## Commands at a glance

| Command | Purpose |
|---|---|
| `rvs init FOLDER --name NAME [--template T] [--git]` | create a project |
| `rvs validate PROJECT [--format json] [--strict] [--fast]` | check a project |
| `rvs export PROJECT --vcm \| --trace SRC:DST \| --coverage \| --impact UID \| --items \| --spec \| --reqif [-o FILE]` | write a report |
| `rvs import PROJECT FILE [--dry-run] [--reason TEXT]` | import items from CSV, XLSX or ReqIF |
| `rvs cr new \| list \| show \| status \| defer ...` | change requests |
| `rvs baseline create \| list \| verify ...` | baselines |
| `rvs diff PROJECT LEFT RIGHT` | compare two states |
| `rvs selftest` | check the installation |
| `rvs guide` | the path of the offline user guide (HTML) |

`rvs --help` and `rvs COMMAND --help` list every option; the [command reference](../guide/06-command-reference.md) explains each.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | problems found (or an internal error: one line, no traceback) |
| 2 | wrong usage or a refused operation (message on standard error) |
| 3 | the project cannot be loaded |
| 130 | interrupted with Ctrl+C |

Set `RVS_DEBUG=1` to see the full traceback of an internal error.

## In a build pipeline

```
rvs validate my-project --format json --strict > findings.json
```

The command fails the job when there are errors or (with `--strict`) warnings. JSON findings have the keys `code`, `severity`, `message`, `hint`, `location`, `uid`, plus a top-level `exit_code`. To show only real problems in text: `rvs validate my-project | grep -E "^(ERROR|WARNING)"`.

```
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) rvs export my-project --vcm -o vcm.xlsx
```

pins the generation time to the last commit, so the same commit always gives the same file.

## Good to know

- Commands that read a project create a disposable `.rvs-cache/` folder inside it (ignored by Git).
- The user name recorded for changes is your operating-system login; commands that record something accept `--user NAME`.
- There is no command to add a single item: use the window, or `rvs import`.

Next: [Modes, themes, shortcuts, settings](09-settings-modes-shortcuts.md) · [Guide: command reference](../guide/06-command-reference.md) · [Troubleshooting](../troubleshooting.md)
