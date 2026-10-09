# Expert walkthrough

Switch to expert mode with **Ctrl+Shift+M** (or **View > Mode**). The status bar shows *Expert mode*.

## Work from the keyboard

| Task | Keys |
|---|---|
| Search items | Ctrl+F, type, Down to the table |
| Go to an ID | Ctrl+G, type the full ID (upper or lower case) |
| New requirement | Ctrl+N: document, title, parents (IDs complete as you type) |
| New verification item | Ctrl+Shift+N: the requirements it verifies |
| Save, revert | Ctrl+S, Ctrl+R |
| Next / previous problem | F8, Shift+F8 |
| Switch tabs | Ctrl+1 … Ctrl+8 |
| Refresh | F5 |

The complete list is in *Keyboard shortcuts* at the end of this guide, and in **Help > Keyboard Shortcuts**. To change a shortcut, add it under `"shortcuts"` in `settings.json`, for example `{"shortcuts": {"export": "Ctrl+Alt+E"}}`.

## Edit in the table

In expert mode, double-click a cell (or press F2) to edit it in place. Editable columns: *Title, Type, Status, Priority, Owner, Method, Level*. Enumerated columns open a drop-down with the project's vocabulary; a value outside the vocabulary is refused with a message. Every cell edit is a normal edit: it is saved immediately, checked by the rules and recorded in the item's history. If the item is baselined, RVS asks for the reason first.

Show more columns through **View > Columns** or by right-clicking the table header (for example *Parents*, *Statement*, *Document*, *Priority*).

## Bulk changes with a spreadsheet

For changes to many items, export the items table, edit it in Excel and import it:

```
rvs export my-project --items --format xlsx -o items.xlsx
rvs import my-project items.xlsx --dry-run
rvs import my-project items.xlsx --reason "Re-numbered after review"
```

The dry run lists, per row, whether an item would be created, updated or left unchanged, and every row-level error. Nothing is written unless the whole file is clean, or you pass `--skip-errors`. In the GUI use **File > Import Items…**.

## Scripting and automation

Every operation of the application is also available on the command line (see *Command reference*). `rvs validate` returns exit code 0 (no errors), 1 (errors, or warnings when `--strict` is given) or 3 (the project cannot be loaded), which suits a build pipeline:

```
rvs validate my-project --format json --strict
```

## Large projects

Opening a project with several thousand items takes a few seconds; RVS keeps a cache in `.rvs-cache` (it is ignored by Git and by Doorstop) so later opens are quicker. The Problems panel and tables remain responsive while exports and project opening run in the background.
