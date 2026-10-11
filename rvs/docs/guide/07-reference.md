# Reference

## Keyboard shortcuts

<!-- shortcuts-table -->

### Changing a shortcut

Add an entry to `"shortcuts"` in `settings.json` (see *Where RVS keeps its own settings*), using the **action ID** from this table and a key such as `Ctrl+Alt+E`. An override that Qt cannot read, or that another action already uses, is ignored and the default stays.

<!-- shortcut-ids-table -->

Besides shortcuts, `settings.json` holds `mode`, `theme`, `recent`, `geometry` and `layout`; the keys are listed under *Where RVS keeps its own settings*.

## Project files and format

A project is a folder:

```
my-project/
  rvs-project.yaml       project name, documents (prefix, kind, title, parent) and optional free attributes
  config/                configuration, one file per topic (see below)
  SYS/ SUB/ VER/ …       one folder per document: a .doorstop.yml (the document's settings) and one YAML file
                         per item (SYS-0001.yml)
  changes/               change requests (CR-0001.yaml)
  baselines/             baseline manifests (SRR.yaml)
  history/               per-item edit history: history/<PREFIX>/<ID>.jsonl (who, when, which fields, why)
  .rvs-cache/            disposable speed-up cache; ignored by Git and by Doorstop
```

Items are plain YAML written by Doorstop 3.2; the statement is the `text` field (Markdown). Item IDs look like `SYS-0012`.

Everything can be edited with a text editor, and diffed and merged with Git. RVS rewrites only the files of the items it changes, and it writes each file as a whole or not at all. The edit history (`history/`) records field *names*, never values; the values are in the item files and their Git history.

**Item fields.** Besides the template fields, an item has Doorstop's own fields: `text` (the statement), `level`, `normative`, `derived`, `active`, `header`, `ref` and `links` (parent links). The editor and `rvs` edit the template fields and the parents; the others are changed by importing a table (see *Bulk changes with a spreadsheet*).

**Status values** (`config/vocab.yaml`): requirements are `draft`, `reviewed`, `approved`, `baselined` or `obsolete`; verification items use the verification status `planned`, `in-progress`, `passed`, `failed` or `waived`. A requirement's *combined* verification status (VCM, Coverage) is `failed` if any verifying item failed, otherwise `passed`, `waived` or `planned` if all of them are, `not verified` if nothing verifies it, and `in-progress` for any other mixture. This is a convention of the tool, not taken from a standard.

**Typed links** are stored in the linking item as lists of IDs: `link_satisfies`, `link_refines` and `link_conflicts` on requirements, `link_verifies` on verification items (see *Terms used in this guide* for their meaning, and `config/links.yaml` for which document kinds each may connect). Parent links are Doorstop's `links`. Only parent links can be suspect.

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

Rules apply to normative, active items of requirements documents (headers and verification items are skipped), except `undefined-acronym`, which reads every active item. Parameters are under `params:` in `config/rules.yaml`; every word or phrase match ignores upper and lower case and matches whole words.

| Rule | Code | Default | What it checks | Parameters |
|---|---|---|---|---|
| `shall-present` | `RVS-RULE-SHALL-PRESENT` | error | The statement uses "shall". | `keyword` (default `shall`) |
| `single-statement` | `RVS-RULE-SINGLE-STATEMENT` | warning | One requirement per statement. | `keyword` (`shall`), `max` (how many times it may occur, default 1) |
| `vague-words` | `RVS-RULE-VAGUE-WORDS` | warning | None of the configured vague words or phrases is used. | `words`: a list (ships with a short `TODO-COMPANY` seed) |
| `no-implementation` | `RVS-RULE-NO-IMPLEMENTATION` | warning | A *functional* requirement does not name a design term. | `terms`: a list. **It ships empty, so the rule finds nothing until you configure terms** (`TODO-COMPANY`). |
| `verify-method-set` | `RVS-RULE-VERIFY-METHOD-SET` | warning | A verification method is set. | none |
| `has-parent` | `RVS-RULE-HAS-PARENT` | error | The item has a parent unless it is in the root document or is *derived* (set `derived` to `yes` by import). | none |
| `verified-when-approved` | `RVS-RULE-VERIFIED-WHEN-APPROVED` | error | An item whose status is one of the listed ones has at least one verifying item. | `statuses` (default `approved`, `baselined`) |
| `undefined-acronym` | `RVS-RULE-UNDEFINED-ACRONYM` | warning | Acronyms in the statement, title and rationale are defined in the glossary. | `min_length` (default 2), `ignore`: words that are not acronyms (ships with GB, MB, TB, KB) |

Each rule also has `severity` (`error`, `warning`, `info`) and `enabled`. The statuses that need a reason for change are set separately under `change_control.reason_required_statuses`.

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
| `RVS-ITEM-DUPLICATE-KEY` | An item file has the same key twice; only the last value is used. Remove the extra line (a bad Git merge is the usual cause). |
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

## Suspect links and review

Two different ideas are easy to mix up.

- A **suspect link** is RVS's own check, and it is what you act on: a parent changed (its statement or a fingerprint attribute) after the child's link to it was last accepted. The finding is `RVS-LINK-SUSPECT`. Review the parent, decide whether the child still holds, and press **Clear suspect links** (or fix the child first). Nothing clears them automatically.
- **Reviewed** is the status value `reviewed` in the requirement life cycle (`draft`, `reviewed`, `approved`, …), set by people in the *Status* field. It is unrelated to links.

Doorstop itself has a third idea, a *review* stamp on each item ("this exact text was reviewed"). **RVS does not use Doorstop's review feature**: it never reviews items on your behalf and keeps no review stamps. Doorstop therefore reports every item as "needs initial review" or "has unreviewed changes", which RVS shows as the information-level finding `DOORSTOP-UNREVIEWED` (only in the full Doorstop validation). It is informational. You can ignore it, hide it with *Errors only* in the Problems panel, or filter it out in scripts by code (`rvs validate --format json`); it never affects the exit code.

## Configuration values to decide

`TODO-COMPANY` and `TODO-STANDARD` mark values that only your organisation (the priority scale, vague words, implementation terms, change request statuses) or a standard (the ECSS wording of the VCM layout) can supply. They are information-level findings (`RVS-STD-PLACEHOLDER`) until replaced; RVS does not guess them.

## Troubleshooting

**"The project could not be opened."** Read the message: it names the file and what to fix. `rvs validate PROJECT` shows the same findings with codes.

**A save is refused because of a reason.** The item is in a baseline, or its status requires a reason. Type why you are changing it.

**Baseline creation fails.** Open change requests (statuses `open`, `in-review`, `approved` by default) must be closed or deferred with a reason; the project must be in a Git repository (tick *Turn on version control* in the dialog, or use `--init-git`); and the name must be valid and unused (letters, digits, `.`, `_`, `-`; not `working`, not a Windows device name such as `CON`, and not the same as an existing name apart from upper and lower case).

**The window seems slow on a big project.** The first open builds the cache (a few seconds at 5,000 items); later opens are faster. *Only items with problems* and the document tree reduce what is shown.

**I do not see a network feature.** There is none, by design.

**I changed `derived` (or `level`, `active`, …) in the editor and cannot find it.** Those fields are not offered there; set them in an items table and import it (see *Bulk changes with a spreadsheet*).

**The graphical program does not start on Linux.** Run `rvs-studio` in a terminal and read the message. Usually a system library from the list in *Installing on Linux* is missing, or the system's glibc is older than 2.38 (use the wheelhouse install).
