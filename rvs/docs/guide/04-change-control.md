# Change control

RVS supports a light configuration-management workflow: change requests that record why things changed, baselines that freeze an agreed state, and a comparison between any two states.

## Change requests

A change request (CR) is a small file `changes/CR-0001.yaml` with a title, a description, the affected items and a status log. Create one in the **Changes** tab (fill in *Title*, *Description* and *Items*, press *New*) or with `rvs cr new`. Select a request in the list to change its title, description, items or *Status* and press *Save*.

- Statuses (default): `open`, `in-review`, `approved`, `implemented`, `closed`, `rejected`, `deferred`. They are configuration (`config/changes.yaml`); the names are a starting point to adapt to your own process (`TODO-COMPANY`).
- **Blocking statuses.** A baseline cannot be created while a change request has one of the statuses listed under `open_statuses` in `config/changes.yaml` (default: `open`, `in-review`, `approved`), unless it is deferred (below). `implemented`, `closed`, `rejected` and `deferred` do not block.
- **Attributing edits.** Tick *Attribute my edits to this change request* in the Changes tab (or pass `--cr CR-0001` to `rvs import`) and the item history records the CR for every edit. This is only accepted for a change request whose status is in `open_statuses` (the same three by default); for any other status RVS refuses with a message. The tab lists the items edited under a CR.
- The status bar shows *editing under CR-0001* while a CR is active.

## Reasons for change

An edit needs a **reason** for every item that is part of any baseline (listed in a baseline manifest), and for every item whose status is listed in `change_control.reason_required_statuses` in `config/rules.yaml` (default: `baselined`). That covers editing fields, changing parents, clearing suspect links and import rows. Give the reason in the box in the editor, in the prompt for in-table edits, or with `--reason` for imports. The reason is stored in the item's history (the `history/` folder of the project) together with who, when and which fields changed.

## Baselines

A baseline is a named, immutable snapshot of the whole project, for example `SRR` or `CDR`. Create one with **Project > New Baseline…** (Ctrl+Shift+B) or `rvs baseline create PROJECT NAME -m "reason"`.

**Baselines need the project folder to be a Git repository.** Git does not have to be installed: RVS has its own. A project is under Git if you created it with **File > New Project…** (*Keep this project under Git* is ticked by default), with `rvs init … --git`, or if it lies inside a Git repository you already use. For any other project, including the example projects, turn Git on when you create the first baseline: tick *Turn on version control* in the New Baseline dialog, or add `--init-git` to `rvs baseline create`. Without it the baseline is refused with a message that says so.

**Baseline names.** 1 to 64 letters, digits, `.`, `_` and `-`, starting with a letter or digit; no spaces or slashes, no `..`, and not ending in `.` or `.lock`. `working` is reserved (it stands for the working copy in comparisons), and so are the Windows device names `CON`, `PRN`, `AUX`, `NUL`, `COM1` to `COM9` and `LPT1` to `LPT9`, with or without an extension. A name is never reused, and a name that differs from an existing one only in upper or lower case is refused too (`SRR` and `srr` are one file on Windows and macOS).

What happens:

1. Open change requests block the baseline, unless you **defer** each one with a reason (the dialog offers a check box and a reason per CR; on the command line use `--defer CR-0001="after SRR"`). Deferring sets the CR's status to `deferred` and lists it in the manifest.
2. Items with status *approved* become *baselined* (configurable: `promote_on_baseline` in `config/changes.yaml`).
3. A manifest `baselines/<name>.yaml` records a content digest of every item.
4. The project folder is committed to Git and tagged with an annotated tag `rvs/baseline/<name>`. When the project folder is a sub-folder of a larger repository, only that sub-folder is committed and the tag carries the folder name: `rvs/baseline/<folder>/<name>`. RVS never signs commits and never talks to a remote: pushing is up to your normal Git workflow.
5. A baseline name is never reused.

Which files are committed: all files of the project folder except `.git`, `.rvs-cache` and temporary `*.tmp` files. RVS's own project data (items, configuration, manifests, change requests and history files: `.yml`, `.yaml`, `.jsonl`) is **always** included, even if a `.gitignore` rule would match it, so a baseline always holds the state its manifest describes. Other files that your `.gitignore` ignores (build output, secrets) are not added.

If creating the baseline fails at any step, everything it changed is put back and the name stays free.

`rvs baseline verify PROJECT NAME` (or the **Verify** button in the Baselines tab) checks that the manifest still matches the tagged content, and reports `RVS-BASELINE-CORRUPT` if the tagged content no longer matches the manifest. `rvs validate` reports a changed manifest (`RVS-BASELINE-MODIFIED`), a missing manifest for an existing tag (`RVS-BASELINE-NOMANIFEST`) and a missing tag (`RVS-BASELINE-NOTAG`). The **Baselines** tab also lists the baselines and has *Compare with working copy*; `rvs baseline list PROJECT --format json` prints them for scripts (`name`, `description`, `created_by`, `created`, `commit`, `tag`, `items`, `deferred`, `manifest_sha256`).

Every export names the baseline it comes from. `rvs export … --baseline SRR` produces any matrix or document *as it was* at that baseline, using the configuration of that time.

## Comparing versions

The **Diff** tab (or `rvs diff <project> <left> <right>`) compares two baselines, or a baseline and the working copy (`working`). It lists added, removed and changed items, and for changed items shows each field before and after. Statements are compared word by word: in the application deletions are struck through and insertions underlined; in `rvs diff` text output a deleted word is written `[-old-]` and an inserted one `{+new+}`. Export the comparison as HTML, DOCX, PDF, CSV or JSON. The **Baselines** tab has a *Compare with working copy* button.

## Suspect links

When a parent item changes after a child was reviewed, the link from the child is *suspect* (`RVS-LINK-SUSPECT`). Review the parent, then use **Clear suspect links** in the child's editor (the button is always shown and is enabled only when the item has suspect links). RVS never clears suspect links on its own. Only *parent* links can become suspect, and only when the parent's statement or one of the fingerprint attributes (title, type, verification method and level) changes: changing the *status* of a parent does not, and the typed links (`satisfies`, `verifies`, `refines`, `conflicts-with`) are never suspect.
