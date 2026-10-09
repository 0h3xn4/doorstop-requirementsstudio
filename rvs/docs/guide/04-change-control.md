# Change control

RVS supports a light configuration-management workflow: change requests that record why things changed, baselines that freeze an agreed state, and a comparison between any two states.

## Change requests

A change request (CR) is a small file `changes/CR-0001.yaml` with a title, a description, the affected items and a status log. Create one in the **Changes** tab (fill in the form, press *New*) or with `rvs cr new`.

- Statuses (default): `open`, `in-review`, `approved`, `implemented`, `closed`, `rejected`, `deferred`. They are configuration (`config/changes.yaml`); the names are a starting point to adapt to your own process.
- Tick *Attribute my edits to this change request* in the Changes tab (or pass `--cr CR-0001` to `rvs import`) and the item history records the CR for every edit. The tab lists the items edited under a CR.
- The status bar shows *editing under CR-0001* while a CR is active.

## Reasons for change

Once an item is **baselined**, every edit needs a reason (the statuses that require one are configurable: `change_control.reason_required_statuses` in `config/rules.yaml`): a box in the editor, a prompt for in-table edits, `--reason` for imports. The reason is stored in the item's history (the `history/` folder of the project) together with who, when and which fields changed.

## Baselines

A baseline is a named, immutable snapshot of the whole project, for example `SRR` or `CDR`. Create one with **Project > New Baseline…** (Ctrl+Shift+B) or `rvs baseline create`.

What happens:

1. Open change requests block the baseline, unless you **defer** each one with a reason (the dialog offers a check box per CR; on the command line use `--defer CR-0001="after SRR"`).
2. Items with status *approved* become *baselined*.
3. A manifest `baselines/<name>.yaml` records a content digest of every item.
4. The project folder is committed to Git and tagged `rvs/baseline/<name>` (an annotated tag). This needs the project to be in a Git repository; the dialog and `--init-git` can create one. RVS never signs commits and never talks to a remote: pushing is up to your normal Git workflow.
5. A baseline name is never reused.

`rvs baseline verify <project> <name>` checks that the manifest still matches the tagged content. Tampering is also reported by `rvs validate` (`RVS-BASELINE-MODIFIED` for a changed manifest, `RVS-BASELINE-CORRUPT` for content that no longer matches it, `RVS-BASELINE-NOTAG` for a missing tag).

Every export names the baseline it comes from. `rvs export … --baseline SRR` produces any matrix or document *as it was* at that baseline, using the configuration of that time.

## Comparing versions

The **Diff** tab (or `rvs diff <project> <left> <right>`) compares two baselines, or a baseline and the working copy (`working`). It lists added, removed and changed items, and for changed items shows each field before and after. Statements are compared word by word: deletions are struck through, insertions underlined. Export the comparison as HTML, DOCX, PDF, CSV or JSON. The **Baselines** tab has a *Compare with working copy* button.

## Suspect links

When a parent item changes after a child was reviewed, the link from the child is *suspect* (`RVS-LINK-SUSPECT`). Review the parent, then use **Clear suspect links** in the child's editor. RVS never clears suspect links on its own, and changing only the *status* of a parent does not make links suspect.
