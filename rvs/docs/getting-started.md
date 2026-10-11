# Getting started

This page takes you from nothing to your first working result: install Requirements & Verification Studio (RVS), open an example project, and then build a tiny project of your own from the command line.

**Contents:** [What you need](#what-you-need) · [Install](#install) · [First run: the application](#first-run-the-application) · [Your first project from the command line](#your-first-project-from-the-command-line) · [What next](#what-next)

New words (ECSS, VCM, baseline, ...) are explained in the [glossary](glossary.md).

## What you need

| You need | Notes |
|---|---|
| **Python 3.11, 3.12 or 3.13** | Python 3.14 and older than 3.11 do not work. Check with `python3 --version`. |
| **pip** | Comes with Python. |
| **A network, once** | Only for `pip install`, to download the libraries. RVS itself never uses the network. To install without a network see [Troubleshooting](troubleshooting.md#pip-install-cannot-reach-the-network). |
| **Git** (optional) | You do **not** need it installed: RVS has a built-in Git for local use. You only need your own Git if you want to share or back up a project. |
| **Linux only:** a few system libraries | The window needs them. On Debian or Ubuntu: `sudo apt-get install libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1 libxcb-util1`. The `rvs` command line does not need them. |

**Which systems are tested?** Linux and Windows run the test suite on every change (Python 3.11 to 3.13). macOS has **not** been tested; it should work because the libraries support it, but you may meet problems. The prebuilt installers (`install.sh`, `install.ps1`) are described in the [release notes for maintainers](RELEASE.md); the Windows installer has never been run on Windows. The `pip` route below is the one that was tested.

## Install

Run these in a terminal. Replace `python3` with `py` on Windows if `python3` is not found.

```
git clone https://github.com/0h3xn4/doorstop-requirementsstudio.git
cd doorstop-requirementsstudio
python3 -m venv .venv
source .venv/bin/activate
pip install ./rvs
rvs --version
```

On **Windows (PowerShell)** the fourth line is `.venv\Scripts\Activate.ps1`. On **Windows (cmd)** it is `.venv\Scripts\activate.bat`.

You should see:

```
rvs 0.1.0 (doorstop 3.2)
```

> **Install the `rvs` folder, not the repository root.** This repository is a copy (a *fork*) of the Doorstop project, so its root folder holds Doorstop itself. `pip install ./rvs` installs RVS, which brings the Doorstop version it needs with it.

Check that everything works:

```
rvs selftest
```

It prints one line per check and ends with `All checks passed.`. It takes a few seconds.

## First run: the application

Start the window:

```
rvs-studio
```

1. Choose **File > Open Example…**, pick a folder, and choose *Small satellite*. RVS creates a fictional project in a new sub-folder there (`rvs-example-satellite`) and opens it. (It is not under Git yet; that matters only when you make a baseline.)
2. You see the **Items** tab: the document tree on the left, the table of requirements in the middle, the editor on the right and the **Problems** panel at the bottom.

   ![The Items tab with the Problems panel](images/problems.png)

   The bottom bar should read about *339 items · 3 errors · 14 warnings*. The example has seven defects planted on purpose so you can see how problems are shown.
3. Click a row in the **Problems** panel (for example the *error* about `EPS-0001`). The **How to fix** column tells you what to do: *Rewrite it as 'The <system> shall <do something>'*.
4. Open the other tabs: **Traceability** (which requirements are linked to which), **VCM** (how each requirement is verified), **Coverage**, **Graph**.

   ![The traceability tab](images/traceability.png)

5. Press **F1** for the built-in user guide (it works offline).

Next, try writing a requirement: press **Ctrl+N**. The wizard asks where it belongs, what it says, the details, and how you will verify it. [How to write and edit requirements](user-manual/02-write-and-edit-requirements.md) walks through it.

## Your first project from the command line

Everything the window does is also a command. This example builds a three-requirement project, checks it, makes a verification matrix and freezes a baseline. It takes about two minutes. You need the install from above (the virtual environment active).

**1. Create the project.** `--git` puts it under version control (needed for baselines).

```
rvs init demo --name "Demo satellite" --template minimal --git
```

```
Project 'Demo satellite' created in demo from the minimal template.
```

**2. Add requirements.** RVS has no `add` command; you add items in the window, or by importing a table. Save this as `items.csv`:

```
id,document,title,text,type,status,verify_method,verify_level,parents
SYS-0001,SYS,Payload power,The spacecraft shall provide electrical power to all payloads.,functional,draft,analysis,system,
SYS-0002,SYS,Eclipse operation,The spacecraft shall operate through an eclipse of up to 35 minutes.,performance,draft,test,system,
SUB-0001,SUB,Battery capacity,The battery shall store at least 120 Wh.,design,draft,analysis,subsystem,SYS-0002
```

Try it without writing anything (a *dry run*), then do it for real:

```
rvs import demo items.csv --dry-run
rvs import demo items.csv --reason "first import"
```

The dry run ends with `Dry run: 3 to create, 0 to update, 0 unchanged, 0 errors.` and the real import with `3 created, 0 updated, 0 unchanged, 0 errors skipped.`

**3. Check the project.**

```
rvs validate demo
```

The last line should read `0 errors, 1 warning, 5 info`. The warning is `RVS-TRACE-NO-CHILD SYS-0001`: nothing below `SYS-0001` yet. Lines starting `INFO` are notices, not problems (see [Troubleshooting](troubleshooting.md#rvs-validate-prints-hundreds-of-info-doorstop-unreviewed-lines)).

**4. Add a verification item.** Save `ver.csv`:

```
id,document,title,text,verify_method,verify_level,v_status,link_verifies,proc_id
VER-0001,VER,Battery capacity test,Measure the battery capacity at 20 degrees C.,analysis,subsystem,planned,SUB-0001,TP-BATT-01
```

```
rvs import demo ver.csv --reason "add verification"
```

**5. Make the verification control matrix (VCM).**

```
rvs export demo --vcm
```

```
Requirement,Title,Method,Level,Verification item,Status,Evidence
SYS-0001,Payload power,analysis,system,,not verified,
SYS-0002,Eclipse operation,test,system,,not verified,
SUB-0001,Battery capacity,analysis,subsystem,VER-0001,planned,
```

(Above it come a few `#` lines naming the project, the baseline, the date and the tool.) Write a spreadsheet instead with `-o vcm.xlsx`: the file type decides the format.

**6. Freeze a baseline.**

```
rvs baseline create demo PDR -m "Preliminary design review"
rvs baseline list demo
```

```
Baseline PDR created: 4 items, tag rvs/baseline/PDR, commit 7d54da601a.
PDR                  2026-10-10T15:51:17  root             4 items  Preliminary design review
```

(The commit ID and time are yours.) From now on every change to these four items needs a reason, and `rvs diff demo PDR working` shows what changed since.

**7. Open it in the window.** Run `rvs-studio`, choose **File > Open Project…** and pick the `demo` folder.

## What next

- Learn the tasks one by one: the [user manual](user-manual/README.md).
- Explore the ready-made projects: [examples](../examples/README.md).
- Something went wrong? [Troubleshooting](troubleshooting.md) and the [FAQ](faq.md).

Next: [User manual](user-manual/README.md) · [Examples](../examples/README.md) · [Glossary](glossary.md)
