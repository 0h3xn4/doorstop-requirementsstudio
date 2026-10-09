# Decisions

One line each: decision — rationale. Status: **A** = answered by user, **D** = default chosen by Claude (change by editing this file).

| # | Decision | Rationale | Status |
| --- | --- | --- | --- |
| D01 | RVS lives in `rvs/` of this repository; the Doorstop 3.2 source clone in the repo root is left untouched and is NOT a dependency of RVS | User choice; RVS depends on `doorstop==3.2` from PyPI per spec (never patch Doorstop). Revisit: a clean RVS repo avoids two pyprojects/CIs | A |
| D02 | Item format: YAML (Doorstop default) | Most widely tested; user choice | A |
| D03 | IDs: `<PREFIX>-<NNNN>` (`sep: "-"`, `digits: 4`), e.g. `SYS-0012` | Doorstop-native, simplest; user choice | A |
| D04 | ReqIF is deferred past v1; import/export layer has a format-plugin interface so it can be added later | User choice; no sample ReqIF available | A |
| D05 | Stack: Python + PySide6 (LGPL) + PyInstaller; Carbon look via bundled QSS/tokens and IBM Plex fonts (OFL) | Spec default; see ARCHITECTURE.md §2 | D |
| D06 | Supported Python 3.11–3.13; CI tests 3.13 | Spec rule 9 (Doorstop itself allows 3.10+) | D |
| D07 | Platforms: Windows 10/11 and Linux (RHEL/Rocky 8+, Ubuntu LTS); macOS untested | Spec default; no answer given | D |
| D08 | Evidence: repo-relative path via Doorstop `ref`/references, or `docno + revision` string; no network shares | Simplest; keeps evidence under Git | D |
| D09 | Approval = `status` field + Doorstop review fingerprint; no sign-off records in v1 (baseline stores who/when/why in its manifest) | Spec puts e-signatures out of scope | D |
| D10 | Licence: internal-only, but dependencies restricted to permissive/LGPL so open-sourcing stays possible | Safest default | D |
| D11 | SBOM: CycloneDX JSON via `cyclonedx-bom` in the `dev` extra only; installers unsigned (signing hook left as a documented step) | Spec rule 7/8; no accreditation answer | D |
| D12 | ECSS numbers/wording/VCM column layout are placeholders in `config/standards.yaml` marked `TODO-STANDARD`; none invented | Spec rule 15; standards text not supplied | D |
| D13 | Typed links stored as extended attributes (`link_satisfies`, `link_verifies`, `link_refines`, `link_conflicts`, `link_refs`) as lists of item UIDs; RVS validates targets | Doorstop `links` are parent-only (spec table) | D |
| D14 | Change log (who/when/why) is derived from Git commits (trailer `RVS-Reason:`) plus `rvs/changes/*.yaml` for change requests; no timestamps inside item files | Rule 14 (byte-identical regeneration) | D |
| D15 | Baseline = annotated Git tag `rvs/baseline/<name>` + manifest `baselines/<name>.yaml` (item UID → content hash) committed before tagging | Immutable, diffable, offline | D |
| D16 | Runtime dep is `PySide6-Essentials==6.12.0` (not the `PySide6` meta package) | Meta package drags in Addons + WebEngine (Chromium); Essentials is enough for Widgets and keeps the bundle ~150 MB and free of network-capable modules | D |
| D17 | Git access for baselines/history (M5) uses pure-Python `dulwich`, not a system `git` | Locked-down workstations may lack git; rule 10 (no compiler). Revisit in M5 spike | D |
| D18 | Linux hosts need system Qt libs (libEGL, libGL, libxkbcommon, fontconfig, dbus) — listed in the install notes and CI | Qt xcb/offscreen platform plugins link against them; not pip-installable | D |
| D19 | Installer in M0 is a PyInstaller one-folder portable build (no admin); MSI/NSIS/`.run` wrappers are M6 | Smallest thing that satisfies "portable build" now | D |
| D20 | Config validation uses pure-Python `fastjsonschema` (draft-07), not `jsonschema` | `jsonschema>=4.18` needs the compiled `rpds-py`; rule 10 | D |
| D21 | `rvs-project.yaml` at the project root declares documents (prefix, kind `requirements`/`verification`, title, parent) and free attributes; `config/*.yaml` (numbering, vocab, templates, rules, exports, standards) are copied from packaged defaults at project creation, and packaged defaults are used (with an info finding) when a file is missing | Doorstop cannot store document kind (V08); keeps rules in project config (rule 22) | D |
| D22 | Verification items use `verify_method`/`verify_level` (same names as requirements), status is `v_status`. `level` is unusable: Doorstop reserves it | Name clash found in M1 (V10) | D |
| D23 | Missing `rvs_schema_version` is an error in config files and a warning on items (item treated as current); unknown extended attributes are warnings; vocabulary and type violations are errors | Plain-Doorstop items stay loadable, bad data stays visible | D |
| D24 | `rvs validate` exit codes: 0 ok (warnings allowed), 1 errors (or warnings with `--strict`), 3 project cannot be loaded (missing, newer schema, invalid config, unloadable tree); 2 is argparse usage | Stable codes for CI | D |
| D25 | Doorstop's "unreviewed changes" warning is reported as info (`DOORSTOP-UNREVIEWED`) | Every new draft item triggers it; would drown real findings | D |
| D26 | `priority` vocabulary (high/medium/low) and the vague-word list are seeds marked `TODO-COMPANY` | Spec gives no values; not from a standard | D |
| D27 | Large-project speed: persistent mtime-keyed index cache inside the project folder (`.rvs-cache/`, gitignored), built via the Doorstop API; scheduled for M3 | M1 spike: 5,000 items read in 4.4 s, validate 15.6 s, dominated by Doorstop's pure-Python YAML parsing | D |
