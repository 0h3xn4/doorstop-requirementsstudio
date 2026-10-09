# Requirements & Verification Studio

This guide is part of the application and works without a network connection. Press **F1** in the application to open it. The same text is available on the command line with `rvs guide`.

Requirements & Verification Studio (RVS) manages requirements and their verification for engineering projects, with traceability, change control and baselines. Your data is stored as plain text files in a folder, so it can be kept under Git and read without RVS.

**Nothing leaves your computer.** RVS never connects to a network: there is no update check, no telemetry and no cloud service.

## Getting started

### Install and start

Run the installer for your system (see *Installation and checks* below) and start **Requirements & Verification Studio** from the application menu, or run `rvs-studio` in a terminal.

### Your first project

Choose one of three ways:

1. **File > Open Example** creates a copy of a fictional example project and opens it. The *Small satellite* example has about 300 requirements, including a few seeded defects you can find in the Problems panel. Use this to explore.
2. **File > New Project…** (Ctrl+Alt+N) creates an empty project from a template: *Minimal* (system, subsystem, verification plan), *Small satellite* (mission, system, seven subsystems, verification plan) or *Software product* (system, software, interfaces, tests). Tick *Keep this project under Git* if you want baselines.
3. **File > Open Project…** (Ctrl+O) opens an existing RVS project folder. **File > Open Recent** lists the last eight.

The same from the command line: `rvs init my-project --name "My project" --template satellite --git`.

### The window

![The Items tab in guided mode: documents on the left, items in the middle, the editor on the right, problems at the bottom](images/items-guided.png)

- **Documents** (left): the document tree. Click a document to filter the item table; click an item to open it.
- **Items** tab: the table of items on the left, the editor on the right.
- **Problems** (bottom): everything the project's quality rules and link checks found. Double-click a row to jump to the item.
- **Impact** (right): which items are affected if the selected item changes.
- Tabs for **Traceability**, **VCM** (verification control matrix), **Coverage**, **Graph**, **Changes**, **Baselines** and **Diff**.

### Guided and expert mode

RVS starts in **guided mode**: a step-by-step wizard for new requirements, an explanation of the field you are editing and a roomy table. When you know the tool, switch to **expert mode** with **View > Mode** or **Ctrl+Shift+M**: a dense table you can edit directly, and the quick "new item" dialog. Your choice is remembered.

| | Guided | Expert |
|---|---|---|
| New requirement | Wizard with live quality hints | Small dialog (document, title, parents) |
| Field help | Shown under every field | Tooltips only |
| Item table | Read-only, comfortable rows | Dense rows, edit cells in place |

Both modes use the same data and the same rules; nothing is hidden in guided mode.

### Light and dark theme

**View > Theme** switches between a light theme, a dark theme and *Follow the system*. The choice is remembered.

![The dark theme](images/items-dark.png)

### Help from the application

- **F1** opens this guide. **Ctrl+/** lists all keyboard shortcuts.
- Hover over any field in the editor to read what it means.
- Problems always say what is wrong *and* how to fix it.

## Installation and checks

### Installing

On Linux, unpack the release and run `./install.sh` (it installs for your user only and needs no administrator rights). On Windows, run the installer, which also installs for your user. `./uninstall.sh` removes the program and leaves your projects and settings untouched.

### Checking an installation

`rvs selftest` checks the installed program: bundled fonts and configuration, a sample project, an export in every format (ReqIF included), a baseline in a scratch Git repository, and that the offline guard is active. It prints one line per check and exits with 0 when everything is fine. `rvs selftest --manifest <folder>` also verifies every installed file against `MANIFEST.sha256`, which shows whether files were damaged or altered after installation.

### Where RVS keeps its own settings

Preferences (mode, recent projects, shortcut overrides, window size) are in a small `settings.json` in your user configuration folder (`~/.config/rvs` on Linux, `%APPDATA%\rvs` on Windows). Set `RVS_CONFIG_DIR` to use another folder. This file never contains project content.

### If something unexpected happens

RVS shows a plain message and writes a short report to the `crash` folder next to `settings.json`. The report contains the error type and program locations only, never requirement text, so it is safe to send to the maintainers. Your saved project files are not affected.
