# Guided walkthrough

This walkthrough uses the *Small satellite* example (**File > Open Example**). Everything in it is fictional.

## 1. Find your way around

Click **EPS** in the Documents panel. The table shows the electrical power subsystem requirements. Select one: the editor on the right shows its statement, its fields (one help line under the form explains the field you are in) and **Problems with this item**.

Use **Ctrl+F** to search by ID, title or statement, the status box to filter, and *Only items with problems* to see what needs attention. **Ctrl+G** jumps to an ID. **F8** and **Shift+F8** step through the items that have problems. The **Tab** key moves from one control to the next (search, status box, check box, table, editor fields); **F4** moves the focus straight into the editor.

## 2. Write a new requirement

Press **Ctrl+N** (or **Item > New Requirement…**). The wizard has five steps:

1. **Where does it belong?** Pick the document. For every document except the top-level one, tick the parent requirement(s) it derives from; *Next* stays disabled until you do, because a requirement without a parent cannot be traced.
2. **What must it say?** Type the statement. Below it, quality hints appear while you type: a missing "shall", vague words such as "adequate", several requirements in one sentence, acronyms that are not in the glossary. The hints never block you. Undefined acronyms are underlined in red.
3. **Details.** Every field of the document template, with help text: title, rationale, type, priority, status, owner, source, standard clause, verification method and level, and the typed links. Fields marked * are required.
4. **How will you show it is met?** Tick *Also create a planned verification item* to create a linked verification item in the verification plan, using the method and level from the previous step.
5. **Review.** A summary of what will be created and everything the rules found. Click *Finish* to create the requirement; you can fix remaining hints later in the editor.

