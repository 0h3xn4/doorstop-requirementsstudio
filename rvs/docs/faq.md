# FAQ

This page answers the questions newcomers ask most. If your question is about an error message, see [Troubleshooting](troubleshooting.md).

**Contents:** [About the tool](#about-the-tool) · [Your data](#your-data) · [Working with it](#working-with-it) · [Standards and other tools](#standards-and-other-tools) · [The repository](#the-repository)

## About the tool

### What is Requirements & Verification Studio?
An offline tool for writing requirements, linking them, saying how each is verified, controlling changes and producing reports (matrices, specification documents). It is a desktop application (`rvs-studio`) and a command line (`rvs`). It is aimed at engineering projects, such as spacecraft, that need traceability from mission requirements down to verification evidence.

### How is it different from Doorstop?
[Doorstop](https://doorstop.dev) stores requirements as text files and links them. RVS is built on Doorstop and adds a desktop application, quality rules, verification tracking, matrices, change requests, baselines, reports and import/export. A project is still a valid Doorstop project, so ordinary tools can read it.

### Which systems does it run on?
Python 3.11, 3.12 or 3.13 on Linux and Windows (tested on every change) and, untested, on macOS. See [Getting started](getting-started.md#what-you-need).

### Do I need to install Git?
No. RVS has its own built-in Git for local work. You need your own Git only to share a project or back it up to a server.

### Is it free? What is the licence?
The `rvs/` folder is marked *proprietary, internal use only* (see `rvs/LICENSE`). The rest of the repository is Doorstop, under its own licence (`LICENSE.md` at the repository root). The libraries RVS uses are licensed permissively or under the LGPL; the release build lists them in `THIRD-PARTY-LICENSES.txt`.

## Your data

### Does RVS use the network?
No. There is no update check, no telemetry and no cloud service, and a test checks that no network library is even loaded. (`pip install` uses the network once to download the libraries, but that is pip, not RVS.)

### Where is my data?
In a folder of plain text files (YAML). See [Project files](user-manual/10-project-files.md). You can read it without RVS, search it, and keep it under Git.

### How do I back it up or share it?
It is a folder: copy it, or push it with your normal Git workflow (RVS never contacts a server itself).

### Can two people work on one project?
Not at the same moment: RVS does not coordinate simultaneous edits, and the last save of an item wins. Work on separate Git branches, or take turns, and merge with Git. Items are separate files, so merges are usually clean.

## Working with it

### How do I add a requirement from the command line?
There is no `add` command. Use the window (**Ctrl+N**), or write rows in a CSV and run `rvs import` ([example](getting-started.md#your-first-project-from-the-command-line)).

### Why can't I edit `derived`, `level`, `normative`, `header`, `ref` or `active`?
They are Doorstop's own fields and the editor does not offer them. Change them by exporting the items table, editing the column and importing it again ([how](user-manual/07-import-export-reports.md#change-many-items-in-a-spreadsheet)).

### Can I delete an item?
Not from RVS. Set its status to `obsolete`, or mark it inactive by import (`active` = `no`). The file and its history stay in the project, so traceability and baselines remain intact.

### Why does RVS ask for a reason when I save?
The item is in a baseline (or its status needs a reason). Every change to a baselined item is recorded with who, when and why.

### How do I change the allowed values (status, priority, type, ...)?
Edit `config/vocab.yaml` in the project. Other settings (rules, fields, glossary, change-request statuses) are in the other `config/` files; see [Project files](user-manual/10-project-files.md#configuration-files-in-config).

### How do I add my own field to every requirement?
Add an attribute to `config/templates.yaml`. The editor, the wizard, imports and exports pick it up.

### What does `TODO-COMPANY` / `TODO-STANDARD` mean?
A value that only your organisation, or a standard, can supply. RVS reports it as information until you replace it and never invents one.

### How do I update RVS?
`git pull`, then `pip install ./rvs` again in your virtual environment. See the [changelog](../CHANGELOG.md).

## Standards and other tools

### Does it follow ECSS?
It is designed for ECSS-style work (requirement wording, verification control matrix, configuration management) but it does **not** contain the text of the standards. Anything that depends on a standard, such as the VCM column layout, is a clearly marked placeholder (`TODO-STANDARD`) until you supply the text.

### Can I exchange data with DOORS, Polarion, Jama or Excel?
Excel and any spreadsheet: yes, through CSV and XLSX. Other requirements tools: through ReqIF import and export. RVS has not been tested against a specific third-party tool. See [Tips](tips.md#working-with-other-tools).

## The repository

### Why does the repository contain so much that is not RVS?
Because it is a copy (a *fork*) of the Doorstop project. RVS lives in the `rvs/` folder. The README at the top explains which part is which.

### Which folder do I install?
`pip install ./rvs`: the `rvs` folder, not the repository root.

Next: [Troubleshooting](troubleshooting.md) · [Glossary](glossary.md) · [User manual](user-manual/README.md)
