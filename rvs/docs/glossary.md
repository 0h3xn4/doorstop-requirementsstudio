# Glossary

This page explains every domain term and acronym used in the Requirements & Verification Studio (RVS) documentation, in alphabetical order. The pages that use a term link back here.

**Jump to:** [A](#a) · [B](#b) · [C](#c) · [D](#d) · [E](#e) · [F](#f) · [G](#g) · [I](#i) · [L](#l) · [M](#m) · [N](#n) · [O](#o) · [P](#p) · [R](#r) · [S](#s) · [T](#t) · [V](#v) · [W](#w) · [Y](#y)

## A

### Acronym
A short form such as EPS. The rule `undefined-acronym` finds acronyms in a requirement that are not in the project glossary (**Project > Glossary and Acronyms…**).

### AIT
Assembly, Integration and Test: the phase in which a spacecraft is put together and tested. Not a feature of RVS; verification items with `test` as their method are typically carried out during AIT.

### Analysis
A *verification method*: showing a requirement is met by calculation, modelling or simulation. The others are *test*, *inspection* and *review of design*.

### AOCS
Attitude and Orbit Control System: the part of a spacecraft that points and steers it. One of the subsystem documents in the *Small satellite* example.

## B

### Baseline
A named, frozen state of the whole project, for example `SRR` or `PDR`, bound to a Git tag. It can never be changed or reused. See [change control](user-manual/06-change-control.md).

### Baselined
A requirement *status*. Approved items become baselined when a baseline is created.

## C

### CDR
Critical Design Review: a project milestone, a typical name for a baseline.

### Change request (CR)
A small record (`changes/CR-0001.yaml`) that asks for, explains and tracks a change. Open ones block a baseline unless you defer them.

### Coverage
How many items there are per status and how many requirements are verified. The **Coverage** tab.

## D

### Derived
A requirement that deliberately has no parent, because it comes from a design decision and not from a higher requirement. Rules and the matrices skip derived items when they look for missing parents. Set by [importing a table](user-manual/07-import-export-reports.md#change-many-items-in-a-spreadsheet).

### Digest
A SHA-256 fingerprint of an item's content. If one character changes, the digest changes: that is how a baseline detects tampering.

### Document
A folder of items with a prefix, for example `SYS`. Documents form a tree; each has a parent document except the root.

### Doorstop
The open-source requirements tool (doorstop.dev) that RVS is built on. It stores each requirement as a small text file. This repository is a copy (a fork) of it; RVS adds a desktop application, rules, verification, matrices, change control and reports. You do not install Doorstop separately.

## E

### ECSS
European Cooperation for Space Standardization: the set of standards used in European space projects. RVS mentions three: **ECSS-E-ST-10-06C** (writing technical requirements), **ECSS-E-ST-10-02C** (verification, which defines the verification control matrix) and **ECSS-M-ST-40C** (configuration management). RVS does not contain their text, so values that depend on them are marked `TODO-STANDARD`.

### EPS
Electrical Power Subsystem. A subsystem document in both examples.

### Evidence
Where the proof that a requirement is met is kept: a path inside the project folder, or a document number and revision. A field of verification items.

### Expert mode
The dense mode of the application: a small new-item dialog and cells you edit in the table. See [modes](user-manual/09-settings-modes-shortcuts.md).

## F

### Fingerprint attributes
The fields whose change makes the links of children suspect: the statement plus title, type, verification method and level. Status, owner and priority are not part of it.

### Finding
One problem found by `rvs validate` or shown in the Problems panel, with a code such as `RVS-RULE-SHALL-PRESENT`, a message and a hint on how to fix it. (Doorstop calls the same things *issues*.)

## G

### Gap
Something missing in the chain of evidence: a requirement without a child (*childless*), without a parent (*orphan*), or that nothing verifies (*unverified*).

### Git
The version-control system. RVS has its own built-in Git for local work, so you do not have to install Git. Baselines are Git tags.

### Guided mode
The default mode: a wizard for new requirements and a help line for the field you are in.

## I

### ICD
Interface Control Document: describes the interface between two systems or subsystems. Not a feature of RVS. The *Software product* template has a document for interface requirements.

### ID
The identifier of an item: the document prefix, a dash and a number, such as `SYS-0012`. (Doorstop calls it UID.)

### Inspection
A *verification method*: showing a requirement is met by examining the product or a document.

### Item
One requirement or one verification item: one file such as `SYS-0012.yml`.

## L

### Level
The position of an item in its document, such as `1.2`; it decides the order. Also the *verification level* (unit, subsystem or system) of a verification item. The context tells which.

## M

### Manifest
The file `baselines/<name>.yaml` listing every item of a baseline with its digest.

### MIS
Mission requirements: the root document of the *Small satellite* example.

## N

### NCR
Non-Conformance Report: a record that something did not meet its requirement. A verification item can list the NCRs raised during its verification (field *Non-conformances*).

### Normative
A *normative* item is a real requirement. A non-normative item (a heading) only structures the document: rules, matrices and counts ignore it.

## O

### OBC
On-Board Computer.

### Orphan
A requirement that has no parent. A *gap*.

## P

### Parent link
A link from an item to the item it derives from, in the parent document. Doorstop just calls these *links*.

### PDR
Preliminary Design Review: a project milestone and a typical baseline name.

### PLD
Payload: the instruments a spacecraft carries. A subsystem document in the *Small satellite* example.

### Provenance
The block that every output carries: project, baseline (or *working copy*), date and time of generation, user, tool and Doorstop version.

## R

### ReqIF
Requirements Interchange Format: an XML file format most requirements tools can read and write. RVS exports and imports it. See [import and export](user-manual/07-import-export-reports.md#exchange-with-other-tools-reqif).

### Requirement
A statement of what a system shall do, in a requirements document. Written "The <system> shall <do something>".

### Review of design
A *verification method*: showing a requirement is met by reviewing design documents.

### Root document
The top document of the project tree: it has no parent. There is exactly one.

## S

### SBOM
Software Bill of Materials: the list of every library inside a program. The release build writes one (`sbom.cdx.json`). For maintainers.

### Shall
The word that marks a requirement. The rule `shall-present` checks it.

### SRR
System Requirements Review: a project milestone and a typical baseline name.

### Statement
The text of a requirement (Markdown). Doorstop calls the field `text`.

### STR
Structure: a subsystem document in the *Small satellite* example.

### Suspect link
A parent link whose parent changed (its statement or a fingerprint attribute) after the link was last accepted. Review the parent, then clear the link. Only parent links can be suspect. See [link and trace](user-manual/03-link-and-trace.md#deal-with-a-suspect-link).

### SYS
System requirements: the document that sits below the mission requirements (or at the top, in the minimal template).

## T

### Test
A *verification method*: showing a requirement is met by running the product under controlled conditions.

### THM
Thermal: a subsystem document in the *Small satellite* example.

### TODO-COMPANY / TODO-STANDARD
Placeholders in `config/` for values your organisation (or a standard such as ECSS) has to supply. RVS never invents them and reports them as information until you replace them.

### TT&C (TTC)
Telemetry, Tracking and Command: the radio link to the ground. Written `TTC` in file and document names.

### Typed link
An extra relation between items besides parent links: `satisfies`, `refines`, `verifies` and `conflicts-with`.

## V

### VCM
Verification Control Matrix: a table listing every requirement with how, at which level and whether it is verified, and the evidence. The **VCM** tab and `rvs export --vcm`. Its layout comes from ECSS-E-ST-10-02C; RVS uses a placeholder layout until you supply that standard.

### Verification item
An item in a verification document that says how and whether a requirement is shown to be met: procedure, method, level, status, evidence, date, responsible person.

### Verification method, level, status
*Method*: how (test, analysis, inspection, review of design). *Level*: at what level (unit, subsystem, system). *Status*: planned, in-progress, passed, failed or waived.

## W

### Working copy
The project files as they are now, as opposed to a baseline. Exports name it *working copy*, and `working` in `rvs diff` stands for it.

## Y

### YAML
A plain-text file format for structured data. Items, settings and baselines are YAML files that you can read and edit in any text editor.

Next: [User manual](user-manual/README.md) · [Getting started](getting-started.md) · [FAQ](faq.md)