![The wizard's first step: choose the document and tick the parent requirement](images/wizard-where.png)

![The statement step: quality hints appear while you type](images/wizard-statement.png)

The new item is selected in the editor and a green message names the IDs that were created.

## 3. Edit an existing requirement

Select an item, change fields or the statement (the preview shows the formatted Markdown), and press **Ctrl+S**. **Ctrl+R** reverts.

- *Parents* completes item IDs from the parent document as you type.
- *Owner*, *Source* and similar fields complete from values already used in the project.
- A **reason for change** is required for every item that is in any baseline, and for every item whose status is one of the configured *reason-required* statuses (by default `baselined`). Type it in the box next to *Save*. The reason is stored in the item's history.
- **Clear suspect links** is always visible; it is enabled when a parent changed after this item was last reviewed. Review the parent first, then accept it.

**What the editor cannot change.** The editor, the table and the command line edit the *template fields* (title, statement, type, status, priority, owner, verification fields, typed links and parents). Some fields of the underlying Doorstop item are **not** editable there: `derived`, `normative`, `level`, `header`, `ref` and `active`. They can only be set by importing a table (CSV or XLSX), see *Bulk changes with a spreadsheet*. For example, when a problem says an item "has no parent requirement" and you decide it has none by design, export the items table, set the `derived` column of that row to `yes`, and import it again.

## 4. Fix problems

Open the Problems panel. Each row has a code, the item, a message and **How to fix**. Examples: `RVS-RULE-SHALL-PRESENT` (add "shall"), `RVS-LINK-SUSPECT` (a parent changed; review and clear), `RVS-RULE-UNDEFINED-ACRONYM` (add the acronym to the glossary with **Project > Glossary and Acronyms…**, Ctrl+Shift+G; the dialog has an *Acronyms* tab, which the rule reads, and a *Terms* tab for definitions of project words). *Run Full Doorstop Validation* (Ctrl+Shift+V) additionally runs Doorstop's own tree checks. Information-level findings starting with `DOORSTOP-` can be ignored or hidden with *Errors only* (see *Suspect links and review* in the reference).

## 5. See the whole picture

- **Traceability** shows which items of one document are linked from another, in both directions. Choose *From* and *to* documents and the direction: *down* lists, for each row, the items below it (children, verifiers); *up* lists the items above it. Gaps (a requirement without a child, without a parent, or nothing verifying it) are shaded, and the last column names the gap.

![The verification control matrix](images/vcm.png)

- **VCM** lists every requirement with its verification method, level, the verification items that cover it, their combined status and the evidence. It is not shaded. Filter by document, method, level or status, or tick *Only unverified* to list just the requirements that nothing verifies.
- **Coverage** shows, for each document, the number of items and their share (in percent) per item status, and for requirements also per verification state (*not verified*, *planned*, *in-progress*, *passed*, *failed*, *waived*). For a verification document the verification columns count its items per verification status.
- **Graph** draws the neighbourhood of the selected item: upstream items above it, downstream items (children, verifiers) below. The *Depth* box (1 to 4) sets how many links away to draw; click a node to open that item.

![The graph of one requirement: its parent above, its verification item below](images/graph.png)

- The **Impact** panel lists everything that depends on the selected item, so you can see what a change would touch, as a *Tree* (by link) or a *List* (with depth and the link it follows). Double-click a row to open that item. Items related by *conflicts-with* are named separately.

Every matrix tab has an **Export…** button; the file type you pick (Excel, CSV, Word, PDF, HTML or JSON) decides the format.

## 6. Record verification results

A verification item says how a requirement is shown to be met, and whether it has been. To record a result:

1. Select the verification item (in the verification plan, for example `VER`) or create one with **Item > New Verification Item…** (Ctrl+Shift+N), choosing the requirement(s) it verifies. In the wizard, step 4 does this for a new requirement.
2. Fill in the verification fields in the editor:
   - **Procedure ID** (`proc_id`): the identifier of the test procedure or analysis report.
   - **Verification method** and **Verification level**: how and at which level it is shown (the same vocabulary as on requirements; a method that differs from the requirement's is reported as `RVS-LINK-METHOD-MISMATCH`).
   - **Verification status** (`v_status`): `planned` (the default), `in-progress`, `passed`, `failed` or `waived`.
   - **Evidence** (`evidence`): where the proof is, preferably a path inside the project folder (so it is kept under Git) or a document number and revision.
   - **Executed on** (`executed_on`): the date, as `YYYY-MM-DD`.
   - **Responsible** (`responsible`): who carried it out or signs it off.
   - **Non-conformances** (`nonconformances`): references to non-conformance reports raised during the verification, comma separated.
3. Press **Ctrl+S**. The VCM and Coverage tabs update; a requirement is *passed* only when every verification item that verifies it has passed (or been waived), *failed* as soon as one fails, and *not verified* when nothing verifies it.

## 7. Retire an item, or add a document

**Retire an item.** Set its status to `obsolete` in the editor. That keeps it in the lists and the matrices, marked obsolete. To take an item out of rules, matrices and coverage completely, mark it inactive: export the items table, set its `active` column to `no`, and import the file (with a reason if the item is baselined). The file stays in the project and its history is kept; items are never deleted from within RVS.

**Add a document to an existing project.** There is no command or dialog for this yet (see `docs/DEVIATIONS.md`). It is done by hand and takes a minute:

1. Create a folder named after the new prefix, for example `PWR/`, in the project folder.
2. Copy the file `.doorstop.yml` from an existing document of the same kind (requirements or verification) into it, and change `prefix:` and, if needed, `parent:` in its `settings:`.
3. Add the document to the `documents:` list in `rvs-project.yaml` with its `kind`, `prefix`, `title` and `parent`. Exactly one document (the root) has no parent.
4. Run `rvs validate PROJECT`; it should report no errors. New items can now be created in the new document in the wizard, or by importing a table with new IDs such as `PWR-0001`.

## 8. Produce documents

**File > Export…** (Ctrl+E) writes a matrix, a specification document, the items table or a ReqIF exchange file. Formats: HTML, DOCX, PDF, XLSX, CSV and JSON for matrices; HTML, DOCX and PDF for specifications; CSV and XLSX for the items table; ReqIF for the exchange file. Exports run in the background and name the project, the baseline (or "working copy") and the date and time. A file that already exists is only replaced after you confirm, and it is replaced as a whole or not at all.

## 9. Control changes

Raise a **change request** in the Changes tab: fill in *Title*, *Description* and the affected *Items* and press **New**; later pick its *Status* and press **Save**. Tick *Attribute my edits to this change request* and every edit you make is recorded against it. The list *Edited under this change request* shows what was changed.

When a milestone is reached, create a **baseline** with **Project > New Baseline…**. A baseline needs the project to be under Git. The example projects are not, so in the dialog tick *Turn on version control* to create the repository (or use `rvs baseline create … --init-git` on the command line). See *Change control* for details.
