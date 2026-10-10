# Post-v1 additions demo note

> **Point-in-time snapshot.** Written when this milestone was finished: test counts, timings, caveats and command forms were true then and are not updated. For the current state see the user guide, `docs/DECISIONS.md`, `docs/DEVIATIONS.md` and `docs/RELEASE.md`.


```
rvs export examples/satellite300 --reqif -o satellite.reqif          # exchange file for other tools
rvs import my-project customer.reqif --document SYS --map "Customer Ref=source" --dry-run
rvs-studio   ->  View > Theme > Dark ;  File > Export… > ReqIF exchange file ;  File > Import Items… (*.reqif)
python scripts/build_screenshots.py                                  # regenerates the guide's pictures
```
What works
- **ReqIF 1.x**: export (specifications by document, objects with all template attributes, parent and typed-link relations, XHTML plus lossless Markdown statement) and import through the same dry run, checks, history and reasons as CSV/XLSX. RVS -> ReqIF -> RVS is lossless (unit and Hypothesis tests, satellite300 round trip); a hand-written foreign file covers name matching, `--map`, ID assignment and level derivation. DOCTYPE/entity declarations are refused.
- **Dark theme** (also "follow the system"): Carbon g100 palette, tokens for every colour, WCAG AA contrast tests, switchable at run time, remembered.
- **Guide screenshots** (7 images from the fictional example) and a help viewer that follows the theme.
- **Cold open of 5,000 items 6.6 s -> 2.0 s** (libyaml C parser; frozen build 2.6 s); warm open 0.6 s, one edit 0.6-0.7 s.
- Found on the way: a hand-edited item file with broken YAML crashed validation; it is now `RVS-ITEM-UNREADABLE`.
- `rvs selftest` also checks a ReqIF round trip and reports which YAML parser is active.

Quality: 488 tests green on Python 3.11, 3.12 and 3.13; ruff and mypy clean; golden manifests include `project.reqif`.

Caveats
- ReqIF files could not be validated against the official XSD offline (V16); `.reqifz` archives, embedded files and images are not handled.
- Windows is still untested (V22).
