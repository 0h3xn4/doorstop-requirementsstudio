# Write and edit requirements

This page shows how to create a requirement, edit it, find it again and understand what a reason for change is.

**Contents:** [Write a new requirement](#write-a-new-requirement) · [Edit one](#edit-an-existing-requirement) · [Find items](#find-items) · [Edit in the table](#edit-in-the-table-expert-mode) · [Reasons](#when-rvs-asks-for-a-reason) · [Fields the editor cannot change](#fields-the-editor-cannot-change)

## Write a new requirement

Press **Ctrl+N** (or **Item > New Requirement…**). In guided mode a five-step wizard opens:

1. **Where does it belong?** Choose the document. Except in the top document, tick the parent requirement(s): *Next* stays off until you do, because a requirement without a parent cannot be traced.
2. **What must it say?** Write the statement (Markdown). Hints appear while you type: no "shall", vague words ("adequate"), several requirements in one sentence, acronyms missing from the glossary. They never block you.

   ![The statement step with quality hints](../guide/images/wizard-statement.png)

3. **Details.** Title, rationale, type, priority, status, owner, source, standard clause, verification method and level, typed links. Fields marked * are required.
4. **How will you show it is met?** Tick *Also create a planned verification item* to create a linked item in the verification plan.
5. **Review.** Read the summary, then **Create requirement**.

In **expert mode** (Ctrl+Shift+M) **Ctrl+N** opens a small dialog instead: document, title, parents.

## Edit an existing requirement

Select it in the table, change the fields or the statement (a Markdown preview shows next to it) and press **Ctrl+S**. **Ctrl+R** reverts; if you have unsaved edits RVS asks first. Help for the field you are in shows under the form.

## Find items

| To ... | Do this |
|---|---|
| Search by ID, title or statement | **Ctrl+F**, type |
| Jump to an ID | **Ctrl+G** |
| Filter by status | the status box above the table |
| See only items with problems | tick *Only items with problems* |
| Step through problems | **F8** / **Shift+F8** |
| Show another column | right-click the table header, or **View > Columns** |

## Edit in the table (expert mode)

Double-click a cell (or press F2). Editable columns: Title, Type, Status, Priority, Owner, Method, Level. Every edit is saved at once, checked by the rules and recorded in the item's history.

## When RVS asks for a reason

Every edit needs a **reason for change** when the item is in any baseline, or when its status is one of the configured reason-required statuses (by default `baselined`). Type it in the box beside *Save* (or answer the prompt for a table edit). It is stored with who and when in `history/`.

## Fields the editor cannot change

Doorstop's own fields `derived`, `normative`, `level`, `header`, `ref` and `active` are not offered in the editor, the table or the command line. Set them by exporting the items table, editing the column and importing it again: see [Import, export and reports](07-import-export-reports.md#change-many-items-in-a-spreadsheet). Typical case: a requirement that deliberately has no parent. Set `derived` to `yes`.

Next: [Link and trace](03-link-and-trace.md) · [Check quality](04-check-quality.md) · [Modes, themes, shortcuts](09-settings-modes-shortcuts.md)
