# Project files

This page explains what is inside a project folder, what you may edit by hand and what you should leave alone.

## The layout

```
my-project/
  rvs-project.yaml     the project name and its documents (prefix, kind, title, parent)
  config/              settings, one file per topic
  SYS/  SUB/  VER/     one folder per document: .doorstop.yml and one YAML file per item (SYS-0001.yml)
  changes/             change requests (CR-0001.yaml)
  baselines/           baseline manifests (PDR.yaml)
  history/             who changed what, when and why: history/<PREFIX>/<ID>.jsonl
  .rvs-cache/          disposable speed-up cache (ignored by Git; delete any time)
```

Everything is plain text. You can read it, search it, diff it and merge it with Git. RVS writes each file whole or not at all.

## An item file

`SYS/SYS-0001.yml` of the *Minimal* example holds one requirement:

```
active: true
derived: false
header: ''
level: 1.1
links: []
normative: true
owner: systems
priority: high
ref: ''
reviewed: null
rvs_schema_version: 1
status: draft
text: |
  The spacecraft shall provide electrical power to all payloads.
title: Payload power
type: functional
verify_level: system
verify_method: analysis
```

`links` are the parent links (empty here). `level` is the position in the document, `derived: true` marks an item that deliberately has no parent, and `reviewed` belongs to Doorstop's own review feature, which RVS does not use. The statement is the `text` field (Markdown). Item IDs look like `SYS-0012`.

## What you may edit by hand

| File | Edit by hand? |
|---|---|
| `config/*.yaml` | yes, it is meant to be adapted (vocabulary, rules, templates, glossary, change statuses) |
| item files | possible, but prefer the window or an import: RVS then checks the result and records the history |
| `rvs-project.yaml` | yes, to declare a new document |
| `changes/`, `baselines/`, `history/` | **no**: baselines are immutable; a changed manifest is reported as `RVS-BASELINE-MODIFIED` |
| `.rvs-cache/` | no need; safe to delete |

After any hand edit run `rvs validate PROJECT`: a mistake in the YAML is reported with the file and line.

## Configuration files in `config/`

| File | Holds |
|---|---|
| `numbering.yaml` | the ID format |
| `vocab.yaml` | allowed values (status, type, priority, verification method, level, verification status) |
| `templates.yaml` | the fields of requirements and verification items |
| `rules.yaml` | quality rules and which statuses need a reason |
| `links.yaml` | typed links |
| `exports.yaml` | the matrix columns |
| `standards.yaml` | standards references (placeholders stay `TODO-STANDARD`) |
| `glossary.yaml` | terms and acronyms |
| `changes.yaml` | change request statuses and what happens at a baseline |

Details: [guide, project files and format](../guide/07-reference.md#project-files-and-format).

Next: [User manual index](README.md) · [Glossary](../glossary.md) · [Developer docs](../developer/README.md)
