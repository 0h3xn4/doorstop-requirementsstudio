# Reference

## Keyboard shortcuts

<!-- shortcuts-table -->

## Project files and format

A project is a folder:

```
my-project/
  rvs-project.yaml       project name, documents (prefix, kind, parent) and optional free attributes
  config/                configuration, one file per topic (see below)
  SYS/ SUB/ VER/ …       one folder per document, one YAML file per item (SYS-0001.yml)
  changes/               change requests (CR-0001.yaml)
  baselines/             baseline manifests (SRR.yaml)
  history/               per-item edit history (who, when, which fields, why)
  .rvs-cache/            disposable speed-up cache; ignored by Git and by Doorstop
```

Items are plain YAML written by Doorstop 3.2; the statement is the `text` field (Markdown). Item IDs look like `SYS-0012`. Typed links are stored in the linking item as lists of IDs (`link_satisfies`, `link_verifies`, …); parent links are Doorstop's `links`.

Everything can be edited with a text editor, and diffed and merged with Git. RVS rewrites only the files of the items it changes.

## Configuration files

All files live in `config/`, are validated against a schema when the project opens, and carry an `rvs_schema_version`. Files from an older version are migrated; files from a newer version are refused with a message. Missing files fall back to defaults and are reported as `RVS-CONFIG-DEFAULTED`.

| File | Purpose |
|---|---|
| `config/numbering.yaml` | Item ID format: separator, digits, per-document overrides |
| `config/vocab.yaml` | Allowed values for type, priority, status, verification method, level and verification status |
| `config/templates.yaml` | Attributes per document kind (requirements, verification): type, required, vocabulary, help text, defaults |
| `config/rules.yaml` | Quality rules, their severity, parameters and whether they are enabled; which statuses need a reason for change |
| `config/links.yaml` | Typed links (satisfies, verifies, refines, conflicts-with): attribute, allowed source and target kinds |
| `config/exports.yaml` | Column layouts of the VCM and traceability exports, provenance fields |
| `config/standards.yaml` | Standards references; values not yet supplied stay `TODO-STANDARD` |
| `config/glossary.yaml` | Terms and acronyms (edit with **Project > Glossary and Acronyms…**) |
| `config/changes.yaml` | Change request statuses, which ones block a baseline, and what happens to item statuses at a baseline |

To add a field to every requirement, add an attribute to `config/templates.yaml`; the editor, the wizard, imports and exports pick it up. Use `TODO-COMPANY` or `TODO-STANDARD` to mark values your organisation still has to decide; RVS reports them until replaced (`RVS-STD-PLACEHOLDER`) and never invents standard text.

## Quality rules

Configured in `config/rules.yaml`. Each rule has an ID, a severity (`error`, `warning` or `info`) and parameters. A finding's code is `RVS-RULE-` plus the ID in capitals.

| Rule | Code | Default | What it checks |
|---|---|---|---|
| `shall-present` | `RVS-RULE-SHALL-PRESENT` | error | The statement uses "shall". |
| `single-statement` | `RVS-RULE-SINGLE-STATEMENT` | warning | One requirement per statement (at most one "shall"). |
| `vague-words` | `RVS-RULE-VAGUE-WORDS` | warning | None of the configured vague words is used. |
| `no-implementation` | `RVS-RULE-NO-IMPLEMENTATION` | warning | A functional requirement does not prescribe a design. |
| `verify-method-set` | `RVS-RULE-VERIFY-METHOD-SET` | warning | A verification method is set. |
| `has-parent` | `RVS-RULE-HAS-PARENT` | error | The item has a parent unless it is in the root document. |
| `verified-when-approved` | `RVS-RULE-VERIFIED-WHEN-APPROVED` | error | An approved item has at least one verification link. |
| `undefined-acronym` | `RVS-RULE-UNDEFINED-ACRONYM` | warning | Acronyms used in text are defined in the glossary. |

One further code belongs to the rule machinery: `RVS-RULE-UNKNOWN` (`rules.yaml` enables a rule that this version does not provide).

## Finding codes

Every problem has a stable code, a message and a hint on how to fix it.

