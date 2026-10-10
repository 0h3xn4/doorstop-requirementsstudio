# Documentation index

This page is the map of all the documentation in this repository: Requirements & Verification Studio (RVS) first, and the documentation of the upstream Doorstop project it is built on, listed separately at the end.

New here? Read [Getting started](getting-started.md), then the [user manual](user-manual/README.md).

**Contents:** [Getting started](#getting-started) · [User guides](#user-guides) · [Help](#help) · [Reference](#reference) · [Examples](#examples) · [Developer docs](#developer-docs) · [History](#history) · [Upstream Doorstop documentation](#upstream-doorstop-documentation)

## Getting started

| Page | What it is |
|---|---|
| [Getting started](getting-started.md) | Install, open the first example, build a small project from the command line |
| [Glossary](glossary.md) | Every term and acronym used in these pages |
| [Examples](../examples/README.md) | The ready-made projects, what each shows, expected output |

## User guides

| Page | What it is |
|---|---|
| [User manual](user-manual/README.md) | Task-by-task pages ("How do I ...?"); start here |
| [1. Create or open a project](user-manual/01-create-a-project.md) | Templates, examples, opening, adding a document |
| [2. Write and edit requirements](user-manual/02-write-and-edit-requirements.md) | The wizard, the editor, search, reasons |
| [3. Link and trace](user-manual/03-link-and-trace.md) | Links, matrices, graph, impact, suspect links |
| [4. Check quality](user-manual/04-check-quality.md) | Problems, rules, how to fix the common findings |
| [5. Verification](user-manual/05-verification.md) | Verification items, results, the VCM, coverage |
| [6. Change control](user-manual/06-change-control.md) | Change requests, baselines, comparing states |
| [7. Import, export and reports](user-manual/07-import-export-reports.md) | Spreadsheets, specification documents, ReqIF |
| [8. The command line](user-manual/08-command-line.md) | Commands, exit codes, build pipelines |
| [9. Modes, themes, shortcuts, settings](user-manual/09-settings-modes-shortcuts.md) | Guided and expert mode, keys, `settings.json` |
| [10. Project files](user-manual/10-project-files.md) | What is in a project folder and what to edit |
| [Tips](tips.md) | Shortcuts, workflows, exchanging data with other tools |
| [The built-in user guide](guide/01-getting-started.md) | The full reference, seven chapters. It is the text the program shows on **F1** (`rvs guide`): [1 Getting started](guide/01-getting-started.md) · [2 Guided walkthrough](guide/02-guided-walkthrough.md) · [3 Expert walkthrough](guide/03-expert-walkthrough.md) · [4 Change control](guide/04-change-control.md) · [5 Import and export](guide/05-import-export.md) · [6 Command reference](guide/06-command-reference.md) · [7 Reference](guide/07-reference.md) |

## Help

| Page | What it is |
|---|---|
| [Troubleshooting](troubleshooting.md) | Error messages and their fixes |
| [FAQ](faq.md) | Short answers to common questions |

## Reference

| Page | What it is |
|---|---|
| [Specification](SPEC.md) | What RVS was asked to do |
| [Architecture](ARCHITECTURE.md) | How the program is built |
| [Decisions](DECISIONS.md) | Every design decision and who decided it |
| [Deviations](DEVIATIONS.md) | Where the result differs from the specification, and why |
| [Plan](PLAN.md) | The milestones and what is still open |
| [Finding codes and rules](guide/07-reference.md#finding-codes) | Every `RVS-...` code |

## Examples

[The examples README](../examples/README.md) explains `minimal10` (10 items), `satellite300` (339 items, seven planted defects) and the generated 5,000-item project.

## Developer docs

| Page | What it is |
|---|---|
| [Contributing](../CONTRIBUTING.md) | How to propose a change |
| [Developer guide](developer/README.md) | Set-up, tests, lint, documentation, release, syncing with upstream |
| [Release checklist](RELEASE.md) | Building and checking a release |
| [Engineering audit](AUDIT.md) | The audit of the code, with what was fixed and what remains |
| [Documentation audit](DOCS_AUDIT.md) | The audit of these documents |
| [Changelog](../CHANGELOG.md) | What changed in each version |
| [`CLAUDE.md`](../CLAUDE.md) | Commands and rules for the AI assistant that helps maintain the code |

## History

Short notes written when each milestone was finished. They are snapshots: numbers and commands in them were true then and are not updated.

[M0](demo/M0.md) · [M1](demo/M1.md) · [M2](demo/M2.md) · [M3](demo/M3.md) · [M4](demo/M4.md) · [M5](demo/M5.md) · [M6](demo/M6.md) · [After version 1](demo/post-v1.md)

## Upstream Doorstop documentation

These belong to the upstream project, [doorstop-dev/doorstop](https://github.com/doorstop-dev/doorstop), and describe Doorstop itself, not RVS. They are in the `docs/` folder at the repository root and are unchanged. You do not need these pages to use RVS.

| Page | What it is |
|---|---|
| [The original Doorstop README](../../docs/upstream/README.upstream.md) | Overview, install and usage of Doorstop |
| [Doorstop installation](../../docs/getting-started/installation.md) · [setup](../../docs/getting-started/setup.md) · [quickstart](../../docs/getting-started/quickstart.md) | Getting started with Doorstop |
| [Creating documents](../../docs/cli/creation.md) · [reordering](../../docs/cli/reordering.md) · [validating](../../docs/cli/validation.md) · [publishing](../../docs/cli/publishing.md) · [importing and exporting](../../docs/cli/interchange.md) | The `doorstop` command line |
| [Desktop client](../../docs/gui/overview.md) · [web server](../../docs/web.md) · [scripting API](../../docs/api/scripting.md) | Other Doorstop interfaces |
| [Tree](../../docs/reference/tree.md) · [Document](../../docs/reference/document.md) · [Item](../../docs/reference/item.md) | Doorstop reference |
| [Third-party projects](../../docs/examples.md) | Projects that use Doorstop |
| [Doorstop contributing](../../CONTRIBUTING.md) (upstream's file) · [Doorstop changelog](../../CHANGELOG.md) · [Doorstop licence](../../LICENSE.md) | About the upstream project |

Next: [Getting started](getting-started.md) · [User manual](user-manual/README.md) · [Developer guide](developer/README.md)
