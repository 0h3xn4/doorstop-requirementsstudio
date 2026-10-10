# Examples

This page lists the ready-made projects that come with Requirements & Verification Studio (RVS), says what each one shows, and gives the commands to try them together with the output you should get.

**Contents:** [The examples at a glance](#the-examples-at-a-glance) · [minimal10](#minimal10) · [satellite300](#satellite300) · [Examples inside the application](#examples-inside-the-application) · [A big project for speed tests](#a-big-project-for-speed-tests)

All three projects are **fictional**: invented requirements for an invented spacecraft.

## The examples at a glance

| Example | Items | What it shows | Where |
|---|---|---|---|
| `minimal10` | 10 | The smallest complete project: system requirements, one subsystem, a verification plan, links between them. A good first thing to open. | `examples/minimal10` |
| `satellite300` | 339 | A larger project with seven planted defects, matrices, a graph and many links. Use it to learn how problems are shown. | `examples/satellite300` |
| (stress, generated) | 5,000 | Speed testing. Not stored in the repository; you generate it. | `scripts/gen_stress.py` |

**Work on a copy.** The repository's tests compare these two folders with what the generators write, so changing them in place would make tests fail. Copy first:

```
cp -r examples/minimal10 /tmp/minimal10        # Windows: xcopy /E /I examples\minimal10 %TEMP%\minimal10
```

Reading a project creates a harmless `.rvs-cache/` folder in it (ignored by Git). The commands below assume you are in the `rvs/` folder of the repository (from the repository root: `cd rvs`) with RVS installed ([Getting started](../docs/getting-started.md)).

## minimal10

Ten items: three system requirements (`SYS-0001` to `SYS-0003`) and a heading (`SYS-0004`), three electrical-power requirements (`EPS-0001` to `EPS-0003`) linked to them, and three verification items (`VER-0001` to `VER-0003`) that verify the EPS requirements.

**Check it.**

```
rvs validate examples/minimal10
```

Expected: the last line is `0 errors, 0 warnings, 11 info` and the exit code is 0. The eleven info lines are notices (ten `DOORSTOP-UNREVIEWED` and one `RVS-STD-PLACEHOLDER`), not problems.

**The verification control matrix.**

```
rvs export examples/minimal10 --vcm
```

```
Requirement,Title,Method,Level,Verification item,Status,Evidence
SYS-0001,Payload power,analysis,system,,not verified,
SYS-0002,Eclipse operation,test,system,,not verified,
SYS-0003,Mass budget,inspection,system,,not verified,
EPS-0001,Battery capacity,analysis,subsystem,VER-0001,planned,
EPS-0002,Array output,test,subsystem,VER-0002,planned,
EPS-0003,EPS mass,inspection,subsystem,VER-0003,planned,
```

Above the table a few `#` lines name the project, the baseline, the date and time, the user and the tool; those lines are yours. The system requirements are *not verified* because nothing verifies them directly; the subsystem requirements are *planned*.

**Traceability, coverage and impact.**

```
rvs export examples/minimal10 --trace SYS:EPS
rvs export examples/minimal10 --coverage
rvs export examples/minimal10 --impact SYS-0002
```

```
Source,Title,Linked items,Link types,Gap
SYS-0001,Payload power,EPS-0002,parent,
SYS-0002,Eclipse operation,EPS-0001,parent,
SYS-0003,Mass budget,EPS-0003,parent,
```

and, for the impact of changing `SYS-0002`:

```
Item,Depth,Via,Title
EPS-0001,1,parent,Battery capacity
VER-0001,2,verifies,Eclipse power analysis
```

That says: if `SYS-0002` changes, `EPS-0001` (one link away) and `VER-0001` (two links away) are affected.

**A specification document and a spreadsheet.**

```
rvs export examples/minimal10 --spec -o spec.html
rvs export examples/minimal10 --vcm -o vcm.xlsx
```

Open `spec.html` in a browser, `vcm.xlsx` in a spreadsheet.

## satellite300

A small satellite: mission requirements (`MIS`), system requirements (`SYS`), seven subsystems (`EPS`, `OBC`, `AOCS`, `TTC`, `STR`, `THM`, `PLD`) and a verification plan (`VER`): 339 items in all.

```
rvs validate examples/satellite300 | grep -E "^(ERROR|WARNING)"
```

Without the filter there are 340 `INFO` lines of notices that hide the interesting ones. The summary line is `3 errors, 15 warnings, 340 info` and the exit code is 1.

**The seven planted defects** (each one is something the checks are meant to find):

| Item | Finding | What is wrong |
|---|---|---|
| `EPS-0001` | `RVS-RULE-SHALL-PRESENT` (error) | no "shall" |
| `THM-0001` | `RVS-RULE-VERIFIED-WHEN-APPROVED` (error) | approved, but nothing verifies it |
| `TTC-0001` | `RVS-RULE-HAS-PARENT` (error) | no parent requirement |
| `AOCS-0001` | `RVS-RULE-SINGLE-STATEMENT` (warning) | two requirements in one statement |
| `OBC-0001` | `RVS-RULE-VAGUE-WORDS` (warning) | uses "adequate" |
| `PLD-0001` | `RVS-RULE-UNDEFINED-ACRONYM` (warning) | the acronym LIDAR is not in the glossary |
| `STR-0001` | `RVS-RULE-VERIFY-METHOD-SET` (warning) | no verification method |

The other warnings are ten `RVS-TRACE-NO-CHILD` (`SYS-0041` to `SYS-0050`, which no subsystem takes) and one Doorstop warning for `TTC-0001`, whose missing parent link also shows here.

**Open it in the application**, to see how it looks:

```
rvs-studio
```

then **File > Open Project…** and choose a copy of `satellite300`. The bar at the bottom reads *339 items · 3 errors · 14 warnings* (one fewer warning than the command line, because the window does not run Doorstop's own extra checks until you choose **Project > Run Full Doorstop Validation**). Click a row in the **Problems** panel to jump to the item.

![The Problems panel on satellite300](../docs/images/problems.png)

Try the **Traceability**, **VCM**, **Coverage** and **Graph** tabs. Fix `EPS-0001` by rewriting it with "shall" and press Ctrl+S: the error disappears.

## Examples inside the application

**File > Open Example…** creates a fresh copy of the *Minimal* or the *Small satellite* example in a folder you choose (a sub-folder named `rvs-example-minimal` or `rvs-example-satellite`), so you never need to copy by hand. **File > New Project…** and `rvs init` also offer a *Software product* template: an empty project with system requirements, software requirements, interfaces and tests.

## A big project for speed tests

```
python scripts/gen_stress.py /tmp/stress
rvs validate /tmp/stress --fast
```

creates 5,000 items (it takes about a minute) and checks them. See the performance notes in the [release checklist](../docs/RELEASE.md).

## How the examples are made

They are written by programs (`scripts/gen_examples.py`), so they are identical every time. A test checks that the committed folders match what the programs write. If you change the generators, regenerate with `python scripts/gen_examples.py` and review the difference.

Next: [User manual](../docs/user-manual/README.md) · [Troubleshooting](../docs/troubleshooting.md) · [Getting started](../docs/getting-started.md)