| Code | Meaning |
|---|---|
| `RVS-PROJECT-MISSING` | The project folder or a file it needs (such as `rvs-project.yaml`) does not exist. |
| `RVS-CONFIG-YAML` | A configuration file is not valid YAML. |
| `RVS-CONFIG-INVALID` | A configuration file does not match its schema. |
| `RVS-CONFIG-DEFAULTED` | A configuration file is missing; defaults are used. |
| `RVS-SCHEMA-MISSING` | A file has no `rvs_schema_version` (for an item it is treated as the current version; add `rvs_schema_version: 1`). |
| `RVS-SCHEMA-MISSING-FATAL` | Reserved: a file without a schema version that cannot be read at all. |
| `RVS-SCHEMA-INVALID` | The schema version is not a whole number. |
| `RVS-SCHEMA-OLDER` | A file is from an older version and was migrated in memory; saving writes the current version. |
| `RVS-SCHEMA-NOMIGRATION` | A file is older but no migration exists. |
| `RVS-SCHEMA-NEWER` | A file is from a newer version of RVS and is refused. |
| `RVS-TREE-INVALID` | The document tree cannot be read by Doorstop. |
| `RVS-ITEM-UNREADABLE` | An item file cannot be parsed, usually because a hand edit broke the YAML. The message names the file and the line; fix it and open the project again. |
| `RVS-ITEM-NAME` | An item file is not named like an ID of its document (for example `SYS-0001 copy.yml`, or an item of another document in this folder). Rename or remove it. |
| `RVS-VALIDATION-FAILED` | Validation stopped unexpectedly, usually because a hand-edited file has content RVS cannot interpret. The message names the kind of error only; check recent edits with `git diff`. |
| `RVS-DOC-MISSING` | A declared document has no folder. |
| `RVS-DOC-UNDECLARED` | A folder is a Doorstop document but is not declared in `rvs-project.yaml`. |
| `RVS-DOC-PARENT` | A document's parent differs from the declaration. |
| `RVS-DOC-FORMAT` | A document does not use YAML item files (warning). |
| `RVS-DOC-NUMBERING` | A document's ID format differs from `config/numbering.yaml`. |
| `RVS-DOC-FINGERPRINT` | A document's list of reviewed attributes differs from the template, so suspect-link detection would behave differently. |
| `RVS-ATTR-REQUIRED` | A required attribute is empty. |
| `RVS-ATTR-TYPE` | An attribute has the wrong type (for example a number where a list is expected). |
| `RVS-ATTR-UNKNOWN` | An item has an attribute that the template does not define; declare it under `free_attributes` in `rvs-project.yaml` or remove it. |
| `RVS-ATTR-VOCAB` | An attribute value is not in the project vocabulary. |
| `RVS-LINK-TARGET-MISSING` | A link points to an item that does not exist. |
| `RVS-LINK-KIND` | A typed link connects document kinds it may not connect. |
| `RVS-LINK-SELF` | An item links to itself. |
| `RVS-LINK-SUSPECT` | A parent changed after this item was reviewed. |
| `RVS-LINK-METHOD-MISMATCH` | A verification item uses a different method than the requirement it verifies. |
| `RVS-TRACE-NO-CHILD` | A requirement has no child requirement in the documents below it (warning; ignore it if no allocation is needed). |
| `RVS-STD-PLACEHOLDER` | Values marked `TODO-STANDARD` or `TODO-COMPANY` are still in use (information). |
| `RVS-CR-INVALID` | A change request file is not valid. |
| `RVS-CR-ITEM` | A change request lists an item that does not exist (warning). |
| `RVS-CR-STATUS` | A change request has a status that is not configured. |
| `RVS-BASELINE-MODIFIED` | The manifest of a baseline was changed after the baseline was created. |
| `RVS-BASELINE-CORRUPT` | The tagged content of a baseline does not match its manifest. |
| `RVS-BASELINE-NOMANIFEST` | A baseline's Git tag exists but its manifest file is missing, so the baseline is no longer enforced. Restore the file from the tagged commit. |
| `RVS-BASELINE-NOTAG` | A baseline manifest exists but its Git tag is missing. |

Doorstop's own tree validation (*Run Full Doorstop Validation*, `rvs validate` without `--fast`) adds findings with codes starting `DOORSTOP-`: `DOORSTOP-EMPTY-DOCUMENT` (a document has no items yet: normal in a new project), `DOORSTOP-NO-CHILD-LINKS`, `DOORSTOP-SUSPECT-LINK`, `DOORSTOP-UNREVIEWED`, and `DOORSTOP-WARNING` / `DOORSTOP-ERROR` for anything else Doorstop reports.

## Troubleshooting

**"The project could not be opened."** Read the message: it names the file and what to fix. `rvs validate PROJECT` shows the same findings with codes.

**A save is refused because of a reason.** The item is baselined. Type why you are changing it.

**Baseline creation fails.** Open change requests must be closed or deferred; and the project must be in a Git repository (the dialog offers to create one).

**The window seems slow on a big project.** The first open builds the cache; later opens are faster. *Only items with problems* and the document tree reduce what is shown.

**I do not see a network feature.** There is none, by design.
