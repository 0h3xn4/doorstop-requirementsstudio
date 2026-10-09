# Deviations from / limits of the base framework (Doorstop 3.2)

| # | Issue | Handling |
| --- | --- | --- |
| V01 | Doorstop 3.2 declares `requests`, `bottle`, `plantuml-markdown`, `verchew` as hard dependencies, and `doorstop.core.publishers.html` imports `bottle` at import time. Spec rule 3 says the offline test fails if *any* networking module is imported. | Offline test is split: (a) block socket creation process-wide (fails on any `socket.socket()` connect/bind); (b) assert no `rvs_*` module imports network modules directly; (c) an explicit, reviewed allow-list of Doorstop's transitive network imports. **Needs user sign-off** — a stricter alternative is lazily importing Doorstop publishers only, but `requests`/`bottle` still install. |
| V02 | Doorstop `links` can only point to parent-document items in validation. | Typed links are RVS extended attributes (D13), validated by RVS rules, not by Doorstop. |
| V03 | Doorstop extended attributes are not schema-typed. | RVS JSON Schema in `config/` validates them; the adapter coerces on read. |
| V04 | Doorstop has no baseline/change-request concept and writes no history. | Implemented in RVS on Git tags (D14, D15). Requires Git on the workstation (or bundled `dulwich`, pure Python — decide in M0). |
| V05 | Doorstop's `doorstop-server`/Tk GUI are not shipped or started. | Excluded from the PyInstaller bundle (`bottle` module still present for publishers). |
| V06 | Doorstop caches/`.doorstop` temp behaviour may write outside the project. | Adapter runs with `TMPDIR` pointed inside the project folder; verified by a test (spec rule 11). |
