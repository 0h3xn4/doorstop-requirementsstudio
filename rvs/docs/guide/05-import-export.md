# Import and export

## What can be exported

| Content | Command | Formats |
|---|---|---|
| Verification control matrix (VCM) | `--vcm` | csv, json, xlsx, html, docx, pdf |
| Traceability matrix between two documents | `--trace SRC:DST` (optionally `:up` or `:down`) | same |
| Coverage per document | `--coverage` | same |
| Impact of changing one item | `--impact UID` | same |
| Specification document(s) | `--spec [--document PREFIX]` | html, docx, pdf |
| All items as a table | `--items` | csv, xlsx |

Binary formats (xlsx, docx, pdf) need an output file (`-o file`). Filters narrow the VCM: `--document`, `--method`, `--level`, `--status`, `--only-gaps`. Add `--baseline NAME` to export the state at a baseline.

Every output carries its provenance: project, baseline (or *working copy*), date, user, and tool versions. Files are reproducible: exporting the same state twice gives byte-identical files when the date is the same.

The VCM layout is a neutral placeholder. It will be aligned with ECSS wording only once you supply the standard's text (`TODO-STANDARD` in `config/standards.yaml`).

## Importing items

`rvs import` and **File > Import Items…** read a CSV or XLSX table written by `export --items`. You can edit it in a spreadsheet and bring the changes back.

- Existing items are matched by ID; unchanged rows do nothing. A table with only `id` and `title` columns updates only titles.
- Rows with new IDs (or a blank ID) create items.
- Row-level errors are listed with the row number: unknown columns, values outside the vocabulary, missing parents, parents in the wrong document, duplicate IDs, and changes to baselined items without a reason.
- Nothing is written unless every row is valid, or you choose to skip the rows with errors.
- Each imported change is recorded in the item history.

Always run `--dry-run` first on a large file.
