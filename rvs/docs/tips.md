# Tips

This page collects shortcuts, power-user workflows and notes on exchanging data with other tools. Everything here is something RVS really does; nothing is assumed about tools it has not been tested with.

**Contents:** [Work faster](#work-faster) · [Workflows that save time](#workflows-that-save-time) · [Working with other tools](#working-with-other-tools) · [Keep it healthy](#keep-it-healthy)

## Work faster

- **Stay on the keyboard.** Ctrl+F (search), Ctrl+G (go to an ID), F8 / Shift+F8 (next / previous problem), F4 (into the editor), F6 (to the Problems panel), Ctrl+1 … Ctrl+8 (tabs), Ctrl+S (save). **Ctrl+/** lists them all; you can [change them](user-manual/09-settings-modes-shortcuts.md#change-a-shortcut).
- **Switch to expert mode** (Ctrl+Shift+M) once you know the tool: a dense table you can edit in place, and a quick new-item dialog.
- **Fix problems in a loop:** tick *Only items with problems*, press F8, fix, Ctrl+S, F8 again.
- **Hide the noise.** The Problems panel's *Errors only* box, or `rvs validate PROJECT | grep -E "^(ERROR|WARNING)"`, hides the `INFO DOORSTOP-UNREVIEWED` notices.
- **Show only the columns you need:** right-click the table header.
- **Use the dark theme** (View > Theme) in a dim room; it follows the system if you choose *Follow the system*.

## Workflows that save time

### Rename or re-prioritise many items
Export the table, edit it in a spreadsheet, import it with a dry run first: [steps](user-manual/07-import-export-reports.md#change-many-items-in-a-spreadsheet). A table with only the columns `id` and `priority` changes only priorities.

### Check a project in your build pipeline
`rvs validate PROJECT --format json --strict` fails the job on errors or warnings. Keep the JSON as an artefact.

### Reproducible reports
Set `SOURCE_DATE_EPOCH` to the commit time so the same commit always gives byte-identical files:

```
SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) rvs export PROJECT --vcm -o vcm.xlsx
```

### A review checklist before a baseline
1. `rvs validate PROJECT --strict` shows no errors or warnings that matter.
2. Open change requests are closed or deferred.
3. The VCM has no *unverified* rows you did not expect (`rvs export PROJECT --vcm --only-gaps`).
4. `rvs baseline create PROJECT SRR -m "System requirements review"`.
5. `rvs baseline verify PROJECT SRR`.
6. Share the tag: `git push origin refs/tags/rvs/baseline/SRR` (RVS never pushes by itself).

### See what changed since the last review
`rvs diff PROJECT SRR working --format html -o changes-since-SRR.html`.

### Report as it was
`rvs export PROJECT --vcm --baseline SRR -o vcm-srr.xlsx` gives the VCM of the baseline, whatever the project looks like now.

### Branch per change request
Because every item is its own text file, a Git branch per change request keeps changes separate and merges cleanly. Name the branch after the CR (`cr-0001-battery-margin`) and tick *Attribute my edits to this change request* while you work.

## Working with other tools

RVS can exchange data in these formats: **CSV and XLSX** (the items table), **ReqIF**, **DOCX, PDF and HTML** (reports and specifications), and **JSON** (findings and matrices).

### Spreadsheets (Excel, LibreOffice)
`rvs export PROJECT --items -o items.xlsx`, edit, `rvs import PROJECT items.xlsx --dry-run`. The `Provenance` sheet of an exported workbook is ignored on import. Text starting with `=`, `+`, `-` or `@` is protected so a spreadsheet will not run it as a formula.

### Other requirements tools (ReqIF)
`rvs export PROJECT --reqif -o project.reqif` and `rvs import PROJECT file.reqif --dry-run`. Relations for parent links and for `satisfies`, `verifies`, `refines` and `conflicts-with` are carried. Files from other tools are matched by attribute name; use `--map "Their name=column"` for the rest. RVS has **not** been tested against a specific tool, and the files could not be validated against the official schema offline: try `--dry-run` first and tell the maintainers what a tool rejects.

### Any tool that can write a table
If a tool can export CSV or XLSX, rename its columns to RVS's column names (the header of `rvs export PROJECT --items`) and import with `--dry-run`. Columns RVS does not know are refused with a clear message, so nothing is imported by accident. Items need a `document` (or an `id` that names it) and, for requirements below the top document, `parents` (without them the *has-parent* rule reports the item).

### Other tools in your toolbox
This documentation does not describe a direct link with other engineering tools (for example mission, harness, budget, AIT-logbook or interface-control tools): RVS has no built-in connection to them. If they can read or write CSV, XLSX or ReqIF, the routes above apply. If you want a specific exchange, describe the file the other tool writes and a mapping can be documented, or built.

### Git hosting and CI
Projects are plain text, so any Git host works. RVS only ever uses local Git; pushing and pulling is yours.

## Keep it healthy

- Run `rvs validate PROJECT` after any hand edit; errors name the file and line.
- Do not edit `baselines/`, `history/` or `changes/` by hand.
- `.rvs-cache/` is safe to delete.
- `rvs selftest` checks an installation in a few seconds.

Next: [FAQ](faq.md) · [User manual](user-manual/README.md) · [Developer docs](developer/README.md)
