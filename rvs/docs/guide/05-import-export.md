# Import and export

## What can be exported

| Content | Command | Formats |
|---|---|---|
| Verification control matrix (VCM) | `--vcm` | csv, json, xlsx, html, docx, pdf |
| Traceability matrix between two documents | `--trace SRC:DST` (optionally `:up` or `:down`, for example `--trace SYS:SUB:down`) | same |
| Coverage per document | `--coverage` | same |
| Impact of changing one item | `--impact UID` | same |
| Specification document(s) | `--spec [--document PREFIX]` | html, docx, pdf |
| All items as a table | `--items` | csv, xlsx |
| Exchange file for other tools | `--reqif [--document PREFIX]` | reqif |

**Choosing the format.** `--format` names it explicitly. Without `--format`, the format is taken from the extension of the `-o` file (`.csv`, `.json`, `.xlsx`, `.html`, `.docx`, `.pdf`, `.reqif`), and without `-o` (or with another extension) it is `csv`, `html` for `--spec` and `reqif` for `--reqif`. So `rvs export P --vcm -o vcm.xlsx` writes an Excel file, and `rvs export P --vcm` prints CSV. An explicit `--format` always wins over the file name (`--format csv -o data.xlsx` writes CSV text into a file called `data.xlsx`). A kind that cannot be written in the chosen format (for example `--items` as `pdf`, or `--spec` as `csv`) is refused with a message. (In the application the file name's extension decides on the matrix tabs, and the *Format* box on **File > Export…**.)

Binary formats (xlsx, docx, pdf) need an output file (`-o file`); text formats go to standard output without `-o`. Files are written as a whole or not at all: if an export fails, a previous file of the same name is left intact. Filters narrow the VCM: `--document`, `--method`, `--level`, `--status`, `--only-gaps`. Add `--baseline NAME` to export the state at a baseline.

In the application, **File > Export…** offers the same contents (including *ReqIF exchange file*), and every matrix tab has an **Export…** button for the table it shows.

Every output carries its provenance: project, baseline (or *working copy*), the date and time it was generated, user, and tool versions. Files are reproducible: exporting the same state twice gives byte-identical files when the generation time is the same. Set the environment variable `SOURCE_DATE_EPOCH` (seconds since 1970, UTC) to fix that time, for example `SOURCE_DATE_EPOCH=1767225600 rvs export P --vcm -o vcm.xlsx`.

The VCM layout is a neutral placeholder. It will be aligned with ECSS wording only once you supply the standard's text (`TODO-STANDARD` in `config/standards.yaml`).

## Importing items

`rvs import` and **File > Import Items…** read a CSV or XLSX table written by `export --items`. You can edit it in a spreadsheet and bring the changes back.

- Existing items are matched by ID; unchanged rows do nothing. A table with only `id` and `title` columns updates only titles.
- Rows with new IDs (or a blank ID) create items.
- The columns `derived`, `normative`, `active` (write `yes` or `no`), `level`, `header` and `ref` set the Doorstop fields that the editor does not offer. This is the only way to change them.
- Row-level errors are listed with the row number: unknown columns, values outside the vocabulary, missing parents, parents in the wrong document, duplicate IDs, and changes to baselined items without a reason.
- Nothing is written unless every row is valid, or you choose to skip the rows with errors (`--skip-errors`, or the check box *Import the valid rows and skip rows with errors* in the preview).
- Each imported change is recorded in the item history.

`--dry-run` shows the plan and writes nothing: it lists each row that would be **created** or **updated** and each row **error**; rows that would not change anything are not listed, only counted in the last line (`2 to create, 5 to update, 120 unchanged, 1 errors.`). Always run it first on a large file.

## ReqIF exchange

ReqIF (OMG Requirements Interchange Format) is the file format most requirements tools (DOORS, Polarion, Jama and others) can read and write. In the application choose **File > Export…** with content *ReqIF exchange file*, or on the command line `rvs export PROJECT --reqif -o project.reqif`. Add `--document PREFIX` for part of the project.

What the file contains:

- one *specification* per document, with the items nested by their level;
- one *object* per item, with every attribute of the project templates (enumerations use the project vocabulary);
- the statement twice: as XHTML (what other tools display) and as the original Markdown (what RVS reads back);
- *relations* for parent links and for the typed links `satisfies`, `verifies`, `refines` and `conflicts-with`. Relations that point outside the exported documents are left out.

Importing a ReqIF file works like importing a table, with the same dry run, checks, history and reasons: `rvs import PROJECT file.reqif --dry-run`, or **File > Import Items…**. Files written by RVS come back exactly as they were. Files from other tools are matched as follows:

- A specification is imported into the document with the same name or title. If none matches, name the target with `--document PREFIX` (the application asks).
- Attributes are matched by name with the item columns (`Title`, `Owner`, `Status`, `Priority` and so on; `ReqIF.Name` and `ReqIF.ChapterName` become the title, `ReqIF.Text` the statement). Use `--map "Their name=column"` (repeatable) for others. Attributes that match nothing are listed and not imported.
- Objects without an RVS item ID get the next free IDs of the document, in hierarchy order, and their position in the hierarchy becomes the item level.
- Relations of type `parent` and of the typed link names are imported when both ends are in the file. Other relation types are listed and skipped, and a parent relation inside one document is skipped because parent links go to the parent document.

RVS refuses files with DOCTYPE or entity declarations. The files RVS writes declare ReqIF version 1.0 in their header and follow the element structure of ReqIF 1.2, but could not be checked against the official XSD offline; if a tool rejects one, please send the tool's message.
