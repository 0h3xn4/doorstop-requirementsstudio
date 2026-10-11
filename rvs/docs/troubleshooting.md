# Troubleshooting

This page lists the errors you are most likely to meet, what they mean and how to fix them. The messages marked **real** were produced while testing a clean install; the others are the likely ones.

**Contents:** [Install](#install) · [Starting the window](#starting-the-window) · [Projects](#projects) · [Imports](#imports) · [Baselines](#baselines) · [Slow or odd behaviour](#slow-or-odd-behaviour)

## Install

### `rvs: command not found` (or `'rvs' is not recognized`)
The virtual environment is not active. Activate it (`source .venv/bin/activate`, or `.venv\Scripts\Activate.ps1` on Windows PowerShell) and try again. The command only exists inside that environment.

### On Windows PowerShell: "running scripts is disabled on this system"
Activating a virtual environment runs a script that PowerShell may block. Either run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `cmd` and `.venv\Scripts\activate.bat`.

### `ERROR: Package 'rvs' requires a different Python: 3.14.x not in '<3.14,>=3.11'`
RVS supports Python 3.11, 3.12 and 3.13. Install one of those and create the virtual environment with it (`python3.13 -m venv .venv`).

### `pip install` cannot reach the network
`pip` needs the network once, to download the libraries. If you are behind a proxy, set `HTTPS_PROXY` for pip. To install with no network at all, build a *wheelhouse* on a machine that has one (`sh scripts/build_wheelhouse.sh`, see the [release checklist](RELEASE.md)), copy it over and run `pip install --no-index --find-links wheelhouse rvs`.

### I installed the repository root and `rvs` is missing (or Doorstop behaves oddly)
The repository root is the **Doorstop** project itself. Install the `rvs` folder: `pip install ./rvs`. If you ran `pip install .` at the root, run `pip uninstall doorstop` and then `pip install ./rvs`.

### `rvs selftest` says a check failed
It prints one line per check. Send the failing line to the maintainers; a missing file usually means a damaged installation, so reinstall.

## Starting the window

### `Could not load the Qt platform plugin "xcb"` or `xcb-cursor0 or libxcb-cursor0 is needed` (Linux)
A system library the window needs is missing. On Debian or Ubuntu run:

```
sudo apt-get install libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1 libxcb-util1
```

The `rvs` command does not need these.

### The window does not appear over SSH, or in a container
There is no display. Use `rvs` (the command line) there, or run `rvs-studio` on a machine with a desktop. For automated tests `QT_QPA_PLATFORM=offscreen` runs the window without a screen.

### The window is too big or its panels are in a strange place
Delete the `geometry` and `layout` keys from `settings.json` (see [settings](user-manual/09-settings-modes-shortcuts.md#where-settings-are-kept)).

## Projects

### `ERROR RVS-PROJECT-MISSING: Project folder nowhere does not exist.` (**real**, exit 3)
The path is wrong. Give the folder that contains `rvs-project.yaml`.

### "That folder is not an RVS project" when opening
You chose a folder inside a project, or a parent of it. Choose the folder that contains `rvs-project.yaml`. Your previous project stays open.

### `rvs init: ... is already an RVS project; a project cannot be created inside another.` (**real**, exit 2)
`rvs init` will not create a project inside another one, and not in a folder that already holds files. Choose a new folder.

### `ERROR RVS-ITEM-UNREADABLE: An item file cannot be read.` (**real**, exit 3)
A hand edit broke the YAML of an item. The message names the file (here `broken/SYS/SYS-0001.yml`) and the line. Fix the file (`git diff` shows what changed) or restore it from Git, and validate again. Common slips: a missing closing bracket, a tab used to indent, a colon in a value that is not in quotes.

### `rvs validate` prints hundreds of `INFO DOORSTOP-UNREVIEWED` lines
They are notices, not problems. RVS does not use Doorstop's review feature, so Doorstop reports every item as "needs initial review". To see only real problems: `rvs validate PROJECT | grep -E "^(ERROR|WARNING)"`, or `--format json`. In the window use *Errors only*.

### `INFO RVS-STD-PLACEHOLDER ... still placeholders`
Values marked `TODO-STANDARD` or `TODO-COMPANY` in `config/` are not decided yet. RVS never invents them. Replace them when you have the standard's text or your organisation's value.

### A requirement "has no parent" but should not
Mark it *derived*: export the items table, set `derived` to `yes` for that row and import it ([how](user-manual/07-import-export-reports.md#change-many-items-in-a-spreadsheet)).

### A warning says `no links to parent document` / `RVS-TRACE-NO-CHILD`
A requirement has nothing linked below it. Allocate it to a subsystem requirement, or ignore the warning if nothing below needs it.

## Imports

### `row 1 ERROR Unknown column(s): nonsense. Use the column names of an exported file.` (**real**, exit 1)
Column names must match an export. Run `rvs export PROJECT --items -o items.csv` and use its header.

### `SYS-0001 is part of a baseline; changing it needs a reason.` (**real**)
Every change to an item in a baseline needs a reason. Add `--reason "why"` to `rvs import`, or fill in the reason box in the window.

### `1 row(s) have errors, so nothing was imported.` (**real**)
By default a file is imported only if every row is valid. Fix the rows, or add `--skip-errors` to import the valid ones.

### `rvs export: --format xlsx writes a binary file; give --output FILE.` (**real**, exit 2)
Spreadsheets, Word and PDF files cannot be printed to the screen. Add `-o file.xlsx`.

## Baselines

### `rvs: nogit is not inside a Git repository. Baselines are Git tags...` (**real**, exit 2)
The project is not under Git. Create it with `--git`, or add `--init-git` to `rvs baseline create`, or tick *Turn on version control* in the window's dialog.

### `The baseline 'PDR' already exists; baselines are immutable.` (**real**)
A baseline name can never be reused. Choose another name.

### `'bad name' is not a valid baseline name.` (**real**)
Use 1 to 64 letters, digits, `.`, `_` or `-`: no spaces, not `working`, not a Windows device name such as `CON`.

### A baseline is refused because of open change requests
Change requests with the status `open`, `in-review` or `approved` block it. Close them, or defer each with a reason (`--defer CR-0001="after PDR"`).

### `RVS-BASELINE-MODIFIED`, `RVS-BASELINE-CORRUPT`, `RVS-BASELINE-NOTAG`
Something changed a baseline's manifest or Git tag after it was made. Do not use that baseline. Restore `baselines/<name>.yaml` from the tagged commit (`git checkout rvs/baseline/<name> -- baselines/<name>.yaml`) and run `rvs baseline verify PROJECT NAME`.

## Slow or odd behaviour

### A big project is slow to open the first time
The first open builds a cache (a few seconds for 5,000 items); later opens take under a second. `--fast` on `rvs validate` skips Doorstop's own extra checks.

### I changed a file by hand and RVS shows the old text
RVS keeps a disposable cache in `.rvs-cache/`. A file changed less than two seconds ago is never cached, but if in doubt delete the `.rvs-cache/` folder: it is rebuilt.

### Two people edit the same project and one change disappears
RVS does not coordinate two people editing at the same moment: the last save of an item wins. Work on separate Git branches, or take turns, and merge with Git.

### Something else
Run the command again with `RVS_DEBUG=1` to see the full error, and look in the `crash` folder next to `settings.json`: the report holds the error type and program locations, never project content, so it is safe to send.

Next: [FAQ](faq.md) · [User manual](user-manual/README.md) · [Getting started](getting-started.md)
