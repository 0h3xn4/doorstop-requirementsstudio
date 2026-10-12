# Pre-release audit: Adapter, configuration, editing service

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

Scratch dir with every probe script (p1.py ... p24.py), the mutation harness (mut.py) and logs (mut1.log, mut2.log):
`<scratch>/core-data/`
(run a probe with `./run.sh pNN.py` from there; `run.sh` sets `RVS_CONFIG_DIR`, `QT_QPA_PLATFORM` and a timeout).

## Coverage
Files read in full: src/rvs_core/__init__.py; adapter/{__init__,_offline_guard,cache,doorstop_adapter,model}.py; atomicio.py;
attrtypes.py; authoring.py; csvsafe.py; findings.py; glossary.py; project.py; project_templates.py; textcheck.py;
userconfig.py; schema/{__init__,versioning}.py; config/{__init__,loader,model,schema}.py; all 9 config/defaults/*.yaml;
all 10 config/schemas/*.json. Also read: CLAUDE.md, ARCHITECTURE, DEVIATIONS, DECISIONS, SPEC, AUDIT, the installed
Doorstop 3.2 sources that the monkey patches touch (common.py, core/base.py, core/item.py, core/document.py).
Tests read and judged: test_adapter, test_cache, test_config, test_authoring, test_schema_versioning, test_userconfig,
test_yaml_loader, test_project_templates, test_glossary, test_findings, test_small_findings, test_review_core,
test_audit_core (adapter/cache/atomic/include/alias-bomb/line-ending parts), test_review_io (csvsafe part).

Probes run (one line each; all against copies of examples/minimal10 in the scratch dir):
- p1/p1b/p10: item YAML oddities (BOM, CRLF, tabs, duplicate key, empty, non-UTF-8, directory in place of file, 70 MB, NUL, top-level scalar/list, wrong types, bad date/level/links) and C-vs-Python loader differential over 40 constructs.
- p2/p13: userconfig with HOME unset and no passwd entry (mocked), corrupt/hostile settings.json (13 shapes), directory as settings.json, relative XDG.
- p3/p16/p19: signed cache: corrupt key file, empty key file, same-size same-mtime edit, non-dict/deep/huge cache JSON, `.rvs-cache` as a symlink.
- p4: 50 tricky strings (NEL, CRLF, lone CR, U+2028, emoji, YAML-significant text, 100 kB) through EditService text/title and read back.
- p5: atomicio: symlink, dangling symlink, mode kept, new-file mode, 250-char name, directory target, CRLF handling, hard link.
- p6/p12/p24: EditService: None values, rvs_schema_version=99, lone surrogate in `why`, NUL in user, duplicate parents, empty text, bool-as-int, vocabulary, IDs with newline/lowercase/Arabic digits/traversal, SYS-7 vs SYS-0007, 3 threads creating items.
- p7/p18: project templates: 14 unusual project names, root is a file, folder with only `.git`, only `.DS_Store`, template traversal, symlinked root, prefixes S2/A1B2/X.
- p8/p21/p22/p23: config: trailing-newline patterns, alias bomb in config, dir in place of config file, duplicate key, template/link/default cross-references, BOM/CRLF/UTF-16, parent cycles, `!include` guard bypass, alias bomb in `.doorstop.yml`.
- p9: alias bomb through get_item / EditService.update_item (hang).
- p11: item file names (unicode digits, spaces, .YML, .yaml, SYS-7, 00008, huge number, dot-prefixed, .tmp, .bak).
- p14/p17/p20: offline guard module list; relative/symlinked/`..` project roots; duplicate/missing/undeclared/broken document folders.
- p15: glossary regex speed on pathological text; csvsafe against 20 trigger/lookalike strings.
- CLI: `rvs import --reason $'caf\xe9'`; `rvs init <cloned repo> --git`; `rvs baseline create` with `promote_on_baseline: {approved: bogus}`; `rvs validate` with the include bypass.
- Mutation probes (19 one-line defects, mut.py): 8 survived (listed under CORE-DATA-17).
Tests run: test_adapter, test_cache, test_config, test_authoring, test_schema_versioning, test_userconfig, test_yaml_loader,
test_project_templates, test_glossary, test_findings, test_review_core: 99 passed (21 s). Plus the targeted subsets of
test_audit_core / test_small_findings / test_review_io / test_baselines / test_change_requests inside the mutation runs.

## Findings

### CORE-DATA-01 `!include` guard in `.doorstop.yml` can be bypassed: local files are read into findings
- Where: src/rvs_core/adapter/doorstop_adapter.py:145-163 (`_custom_tags`), called from `_refuse_includes` (:129)
- Severity: high
- Confidence: verified (reproduced, also through the CLI)
- What is wrong: the guard composes the document config with libyaml's `CSafeLoader`. Doorstop itself loads `.doorstop.yml` with its own pure-Python `IncludeLoader` (a `yaml.SafeLoader` subclass, core/document.py `_load_with_include`). When the C composer raises a `YAMLError`, `_custom_tags` falls back to `"%TAG" in text or "!<" in text`. A file that the C parser rejects but the Python parser accepts (for example `zz: "\ud800"`, a lone-surrogate escape) skips the tag walk. If the include tag is then spelled with a percent escape (`!inc%6Cude`, decoded by the scanner to `!include`) neither substring test matches, the guard passes, and Doorstop reads any local file the user can read. This re-opens the hole that docs/AUDIT.md lists as fixed ("`!include` guard was a substring test").
- Evidence: `EPS/.doorstop.yml` edited to `sep: !inc%6Cude ../../secret.txt` plus a line `zz: "\ud800"` (probe p22.py):
  ```
  plain !include                       REFUSED: EPS/.doorstop.yml uses a custom YAML tag such as '!include' ...
  escaped tag alone                    REFUSED: ... custom YAML tag ...
  escaped tag + C-breaking surrogate   OPENED; sep= 'TOPSECRET-VALUE-123'
     "Document EPS numbers items with separator 'TOPSECRET-VALUE-123' and 4 digits, but config/numbering.yaml requires '-' ..."
  ```
  CLI: with `sep: !inc%6Cude /etc/hostname` and the surrogate line, `rvs validate w/inc2` prints `... separator 'vm' ...` (content of /etc/hostname).
- Why it matters: a project from a zip/clone can exfiltrate any readable file (YAML-parseable content, first scalar) into findings, the GUI Problems panel and exported reports; this is the exact threat the guard exists for.
- Proposed fix: compose with the same loader Doorstop uses (`yaml.SafeLoader`), and if composing fails for ANY reason raise `ProjectError` (never fall back to a substring test); optionally also refuse a non-standard tag in a second pass with the C loader.
- Test that would catch it: copy of `test_include_cannot_be_smuggled_in_through_a_tag_handle` with `!inc%6Cude` and an extra `x: "\ud800"` line; assert `ProjectError` and that the secret is not in any finding.

### CORE-DATA-02 A lone surrogate (or any unencodable character) in the reason/user is detected only AFTER the item file was changed; the edit then has no history
- Where: src/rvs_core/authoring.py:79-97 (`record`), :126-150 (`_check_values` only checks statement and attribute values, never `why` or `user`)
- Severity: medium
- Confidence: verified
- What is wrong: `update_item` writes the item, then `record()` opens the history file and writes the JSON line with `ensure_ascii=False`; a `why` containing a lone surrogate raises `UnicodeEncodeError` at that point. On Linux, command-line arguments that are not valid UTF-8 arrive as lone surrogates (`\udce9`), so this is reachable with `--reason`. The item stays modified, the history file is created empty, and the user gets a codec message. The existing test `test_a_failing_history_write_leaves_the_item_unchanged` only covers an unusable history folder (fail before writing), not a failure of the write itself.
- Evidence:
  ```
  $ LC_ALL=C PYTHONUTF8=0 rvs import w/imp w/items.csv --reason $'caf\xe9'
  row 8 update SYS-0001 owner ... (6 rows planned)
  rvs import: 'utf-8' codec can't encode character '\udce9' in position 105: surrogates not allowed   (exit 2)
  $ grep owner w/imp/SYS/SYS-0001.yml   ->  owner: SYSTEMZ        (item changed)
  $ cat w/imp/history/SYS/SYS-0001.jsonl  ->  (empty file)
  ```
  API: `EditService(d,user="t").update_item("SYS-0001", attrs={"owner":"zed"}, why="bad \ud800 char")` -> UnicodeEncodeError, `owner: zed` is in the file, `read_history` returns `[]` (probe p6.py). The import stops after the first row, leaving the rest unapplied.
- Why it matters: the spec's accountability rule (who/when/why for every edit, mandatory reason for baselined items) is broken: a change without a record, plus a half-applied import and a non-actionable message.
- Proposed fix: in `_check_values` (and `set_parents`/`clear_suspect`) run `textcheck.check("reason", why)` and `check("user", self.user)` before any write; better, serialise the history entry (`json.dumps(...).encode("utf-8")`) before the item is written and only then write both.
- Test that would catch it: `update_item(..., why="x\ud800")` raises `ValueError` and leaves the item file byte-identical; same for the CLI import with a non-UTF-8 `--reason`.

### CORE-DATA-03 A `.rvs-cache` that is a symbolic link makes RVS write requirement text and overwrite files outside the project
- Where: src/rvs_core/adapter/cache.py:111-136 (`ItemCache.save`); contrast baselines.py `snapshot_dir`, which does refuse a symlinked cache folder
- Severity: medium
- Confidence: verified
- What is wrong: `save()` only does `self.dir.mkdir(exist_ok=True)` and writes `.gitignore`, `.doorstop.skip-all` and `<PREFIX>.json` (via `os.replace`, so an existing file of that name is replaced) through whatever the link points to. A project that arrives as a zip or Git clone can ship `.rvs-cache -> /some/folder` (symlinks survive both; the cache folder is only git-ignored if the project's own .gitignore says so).
- Evidence (probe p19.py): `.rvs-cache` symlinked to `w/outside/` containing a file `SYS.json` ("victim file"); after `DoorstopProject.open(d).items()` the folder holds `['.doorstop.skip-all', '.gitignore', 'EPS.json', 'SYS.json', 'VER.json']` and `SYS.json` now starts with `{"v": 3, "config": [...], "items": {"SY...` (victim content gone, requirement text written there).
- Why it matters: spec rule 11 (never write project content outside the project folder) and an arbitrary-directory file overwrite (names limited to `<PREFIX>.json`, `.gitignore`, `.doorstop.skip-all`) driven by an untrusted project.
- Proposed fix: in `ItemCache.save`/`load` return without caching when `self.dir.is_symlink()` (and resolve-check that `self.dir.resolve()` stays inside the project root), the same guard as `snapshot_dir`.
- Test that would catch it: project with `.rvs-cache` symlinked elsewhere; assert nothing is written to the target and items still load.

### CORE-DATA-04 A damaged or foreign cache file can make the project unopenable, with a message that blames the item files
- Where: src/rvs_core/adapter/cache.py:98-109 (`ItemCache.load` catches only OSError, ValueError, KeyError, TypeError, IndexError)
- Severity: medium
- Confidence: verified
- What is wrong: valid JSON that is not an object (`null`, `123`, `"abc"`) raises `AttributeError` at `raw.pop(...)`, and deeply nested JSON raises `RecursionError`; neither is caught. They surface in `DoorstopProject.items()` as `UnreadableItemError`: "An item file has content RVS cannot read (AttributeError)". The hint says "Fix the YAML syntax of the file named above", but no file is named. The failure persists on every open until the user happens to delete `.rvs-cache/`. The whole point of the signed cache was that foreign or damaged caches are "ignored".
- Evidence (probe p16.py/p16b.py): cache file content `123`, `null`, `"abc"`, 200000 nested `[` or `{"a":` -> `validate_project(...).exit_code == 3`; message `RVS-ITEM-UNREADABLE ... (AttributeError)` / `(RecursionError)`. `rvs validate w/cj` prints the same.
- Why it matters: unopenable project from a cache that is supposed to be disposable; misleading hint.
- Proposed fix: widen the `except` to `Exception` (or add AttributeError and RecursionError) and verify `isinstance(raw, dict)` first.
- Test that would catch it: write each of those contents to `.rvs-cache/SYS.json` and assert `items()` still returns 10 items.

### CORE-DATA-05 `rvs init --git` (and the GUI option) fails after writing the project when the folder already holds a `.git` (a fresh clone)
- Where: src/rvs_core/project_templates.py:76-80 (`create_from_template`); GitRepo.init in src/rvs_core/vcs/git.py
- Severity: medium
- Confidence: verified
- What is wrong: the emptiness check deliberately ignores `.git` (so cloning an empty repository and initialising a project in it is meant to work), but `GitRepo.init(root)` then raises `FileExistsError` because `.git` exists. By that time `create_project` has already written everything.
- Evidence:
  ```
  $ git init -q w/clone ; rvs init w/clone --name Demo --git
  rvs init: [Errno 17] File exists: 'w/clone/.git'          (exit 2)
  $ ls -a w/clone  ->  .git SUB SYS VER config rvs-project.yaml     (project WAS created)
  ```
  A retry now says the folder already contains an RVS project; the same happens with an empty `.git` directory (probe p7.py).
- Why it matters: the documented workflow "create repo, clone, init project" reports a failure for a successful creation, and the raw errno text is not actionable.
- Proposed fix: skip `GitRepo.init` when `GitRepo.discover(root)` already finds a repository (or check before writing anything and say so).
- Test that would catch it: `git init` a folder, `create_from_template(..., git=True)` must succeed and not raise.

### CORE-DATA-06 `userconfig` and the cache key crash when the home directory cannot be determined; validation then fails with a wrong explanation
- Where: src/rvs_core/userconfig.py:22-30 (`config_dir`, `Path.home()`), :36-60 (`load`/`save` catch only OSError/ValueError); src/rvs_core/adapter/cache.py:31-37 (`_key` calls `config_dir()` outside its try)
- Severity: medium
- Confidence: verified (with `pwd.getpwuid` mocked to raise KeyError and HOME/XDG/RVS_CONFIG_DIR unset; the real case is a container or CI job run as a numeric uid with no passwd entry and no HOME)
- What is wrong: `Path.home()` raises `RuntimeError("Could not determine home directory.")`. The module docstring promises "never raises", yet `load()`, `save()` and, worse, `cache._key()` all raise it.
- Evidence (probe p2.py):
  ```
  config_dir EXC RuntimeError Could not determine home directory.
  load EXC RuntimeError ...    save EXC RuntimeError ...
  validate exit 3
  ERROR RVS-VALIDATION-FAILED: Validation stopped unexpectedly (RuntimeError). A file with content RVS cannot interpret is the usual cause.
  ```
  `rvs validate` exits 3 for a perfectly good project.
- Why it matters: `rvs validate` is meant for CI; locked-down runners often have no HOME.
- Proposed fix: catch `RuntimeError` in `config_dir()` and fall back (for example the system temp folder is not allowed by rule 11, so return None and let `load` give defaults, `save` do nothing, `_key` return None = no cache).
- Test that would catch it: monkeypatch `Path.home` to raise `RuntimeError` with the env vars cleared; `validate_project(minimal)` must return exit code 0.

### CORE-DATA-07 Two concurrent creators of an item in the same document can both "succeed" and one new requirement is silently lost
- Where: src/rvs_core/authoring.py:152-172 (`create_item`), adapter `add_item` (:403) via Doorstop's check-then-write (`item already exists`); V29 documents lost updates of existing items, not lost creations
- Severity: medium
- Confidence: verified (threads, each with its own `EditService`/`DoorstopProject`; the race is the same across processes)
- What is wrong: Doorstop picks the next number from the directory listing and checks `exists()` before writing; between the two steps another creator can pick the same number, and RVS replaces the file with `os.replace`. Both calls return a valid `ItemData`, both write a history record, one item no longer exists.
- Evidence (probe p24.py, 3 threads x 4 creations): `created 9 unique uids 8` (nine successful returns, two with the same UID), `survivors 8 of 9`; other calls failed with `item already exists`.
- Why it matters: silent loss of a newly entered requirement with a success message; a GUI plus a CLI import on one project, or two people on a shared folder, are enough.
- Proposed fix: create the item file with exclusive creation (`os.open(..., O_CREAT|O_EXCL)`) and retry with the next number on `FileExistsError`; keep `os.replace` only for updates.
- Test that would catch it: N threads x M `create_item` calls; assert N*M distinct UIDs and N*M files.

### CORE-DATA-08 Configuration cross-references are not validated; typos produce silent behaviour or an immutable wrong baseline
- Where: src/rvs_core/config/loader.py:108-190 (`load_project_config`) and the schemas (only structure is checked)
- Severity: medium
- Confidence: verified (baseline case), verified for the others
- What is wrong: nothing checks that
  - `changes.promote_on_baseline` keys/values are in `vocab.status` (verified: with `promote_on_baseline: {approved: bogus}`, `rvs baseline create w/promo B1 -m test --init-git` exits 0, rewrites `status: approved` to `status: bogus` inside the baseline commit; afterwards `RVS-ATTR-VOCAB ... 'status' of SYS-0001 is 'bogus'`; the baseline name is burned and immutable);
  - `rules.change_control.reason_required_statuses` values exist in `vocab.status` (a typo such as `baseline` silently disables the "reason is mandatory once baselined" control for status-based detection);
  - `templates.*.defaults` keys are template attributes with valid values (`defaults: {status: bogus, zzz: 1}` loads without a finding and is applied to new items by `create_item`, which skips `_check_values` for defaults);
  - `links.types.*.attribute` exists in the templates (`link_refines` renamed to `link_bogus` loads cleanly and the link type becomes uneditable);
  - duplicate keys in a config file: `numbering.yaml` with `digits: 4` and a later `digits: 9` loads with 9 and no finding (items do get `RVS-ITEM-DUPLICATE-KEY`; config files do not).
- Evidence: probes p8.py ("bad defaults", "link attr not in templates", "dup key digits") and the CLI baseline run above.
- Why it matters: the spec says rules and vocabularies live in config; a one-letter typo should be a config error, not a permanent bad baseline.
- Proposed fix: add the checks in `load_project_config` (all are set comparisons); detect duplicate mapping keys with a small custom `SafeLoader` for config files.
- Test that would catch it: one test per bullet expecting `ConfigError` (these checks are untested today; see CORE-DATA-17).

### CORE-DATA-09 "Item file cannot be read" does not name the file for the common hand-edit mistakes
- Where: src/rvs_core/adapter/doorstop_adapter.py:314-324 (`items`) and :357-361 (`obj.active` is evaluated before the per-file `try`)
- Severity: medium
- Confidence: verified
- What is wrong: the per-file message ("<path> has content RVS cannot read ...") only exists around `_data(obj)`. The first access, `obj.active`, loads and parses the file outside that block, so a wrong type, impossible date or bad level reaches the generic handler: "An item file has content RVS cannot read (ValueError). Check the most recently edited item files." The finding has `location=""` and `uid=""` and its hint says "the file named above", which is not named. For non-UTF-8 files the message prints the absolute path of the scratch folder instead.
- Evidence (probe p1b.py): `executed_on: 2024-13-45`, `text: [a, b]`, `level: abc` each give exactly that generic message with empty location; NUL byte and non-UTF-8 give a Doorstop message containing the absolute path and a codec text.
- Why it matters: spec rule 19 (what is wrong, where, what to do, with a jump link) for the most likely failure class (hand edits); on a 5,000-item project the user must bisect by hand.
- Proposed fix: move `obj.active` inside the per-file `try` and raise `UnreadableItemError` with the relative path; also set `location` on the finding.
- Test that would catch it: item with `level: abc`; assert the message contains `SYS/SYS-0001.yml`.

### CORE-DATA-10 EditService accepts values that break the item or the whole project
- Where: src/rvs_core/authoring.py:126-150 (`_check_values`), :174-203 (`update_item`)
- Severity: low
- Confidence: verified
- What is wrong:
  - `attrs={"status": None}` (or `""`) skips every check (`value not in (None, "", [])`) and is written: `status: null`, a required enum cleared (`RVS-ATTR-REQUIRED` only appears at the next validate). The `required` flag of the template is never enforced by the service (also not in `create_item`: `create_item("SYS","hello")` creates an item without title/type/status).
  - `rvs_schema_version` is a template attribute (type int), so `attrs={"rvs_schema_version": 99}` is accepted; the next `validate_project` returns exit 3 with `RVS-SCHEMA-NEWER` for the whole project. The GUI hides the field but the service is the shared gate.
  - `set_parents(uid, ["A","A"])` is "changed" (the sorted list differs from the stored one) and appends a history entry each time although nothing changes.
  - typed-link attributes accept self links and non-existent IDs (the rule engine reports them later).
- Evidence: probe p6.py outputs `['status: null']` + `RVS-ATTR-REQUIRED`; `schema ver 99 -> ok` then `after: 3 [('RVS-SCHEMA-NEWER', ...)]`; `hist entries 2` after two identical `set_parents` calls.
- Proposed fix: reject None/"" for `required` attributes, exclude `rvs_schema_version` (managed field) like Doorstop's own fields, compare `sorted(set(parents))`.
- Test that would catch it: the three calls above must raise `ValueError` / not append history.

### CORE-DATA-11 `get_item` / `EditService.update_item` have no alias-bomb or size guard (hang)
- Where: src/rvs_core/adapter/doorstop_adapter.py:275-310 (`_item`, `_data`); the guard `_scan_item` runs only inside `_items_of`
- Severity: low
- Confidence: verified
- What is wrong: an item whose YAML aliases expand exponentially is refused by `items()` ("uses YAML aliases that expand to an unreasonable size") but `get_item()`/`update_item()` go straight to `_data()` -> `_plain()`, which walks the expanded structure.
- Evidence (probe p9.py, 10 levels of 9-way aliases): `items() UnreadableItemError ... 0.0 s`; `get_item HANG >15s`; `EditService.update_item HANG >15s`. Normally the GUI lists first, so this needs the file to change after the project was opened (or a CLI import that does not list first).
- Also: the 64 MB size check in `_scan_item` runs after Doorstop already parsed the file (`obj.active` earlier in the same loop), so it limits later work, not parsing time or memory.
- Proposed fix: call `_scan_item` (size first, then expansion) from `_item()` before `item.load()`, and in `_items_of` before `obj.active`.
- Test that would catch it: the existing alias-bomb test, but through `get_item` with a 5 s alarm.

### CORE-DATA-12 U+0085 (NEL) in text or attributes is silently turned into a line break/space
- Where: src/rvs_core/textcheck.py:10 (`_BAD` set) with Doorstop's YAML dump/load
- Severity: low
- Confidence: verified
- What is wrong: PyYAML emits U+0085 unescaped and reads it back as a line break. `textcheck` does not reject it. Of 50 tricky strings only this one (and CRLF -> LF normalisation, which is expected) did not survive a write/read round trip.
- Evidence (probe p4.py): statement `...shall a\x85b end.` reads back as `a\nb`; title `a\x85b` reads back as `a b`.
- Why it matters: content changed without a message (Word and PDF paste can contain NEL). Spec rule 14 (round trip lossless).
- Proposed fix: add `\x85` to `_BAD` (message already says "control character") or replace it by a space on input.
- Test that would catch it: a round-trip test over a list of unusual characters (none exists for the service).

### CORE-DATA-13 Items are parsed with libyaml, `.doorstop.yml` with the Python loader: tab after a colon is accepted by RVS and rejected by Doorstop
- Where: src/rvs_core/adapter/doorstop_adapter.py:45-46 (V26 patch of `load_yaml.__defaults__`); tests/test_yaml_loader.py
- Severity: low
- Confidence: verified
- What is wrong: a differential run (probe p10.py) over 40 constructs found three differences between `SafeLoader` and `CSafeLoader`: `a:\t1` and `a: [1,\t2]` parse with the C loader and raise `ScannerError` with the Python loader; `"\ud800"` escapes parse only with the Python loader. The patch only affects calls that use `load_yaml`'s default loader, so `.doorstop.yml` (explicit `IncludeLoader`) stays on the Python parser. An item written with a tab after the colon is therefore read by RVS but fails in plain `doorstop` (spec: the folder must stay a valid Doorstop tree) and in `config/*.yaml` (which RVS reads with the Python `yaml.safe_load`). `test_tricky_scalars_are_read_alike` has no tab case.
- Proposed fix: add the tab cases to the test; optionally have `_scan_item` (which already composes each new item) also compose with the Python loader and emit a finding when the two disagree.
- Test that would catch it: parametrised equal-or-both-fail assertion over the three constructs.

### CORE-DATA-14 Item file names: digit count not enforced, near-miss file names silently ignored
- Where: src/rvs_core/validate.py:123 (`RVS-ITEM-NAME` regex `prefix + sep + [0-9]+`); adapter `_item_files`
- Severity: low
- Confidence: verified
- What is wrong: `SYS-7.yml`, `SYS-00008.yml` and `SYS-9999999999999999999999.yml` are accepted as items of a 4-digit document; `SYS-7.yml` and `SYS-0007.yml` coexist as two different items and no finding is produced (only `DOORSTOP-WARNING duplicate level` when levels clash). `SYS-0007.yaml`, `SYS-0005.YML` and `SYS-0012.yml.bak` are not items to Doorstop and RVS gives no hint, so a requirement file with a wrong extension disappears silently. (Non-ASCII digits, trailing newline, lowercase prefix and underscore separator are correctly flagged.) The same ID pattern is defined four times (attrtypes.py:7, validate.py:35, exporters/reqif.py:35, exporters/itemsio.py:35) and a fifth, looser one (`itemsio._LEVEL = ^\d+(\.\d+)*$`) accepts non-ASCII digits.
- Evidence: probes p11.py/p12.py: `[('SYS-0007','Seven long'), ('SYS-7','Seven short')]`, findings contain no ITEM-NAME entry.
- Proposed fix: require `[0-9]{digits}` (or at least `doc.digits` zero-padded) in the check; add an info finding for `*.yaml`/`*.YML` files in a document folder; import the single `attrtypes.UID`.
- Test that would catch it: file `SYS-7.yml` in a 4-digit document -> `RVS-ITEM-NAME`.

### CORE-DATA-15 Atomic-write details
- Where: src/rvs_core/atomicio.py:10-23; src/rvs_core/adapter/doorstop_adapter.py:109-123
- Severity: low
- Confidence: verified for the name limit and the duplication; reading-only for the other two
- What is wrong:
  - `atomicio.write_bytes` builds `.<name>.<pid>.<tid>.tmp` next to the target, so a target name above ~230 characters fails with `OSError: File name too long` although it could be written directly (probe p5.py, 250-character name). Rare but reachable for exports named after long titles.
  - The adapter's `_atomic_write_text` has no `flush`/`fsync` before `os.replace` (atomicio has), so "a crash never leaves a half-written item" does not hold for power loss on file systems that do not order data before rename. Two near-identical implementations also exist (atomicio and the adapter), with different temp-file naming.
  - Because the new file is renamed over the old one, a file the user made read-only (`chmod a-w`, or in a read-only baseline checkout) is replaced without error on POSIX; with Doorstop's own `open(path, "w")` it failed. On Windows `os.replace` raises `PermissionError` when anti-virus, an editor or Git holds the item open, and neither path retries (reading-only; Windows untested, see DEVIATIONS V22).
  - `glossary.save_glossary` (called from the GUI) and `project.create_project` still use plain `Path.write_text`: a full disk truncates `config/glossary.yaml`, after which the whole project is unreadable (`must contain a mapping`). Not atomic although AUDIT.md lists "exports and user settings" only.
- Proposed fix: use `atomicio.write_text` in `save_glossary`; share one implementation; add a short retry on `PermissionError` for Windows; document the read-only behaviour.

### CORE-DATA-16 Signed-cache details
- Where: src/rvs_core/adapter/cache.py:31-67
- Severity: low
- Confidence: verified (a, b), reading-only (c, d, e)
- What is wrong:
  - (a) a `cache.key` that exists but is not hex (`ValueError` in `bytes.fromhex`) sets the key to None for the whole process and is never repaired: the cache is disabled forever and silently (probe p3.py: `corrupt key: hits 0 misses 10`, file unchanged). The `len(key) < 16` repair branch exists but is unreachable for non-hex content.
  - (b) key creation is not race-free: `O_TRUNC` followed by the write lets a second thread/process read an empty file, conclude "no key" and generate another one; then each uses a different key and the cache files signed by the loser are rejected on the next run (self-healing, one cold open). `_KEYS` is a plain dict without a lock and is used from worker threads.
  - (c) the signature covers neither the project path nor the prefix: a `SYS.json` from another project of the same user whose item files carry identical (mtime_ns, size) is accepted. Practically only reachable with `cp -a`/`rsync -a` copies.
  - (d) the validity test is `(mtime_ns, size)` equality, so a deliberate same-size edit with the mtime restored (`touch -r`) is served stale (probe p3.py: `same-mtime edit visible: systems`). The `.doorstop.yml` key has no 2-second "racy" rule at all, which matters on 1-2 s timestamp file systems (FAT/exFAT, some shares).
  - (e) the key is per user, the cache is per project: on a shared project folder, each user's cache invalidates the other's, so every open is cold. `docs/user-manual/09-settings-modes-shortcuts.md` lists the contents of the user configuration folder but not `cache.key` (a secret that would be copied by a dotfile sync).
- Proposed fix: regenerate the key when it does not decode, create it with `O_EXCL` and re-read on `FileExistsError`, guard `_KEYS` with a lock, mention `cache.key` in the docs; consider adding the relative project path to the signed payload.

### CORE-DATA-17 Test gaps found by mutation probes (19 one-line defects; 11 caught, 8 survived)
- Where: tests for csvsafe, atomicio, config/loader, authoring
- Severity: medium (these guard the formula-injection defence, change control and config integrity)
- Confidence: verified (mutations run on a copy under `.../core-data/mut/src`, targeted test files only; results in `mut1.log`, `mut2.log`)
- Survivors (nothing failed):
  1. `csvsafe._TRIGGER`: removing `\t\r` from the trigger class. `test_csv_cells_that_excel_would_run_are_protected...` only tries `= + - @`; tab and CR are in the docstring but untested.
  2. `atomicio.write_bytes`: deleting the `tmp.chmod(...)` that keeps the file mode (the only test of permissions exercises the adapter's own writer; settings and every export go through atomicio).
  3. `config/model.check_document_tree`: removing the parent-cycle check (would loop forever); no test has a cycle.
  4. `config/loader`: removing the "fingerprint attribute not in attributes" check.
  5. `config/loader`: removing the "enum attribute uses unknown vocabulary" check.
  6. `config/loader`: removing the "open_statuses/deferred_status not in statuses" check.
  7. `authoring._check_values`: removing the "value not in the vocabulary" check (`test_type_checks_apply_to_edits` has no enum case).
  8. `adapter` `_settings.WRITE_LINESEPERATOR = "\n"` pin: cannot fail on Linux (Doorstop's default is already `\n`); only the Windows CI job can catch it. Equivalent on this platform.
- Also without any unit test: `textcheck` (only reached indirectly), `userconfig` with an unavailable home, `project_templates` with names/odd folders, `glossary.save_glossary`, `findings.Finding.to_dict`.
- Caught (good): forged cache signature, "never racy", textcheck U+000B, reason for baselined uid and for baselined status, user theme validation, newer schema version, include guard (plain/%TAG), link stamping on `link()`, type check, parent-document check, acronym ID lookahead.

### CORE-DATA-18 Smaller items (low)
- `create_project` (project.py:39-52) loops forever if a document's `parent` is not in the list or the list is cyclic (`while remaining:`); only internal callers with fixed lists exist (reading-only).
- Windows device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`, `LPT1`) match the document prefix pattern `^[A-Z][A-Z0-9]*$` and become folder names; baseline names are checked against them, prefixes are not (reading-only).
- `rvs-project.yaml`/config `rules` `params` accept unknown keys, `rules[].id` is not checked against known rule IDs, `rules` ids may repeat (typos silently ignored; reading-only, belongs to the rules slice).
- A directory in place of a config file (`config/vocab.yaml/`) is reported as "not found; using the packaged default" (INFO) rather than an error (probe p8.py).
- `standards.yaml` placeholder with `status: resolved` and `value: null` is accepted and drops out of `unresolved()`.
- `cache.py` `ItemCache.save`: `.gitignore`/`.doorstop.skip-all` are only created when missing; if the user deletes `.gitignore` inside `.rvs-cache`, requirement text can be committed (the project `.gitignore` is not touched).
- Following symbolic links: an item file that is a symlink to a file outside the project is rewritten through the link on edit (intended by the earlier audit for links inside a checkout, see QUESTIONS).

## Checked and found correct
- Offline guard: after importing adapter, validate, authoring, project_templates and config, no `socket`, `ssl`, `http`, `urllib.request`, `urllib3`, `requests` or `asyncio` is loaded; `bottle`/`plantuml_markdown` are the inert placeholders.
- Doorstop patches (V26): `write_text` is replaced and used by `Item`/`Document` saves (Doorstop 3.2 calls `common.write_text` through the module); `load_yaml.__defaults__` applies to item loads; `.doorstop.yml` keeps the Python loader. Saves keep LF, keep file mode, follow symlinks, leave no `.tmp` on failure.
- Item YAML: BOM, CRLF, tabs in values, duplicate key (reported), empty file (required-attribute errors), non-UTF-8, NUL, directory in place of file, 70 MB file (refused), top-level scalar/list, wrong types, bad date/level are all reported as findings or exit 3 without a traceback (message quality: see -09).
- Alias bomb in an item file is refused quickly by `items()`; alias bomb in a config file's free-form `params` does not slow loading (schema does not walk it).
- Config: all nine default files validate against their schemas; unknown keys, wrong types, empty file, UTF-16, missing `rvs-project.yaml`, reserved attribute names, free attribute redefining a template attribute, duplicate prefix, two roots, parent cycles (real code), unknown parent are rejected with a message naming the file. JSON-schema patterns with `$` do NOT accept a trailing newline (`"SYS\n"` prefix, `"owner\n"` attribute, `"open\n"` status all rejected). BOM and CRLF config files load. Numbering override of digits is flagged on existing documents (`RVS-DOC-NUMBERING`).
- Item IDs: `attrtypes.UID` uses `\Z` and `[0-9]`; EditService rejects `SYS-0001\n`, lowercase, Arabic-Indic digits and traversal strings with `ProjectError`; `RVS-ITEM-NAME` flags non-ASCII digits, spaces, newline, `_` separator, dot-prefix.
- Prefixes `S2`, `A1B2`, `X` work end to end (create, link, edit, validate).
- Signed cache: forged text and forged signature ignored; truncated/garbage/`list`/oversized-int/bad-signature-type JSON ignored; racy files never cached; changed size or mtime reloaded; deleted item disappears; moved document folder recomputes paths; concurrent savers use per-writer temp names.
- atomicio: symlink target updated and link kept, dangling link handled, mode of an existing file kept, no temp file left on directory target or failure, CRLF normalised, relative paths.
- EditService: reason required for baselined status and for UIDs in a baseline manifest (both mutation-tested), failed edit leaves the file untouched (reason check precedes the write), type/vocabulary/field-name checks, parent must exist and sit in the parent document, history is JSONL with names only (no values), a damaged history line does not hide the rest, parent cycles cannot occur through `set_parents` (parents must be in the parent document).
- csvsafe: `= + - @ TAB CR` (also after leading apostrophes) are protected and round-trip losslessly; leading space, NBSP, fullwidth `＝`, `−`, `–`, BOM, ZWSP, RLO, NUL, LF, `|`, `%` are not formula starts in Excel and are left alone (checked 20 strings).
- glossary `_ACRONYM` is linear on pathological text (200 k characters: 0.02 s); userconfig survives 13 hostile settings.json shapes, a directory as settings.json and unserialisable data (`save` raises TypeError only for unserialisable input, which no caller produces).
- Project names with newline, colon, quotes, `!!python/...`, 5000 characters, NUL, lone surrogate and BOM round-trip through `create_from_template` and validate; template key traversal is refused; non-empty folder, existing project and symlink-to-project are refused.
- Relative, `..`, trailing-slash and symlinked project roots all open.
- Schema versioning: missing, bool, negative, newer, missing migration step all give the intended codes.

## Questions about intended behaviour
1. Should a symbolic link inside a project that points outside the project folder (an item file, `config/*.yaml`, `history/`) be followed on write? The earlier audit made item saves follow links on purpose; for a project from a zip/clone this means an edit can overwrite any YAML-parseable file the user can write. Is "inside the project" the intended boundary?
2. Is it intended that EditService/`create_item` lets a new item exist without its `required` attributes (title/type/status) and that `None`/`""` clears a required attribute? The GUI wizard presumably prevents it; the CLI import and API do not.
3. V29 says lost updates are accepted; is a lost CREATION (CORE-DATA-07) covered by that acceptance? I treated it as not covered because the caller gets a success and a history record for an item that no longer exists.
4. The per-user HMAC key (`cache.key`) makes caches on shared project folders useless across users. Is a shared project folder (network drive) a supported setup? If yes, a per-project key stored inside the project is not an option (forgeable), so the alternative is to document that each user pays the cold open.
5. Should `.doorstop.yml` and `config/*.yaml` be parsed with the same loader as the items (C) or should items be checked against the Python loader too (CORE-DATA-13)? Which behaviour is the contract: "valid for RVS" or "valid for plain Doorstop"?
6. `standards.yaml` `status: resolved` with `value: null` and `promote_on_baseline`/`reason_required_statuses` typos: should these be hard `ConfigError`s (my recommendation) or findings?


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
