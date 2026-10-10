# Expert walkthrough

Switch to expert mode with **Ctrl+Shift+M** (or **View > Mode**). The status bar shows *Expert mode*.

## Work from the keyboard

| Task | Keys |
|---|---|
| Search items | Ctrl+F, type, then Tab to move on to the status filter, the *only problems* box and the table |
| Go to an ID | Ctrl+G, type the full ID (upper or lower case) |
| New requirement | Ctrl+N: document, title, parents (IDs complete as you type) |
| New verification item | Ctrl+Shift+N: the requirements it verifies |
| Save, revert | Ctrl+S, Ctrl+R |
| Next / previous problem | F8, Shift+F8 |
| Move to the Problems panel, to the editor | F6, F4 |
| Switch tabs | Ctrl+1 … Ctrl+8 |
| Refresh | F5 |

**Tab** and **Shift+Tab** move between the widgets of the window (search box, filters, table, editor fields, buttons). Inside a table the arrow keys move between cells, and Tab leaves the table. In a multi-line field (the statement, the rationale) Tab also moves on to the next field instead of typing a tab character.

The complete list is in *Keyboard shortcuts* at the end of this guide, and in **Help > Keyboard Shortcuts**. To change a shortcut, add it under `"shortcuts"` in `settings.json` with the action ID from the table in the reference, for example `{"shortcuts": {"export": "Ctrl+Alt+E"}}`. An override that Qt cannot read, or that another action already uses, is ignored.

## Edit in the table

In expert mode, double-click a cell (or press F2) to edit it in place. Editable columns: *Title, Type, Status, Priority, Owner, Method, Level*. Enumerated columns open a drop-down with the project's vocabulary; a value outside the vocabulary is refused with a message. Every cell edit is a normal edit: it is saved immediately, checked by the rules and recorded in the item's history. If the item is in a baseline (or has a status that requires a reason), RVS asks for the reason first.

![Expert mode: a dense table that can be edited in place](images/items-expert.png)

Show more columns through **View > Columns** or by right-clicking the table header (for example *Parents*, *Statement*, *Document*, *Priority*).

## Bulk changes with a spreadsheet

For changes to many items, export the items table, edit it in Excel and import it:

```
rvs export my-project --items --format xlsx -o items.xlsx
rvs import my-project items.xlsx --dry-run
rvs import my-project items.xlsx --reason "Re-numbered after review"
```

The dry run lists every row that would be created or updated, and every row-level error; rows that would not change anything are only counted in the summary line. Nothing is written unless the whole file is clean, or you pass `--skip-errors`. In the GUI use **File > Import Items…**: the preview shows the same plan, a box for the reason, and a check box *Import the valid rows and skip rows with errors*.

The items table is also the way to set the fields that the editor does not offer: `derived`, `normative`, `level`, `header`, `ref` and `active` (write `yes` or `no`). Change the cell, import, and give a reason if the item is in a baseline.

## Scripting and automation

Every operation of the application is also available on the command line (see *Command reference*). `rvs validate` returns exit code 0 (no errors), 1 (errors, or warnings when `--strict` is given) or 3 (the project cannot be loaded), which suits a build pipeline:

```
rvs validate my-project --format json --strict
```

Commands that read a project (`validate`, `export`, `diff`) keep a speed-up cache in a folder `.rvs-cache` inside the project; it is ignored by Git and by Doorstop and can be deleted at any time.

## Large projects

Opening a project with several thousand items takes a few seconds the first time and under a second afterwards (measured with 5,000 items on a 4-core machine: about 3 to 5 s cold, under 1 s warm). RVS keeps the cache in `.rvs-cache` so later opens are quicker. The Problems panel and tables remain responsive while exports and project opening run in the background. Very large specification documents (DOCX, PDF) take a while to write; they run in the background too.

Two people changing the same project at the same time are not coordinated by RVS: the last save of an item wins. Work on separate Git branches, or take turns, and merge with Git.
