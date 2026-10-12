# Pre-release audit: Baselines, change requests, diff, Git

Detailed report of one auditor (evidence, commands, mutation probes). The consolidated list is [AUDIT.md](../../AUDIT.md).

(Repository checked clean with `git status --short` after the audit; all mutations were done in a scratch copy `.../audit/changecontrol/mut`.)

## Coverage
Files read in full: src/rvs_core/changecontrol/{baselines,changes,diff,manifests,__init__}.py, src/rvs_core/vcs/{git,__init__}.py, src/rvs_cli/changecontrol.py, src/rvs_core/config/defaults/changes.yaml + schemas/changes.schema.json, config loader part for changes, docs/guide/04-change-control.md, docs/user-manual/06-change-control.md, relevant parts of authoring.py (EditService reasons), validate.py (baseline/CR section), cli/main.py export --baseline, adapter/cache.py (sign/verify); docs CLAUDE/ARCHITECTURE/DEVIATIONS/DECISIONS/SPEC/AUDIT. Tests read: test_baselines, test_vcs_git, plus names/key parts of test_review_cc, test_audit_core/gaps, test_diff, test_change_requests, test_cli_changecontrol.

Probes run (scratch copies of minimal10 / satellite300 / generated 5,000-item stress project):
- tamper matrix: edit working item; edit manifest (digest, CRLF, remove item, null/int `items`, bad `created`/`deferred_change_requests`); delete manifest; delete tag; lightweight tag (same commit / later commit); annotated tag re-created with copied message pointing to a tampered commit (item edit, add/delete item, config+history edit, parents change, reviewed/link-stamp change); edit the extracted snapshot cache; leaf-symlink planted in `.rvs-cache/snapshots`; inactive item tampering; project copied without `.git`; clone with/without tags; pack-refs/gc.
- names: ~35 names (HEAD/head, slashes, unicode, dots, `.lock`, 64/65 chars, Windows devices, `working`, trailing newline, `main`, `refs`, `a.yaml`).
- Git environments: not a repo, `--init-git`, unborn HEAD, detached HEAD, project nested in larger repo with other staged/untracked/ignored files, empty project (0 items), no `user.name`/`email`, odd/hostile `--user`, `index.lock`, ref lock, concurrent baseline creation (3 projects of 300 items), kill mid-creation (`os._exit` before/after commit), 5,000-item baseline/verify/diff/snapshot timing and cache size.
- CR: id allocation (8 parallel creators), transitions (closed->open, deferred without reason, same->same), nonexistent/lowercase item refs, control chars, 9 KB title, `promote_on_baseline` to a status outside the vocabulary.
- reasons: CSV and ReqIF import on a baselined item (reason enforced); mutation of set_parents/clear_suspect.
- diff: same-vs-same, working-vs-baseline both directions, whitespace-only, NFC vs NFD, huge text, moved level, header rename, parents change, added/removed/inactive item, `--format text|json|csv|html|docx|pdf`, CSV/HTML injection in titles.
Tests run: 79 tests of the 6 files in a scratch copy (all pass unmutated); mutation batch M1/M2 on 10 test files; later mutations were invalidated (see Test gaps).

## Findings
### CHANGECONTROL-01 Leaf symlink in the snapshot cache writes the tagged tree anywhere (arbitrary file overwrite)
- Where: src/rvs_core/changecontrol/baselines.py:415-441 (snapshot_dir)
- Severity: high
- Confidence: verified
- What is wrong: `snapshot_dir` refuses a symlinked `.rvs-cache` or `.rvs-cache/snapshots`, but not a symlink at `.rvs-cache/snapshots/<commit[:16]>`. `shutil.rmtree(target, ignore_errors=True)` silently fails on a symlink, then every file of the tagged tree is written through the link. The `is_relative_to(target.resolve())` check resolves the link first, so it passes.
- Evidence: in a copy of minimal10 with baseline B1: `mkdir -p .rvs-cache/snapshots; ln -s /abs/victim .rvs-cache/snapshots/e95573f28f6deaf6` (the 16 hex chars of the tag's commit), `echo precious > /abs/victim/rvs-project.yaml`, then `rvs diff . B1 working`. Afterwards `/abs/victim` contains `.complete EPS SYS VER baselines config .rvs-cache` and `rvs-project.yaml` was overwritten (293 bytes of project yaml instead of "precious"). A dangling link gives a raw `rvs: File exists (...)`.
- Why it matters: a project folder received as an archive (symlinks survive zip/tar; `.rvs-cache` is not in Git but is in an archive) plus its repository with an attacker-made tag lets `rvs diff`, `export --baseline`, `baseline verify` or the GUI Diff tab overwrite files with attacker-chosen names and content (e.g. a tree entry `.bashrc` with the link pointing at `$HOME`). `read_tree` rejects only `.git`, `..`, `.`, empty names.
- Proposed fix: after the existing checks, `if target.is_symlink() or any(p.is_symlink() for p in target.parents if p is inside root/CACHE)` raise; remove with `os.unlink` for symlinks; write with `O_NOFOLLOW`/check each `dest` parent is not a link; extract into a fresh `tempfile.mkdtemp` sibling and `os.replace` it.
- Test that would catch it: plant the leaf symlink to a tmp dir, call `snapshot_dir`, assert BaselineError and that the victim dir is unchanged.

### CHANGECONTROL-02 `diff` and `export --baseline` use a moved or tampered baseline without any check
- Where: src/rvs_core/changecontrol/diff.py:29 (load_snapshot), src/rvs_cli/main.py:171-174, snapshot_dir
- Severity: high
- Confidence: verified
- What is wrong: only `baseline verify` (and the GUI Verify button) checks a baseline. `rvs diff` and `rvs export --baseline B1` take the commit the tag points at and label the result "Baseline: B1" even when the manifest was changed or the tag was moved to another commit.
- Evidence: minimal10 + B1; `sed -i s/shall/SHALL/ SYS/SYS-0001.yml; git commit -qam tamper; git tag -d rvs/baseline/B1; git tag rvs/baseline/B1 HEAD` (lightweight tag at the later commit). `rvs baseline verify` -> `RVS-BASELINE-MODIFIED`, exit 1, but `rvs diff . B1 working` prints `0 added, 0 removed, 0 changed` and `rvs export . --items --baseline B1` prints "The spacecraft SHALL provide ..." with no warning, exit 0. With an annotated tag that copies the message (see 03) even `rvs validate` is silent. Same with only the manifest edited: diff/export proceed silently.
- Why it matters: deliverables (VCM, specs) "as it was at baseline X" for a review can silently come from the wrong content; the diff reports "no change" against a forged baseline. The guide calls verify "the only command that re-reads the tagged content" which hides that diff/export read it unchecked.
- Proposed fix: in `snapshot_dir`/`load_snapshot` run the cheap digest check (tag message vs manifest) and raise/print a warning; offer `--verify` for the deep check; label the output "UNVERIFIED" when the check fails.
- Test that would catch it: move the tag, run `export --baseline`/`diff`, expect refusal or a warning on stderr and a non-zero exit.

### CHANGECONTROL-03 Integrity check covers item content only; tag identity, config, documents, history and inactive items can change undetected
- Where: baselines.py:86-94 (item_digest), 366-402 (verify_baseline), 379-380
- Severity: medium
- Confidence: verified
- What is wrong: the tag message stores only the manifest digest, not the commit/tree, so a new annotated tag (same message) on any commit whose item digests equal the manifest verifies as "intact". Not covered: `config/*.yaml`, `rvs-project.yaml`, `.doorstop.yml` (fingerprint attributes, parent), `history/**`, attachments referenced by `ref`, Doorstop `references`, review state and link stamps (suspect state), and inactive items (see 06). `rvs validate` only runs the cheap check, so a retargeted tag with copied message and tampered items gives `0 errors`.
- Evidence: after `git commit` of tampered `config/rules.yaml` and a forged `history/SYS/SYS-0001.jsonl`, `git tag -a -F msg rvs/baseline/B1 HEAD` -> `rvs baseline verify . B1` = "Baseline B1 is intact." (rc 0), `validate` 0 errors. Item edit + same re-tag: `validate --fast` -> 0 errors; `baseline verify` -> CORRUPT. Changing `reviewed:` or a link stamp in the tagged tree -> intact.
- Why it matters: "can never be altered" holds for item text/attributes only if someone runs the deep verify; V24 mentions movable tags but not that everything else in the commit is unprotected, and the docs say "verify checks the tagged content against the manifest".
- Proposed fix: record the commit's tree id (and the tagged commit id) in the manifest or hash all non-cache files of the tagged tree into the manifest; make `validate` deep for baselines (or add an info finding "run baseline verify").
- Test that would catch it: tag-retarget test that changes a non-item file and expects CORRUPT.

### CHANGECONTROL-04 The snapshot marker signs the commit id, not the extracted files
- Where: baselines.py:419-421, 441
- Severity: medium
- Confidence: verified
- What is wrong: once `.complete` exists, the folder is trusted forever. Editing a file inside `.rvs-cache/snapshots/<commit>/` changes what `diff`, `export --baseline` and the GUI show; the AUDIT fix "snapshot folders trusted on a marker file" only stops forged folders, not edits after extraction.
- Evidence: `rvs diff . B1 working` (extracts), edit `.rvs-cache/snapshots/*/SYS/SYS-0001.yml` (shall->SHALL), then `rvs export --items --baseline B1` prints SHALL and `rvs diff . B1 working` reports the baseline as having SHALL (reversed diff); only `baseline verify` reports CORRUPT (as a false "baseline damaged" for a cache edit).
- Why it matters: silent wrong "as-baselined" outputs; also a mismatch message that blames the baseline instead of the cache.
- Proposed fix: sign a digest of the (path, sha256) list written at extraction and re-check cheaply (size+mtime) on reuse, or re-extract when any file differs; make verify bypass the cache.
- Test that would catch it: tamper one snapshot file after extraction, assert next snapshot_dir re-extracts.

### CHANGECONTROL-05 Concurrent baseline creation: crash and the loser's rollback overwrites the winner's promotions
- Where: baselines.py:184-189 (backup), 209 and 289-293 (_promote), 251-269 (_roll_back)
- Severity: medium
- Confidence: verified
- What is wrong: `_promotions` is computed before the manifest reservation; a second process promotes the same items first, so `cfg.changes.promote[status]` raises `KeyError('baselined')`. The loser's `_roll_back` then writes its stale backup bytes over the winner's already promoted item files and history.
- Evidence: examples/satellite300 copy (15 approved items), `git init`+commit, two `rvs baseline create . A` / `B` started together: A -> `KeyError: 'baselined'` (traceback at baselines.py:293), B -> "Baseline B created". Afterwards 14 items are `status: approved`, 1 `baselined`, while 15 history files contain `"action": "baseline", "why": "Baseline B"`; B's tagged tree has the items still approved. Three parallel creators on satellite300: 2 crashes with `unexpected error (KeyError)`, 9 of 15 promotions reverted.
- Why it matters: baseline content and history disagree; "promoted" items were not promoted in the baseline; an unhandled crash instead of a message. (DEVIATIONS V29 covers lost updates in general, not this path.)
- Proposed fix: take an exclusive lock file (e.g. `.rvs-cache/baseline.lock` via `open('x')`) for the whole creation; compute promotions after the lock; use `.get()`; roll back only files whose bytes still equal what this run wrote.
- Test that would catch it: create two baselines from threads with a barrier before `_promote`.

### CHANGECONTROL-06 Inactive items are outside the manifest, the digest check and the diff semantics
- Where: baselines.py:213-222 (`DoorstopProject.open(root).items()`), diff.py:128-169
- Severity: medium
- Confidence: verified
- What is wrong: `items()` omits `active: false` items, so they are absent from `baselines/*.yaml` and `item_digest`, are committed but never verified, never require a reason (not in `baselined_uids`), and the diff shows a deactivated item as `removed` (and a reactivated one as `added`); the `active` field difference in `_fields` can never occur.
- Evidence: SYS-0004 set `active: false`; `rvs baseline create . I1` -> manifest has 9 items, `grep -c SYS-0004 baselines/I1.yaml` = 0. Text of SYS-0004 forged in a later commit and tag re-created with the copied message: `rvs baseline verify . I1` = "Baseline I1 is intact." `rvs diff . B1 I1` -> `removed SYS-0004` although the file still exists.
- Why it matters: retired requirements are exactly what an audit asks about; they are not protected by the baseline and a deactivation is reported as a deletion.
- Proposed fix: include inactive items in manifest/digest (with `active` in the payload) and diff them (report "deactivated").
- Test that would catch it: baseline with an inactive item, tamper its file in the tagged commit, expect CORRUPT.

### CHANGECONTROL-07 A baseline can be created that is corrupt at birth when an item file is a symlink
- Where: git.py:105-127 (_project_files stages symlinks), baselines.py:238-248 (_check_committed), git.py:312 (read_tree skips symlinks)
- Severity: medium
- Confidence: verified
- What is wrong: a symlinked item file is staged as a mode 120000 blob; `_check_committed` only tests the path exists in the tree, while `read_tree` skips symlinks, so the snapshot lacks the item.
- Evidence: move `SYS/SYS-0002.yml` elsewhere in the project and `ln -s` it back; `rvs baseline create . Y1 -m sym` -> "Baseline Y1 created: 10 items" rc 0; `rvs baseline verify . Y1` -> `RVS-BASELINE-CORRUPT ... (items: SYS-0002)`, rc 1. The name is burned for good.
- Why it matters: a permanent, unusable baseline (and diff/export for it are wrong) is produced with a success message, which the AUDIT said `_check_committed` prevents. (The earlier audit made saves preserve symlinks, so symlinked items are an anticipated setup.)
- Proposed fix: in `_check_committed` require blob mode 100644/100755 for each item path (or follow the link and store the content); refuse before writing anything.
- Test that would catch it: baseline of a project with a symlinked item file expects BaselineError.

### CHANGECONTROL-08 Promotion target not checked against the vocabulary; typo writes invalid status into an immutable baseline
- Where: baselines.py:289-293 (_promote), config/loader.py:179-187, changes.schema.json
- Severity: medium
- Confidence: verified
- What is wrong: `promote_on_baseline` values are free strings and `_promote` writes via `proj.update_item`, bypassing `EditService._check_values`.
- Evidence: `config/changes.yaml: promote_on_baseline: {draft: bogus-status}`; `rvs baseline create . P1 -m t` -> created, rc 0; `rvs validate` -> `ERROR RVS-ATTR-VOCAB ... 'bogus-status'` on all items; the baseline cannot be redone.
- Why it matters: a one-word config typo permanently pollutes a baseline.
- Proposed fix: validate promote targets against the status vocabulary at config load or before the first write in `create_baseline`.
- Test that would catch it: config with an unknown target expects BaselineError and no files changed.

### CHANGECONTROL-09 `rvs cr status ... deferred` (and the GUI status box) defers a CR without the mandatory reason
- Where: changes.py:187-196 (set_status) vs 198-201 (defer); changes_view.py:214-215; cli changecontrol.py:172
- Severity: medium
- Confidence: verified
- What is wrong: only `defer()` insists on a reason; `set_status(..., "deferred", note="")` takes the same state silently. Terminal statuses (closed, rejected) can be reopened and any transition is allowed (open -> implemented).
- Evidence: `rvs cr status . CR-0001 deferred` -> "CR-0001 is now deferred."; `cr show` log `deferred  ` with empty note; then `closed`, `open`, `open` all accepted. Such a CR no longer blocks and is listed in the next manifest without a reason.
- Why it matters: SPEC: open CRs block a baseline unless explicitly deferred with a reason (D59).
- Proposed fix: in `set_status` require a note when the target is `deferred_status`; optionally a transition table in changes.yaml.
- Test that would catch it: `set_status(id, "deferred", who, "")` raises.

### CHANGECONTROL-10 `validate` says nothing when baselines cannot be checked (no Git repository)
- Where: validate.py:380-383
- Severity: medium
- Confidence: verified
- What is wrong: `except (GitError, BaselineError): break` drops the check silently.
- Evidence: copy of a project with baseline B1 and edited manifest, `.git` removed: `rvs validate . --fast` -> `0 errors, 0 warnings, 1 info`; `baseline verify` exits 2 "not inside a Git repository", `rvs baseline list` still lists B1.
- Why it matters: BRIEF asks that tamper checks "honestly say they cannot". A delivered copy (zip) reports a clean validation.
- Proposed fix: emit an info/warning finding `RVS-BASELINE-UNCHECKED` when manifests exist and no repository is found.
- Test that would catch it: project with manifest and no .git -> finding present.

### CHANGECONTROL-11 A damaged manifest crashes list/edit instead of being reported
- Where: manifests.py:21-35, baselines.py:358 (`len(m.get("items", {}))`), authoring.require_reason via baselined_uids
- Severity: medium
- Confidence: verified
- What is wrong: `read_manifest` only checks "is a dict". `items: null`/`items: 5`/`deferred_change_requests: 7` raise TypeError in `list_baselines` and `baselined_uids` (every edit of any item).
- Evidence: `items: 5` in baselines/B1.yaml -> `rvs baseline list .` = `rvs: unexpected error (TypeError)` with crash report; `EditService.update_item` -> `TypeError: 'int' object is not iterable`. `created: 123` prints `123`. (Validate reports MODIFIED correctly.)
- Why it matters: tampering or a merge accident disables editing and the Baselines tab instead of pointing to the manifest.
- Proposed fix: validate types in `read_manifest` (items must be a mapping, deferred a list) and return {}.
- Test that would catch it: parametrised bad manifests for list_baselines/baselined_uids.

### CHANGECONTROL-12 Interrupted creation leaves a burned name with a wrong hint
- Where: baselines.py:193-199, 376-378
- Severity: low
- Confidence: verified
- What is wrong: after a kill between commit/tag (`os._exit` in `commit_directory` or right after it) the manifest exists without a tag and items stay promoted. `validate` reports `RVS-BASELINE-NOTAG` with "Restore the tag from the repository history ... baselines are never deleted", but there is no tag to restore; re-running says "already exists" and there is no supported way to discard it.
- Evidence: kill after commit: `ls baselines` = K1.yaml, `rvs validate` -> NOTAG for K1, `rvs baseline create . K1` -> "already exists; baselines are immutable"; status of 29 items modified in the working tree.
- Why it matters: AUDIT lists this as "recoverable by hand" but neither guide nor message says how.
- Proposed fix: detect "manifest with empty/new and no tag and no commit" and offer `baseline create --resume/--discard`, or document the manual steps in the hint.
- Test that would catch it: message test for NOTAG of an unfinished baseline.

### CHANGECONTROL-13 Git failures that are not OSError/KeyError surface as "unexpected error"
- Where: git.py:209-213, 265-268
- Severity: low
- Confidence: verified
- What is wrong: dulwich `FileLocked` (index.lock or a ref lock held by another git process) is not caught.
- Evidence: `touch .git/index.lock; rvs baseline create . L1 -m t` -> `rvs: unexpected error (FileLocked). A crash report ...` rc 1 (state was rolled back correctly). Same with a `.lock` on the tag ref.
- Why it matters: common situation (IDE/GUI running git) gives a crash report rather than "another Git process is running; remove .git/index.lock".
- Proposed fix: catch `dulwich.file.FileLocked` and raise GitError with that advice.
- Test that would catch it: create `.git/index.lock`, expect BaselineError/GitError.

### CHANGECONTROL-14 Reason requirement for set_parents / clear_suspect on baselined items is not tested
- Where: authoring.py:197, 208 (code is correct); tests
- Severity: medium (test gap)
- Confidence: verified (mutation survives)
- What is wrong: removing `self.require_reason(before, why)` from `clear_suspect` or `set_parents` leaves the 10 test files (test_baselines, change_requests, diff, vcs_git, cli_changecontrol, review_cc, audit_core, audit_gaps, small_findings, authoring) green; the guide promises it for "changing parents, clearing suspect links". Also mutations M3 (digest ignores `parents`) and M4a (digest ignores `header`) survive test_baselines, test_diff, test_review_cc, test_audit_core and test_audit_gaps: no test tampers a tagged tree's parents or header. (Mutations for ref/level/flags/deep-verify/ordering were not completed; the machine was loaded and the batch was stopped.)
- Evidence: scratch-copy mutations with `mutate.sh`, pytest output all dots.
- Proposed fix: add tests for both calls, and a verify test per digest field (parents, header, ref, level, flags).

### CHANGECONTROL-15 Smaller defects (each reproduced)
- Where / what / evidence:
  - baselines.py:31 `NAME_RE` uses `$`, so `"X1\n"` passes `_check_name` and is rejected later with "Git does not accept 'rvs/baseline/X1\n'" (use `fullmatch`). Severity low.
  - git.py:85-96 `_identity`: email always comes from git config even when `--user` is given (`--user root` with `user.email other@x` -> `root <other@x>`); with no config the email is synthesised from the display name (`abc@d@localhost`, `Ünï.Çode.😀@localhost`). Low.
  - A description containing NUL (API/GUI) yields a commit object that `git fsck` reports as `nulInCommit`; a lone surrogate gives a raw `'utf-8' codec can't encode` message (rolled back). Low.
  - `baseline list` prints `created[:19]` (local wall time without offset) and multi-line descriptions break the one-line-per-baseline table. Low.
  - `rvs diff --document NOPE` silently prints an empty diff (cli changecontrol.py:201). Low.
  - Baseline with 0 items is created without a warning (empty project). Low.
  - `rvs baseline verify` on a baseline whose manifest was deleted says "The baseline 'B1' does not exist" and `baseline list` says "No baselines yet." although a tag exists; only `validate` shows NOMANIFEST (baselines.py:370). Low.
  - CR title/description accept control characters (`\x07` stripped on display, newline in the title breaks `cr list`); CR `update()` ignores `who` and logs nothing when title/items change; CR ids can be reused after the newest file is deleted (changes.py:157). Low.
  - The `.gitignore`/symlinked-folder/nested-repo skips are only partly in the guide ("all files except .git, .rvs-cache and *.tmp"); the guide says `git push` is the user's job but never mentions that tags need `git push --tags`; a teammate's clone without the tags gets `RVS-BASELINE-NOTAG` errors on every baseline (verified with `git clone --no-tags`). Low (docs).
  - `item_digest` ignores Doorstop `references` (verified SAME) although D08 names `references` for evidence. Low.
  - Manifest `created`, history `when`, CR log `when`, commit/tag times use the wall clock and ignore `SOURCE_DATE_EPOCH` (timezone-aware everywhere checked; commit/tag zone is fixed to +0000). Low/question.

## Checked and found correct
- Manifest edit, manifest CRLF conversion (no false alarm), manifest deleted, tag deleted, lightweight tag swap: `baseline verify` and `validate` report MODIFIED / NOMANIFEST / NOTAG correctly; tag retargeted with copied message and an edited, added or deleted item or changed parents: deep verify reports CORRUPT.
- Name validation: HEAD/head collision, `working`, Windows devices (with extensions), `..`, `.lock`, 65 chars, unicode, spaces, slashes all refused with plain messages; `aux.x.y`, `NUL.` refused; creation is atomic w.r.t. existing names and case variants.
- Nested project in a larger repo: only the project subtree is committed; other staged files (modified and new), untracked and ignored files stay out and stay staged; tag path `rvs/baseline/docs/sub/N1`. Detached HEAD, unborn HEAD with `--init-git`, empty project, packed refs/gc, normal clone: all worked and verify intact.
- Rollback on `index.lock`/ref lock leaves no manifest and no commit. Signing config is ignored.
- 5,000 items: create 6.0 s, verify 5.3 s, diff 2.5 s, list 0.6 s; each compared baseline adds ~25 MB to `.rvs-cache/snapshots` (V30).
- CSV/HTML/JSON/DOCX/PDF diff outputs: formula titles are apostrophe-prefixed, HTML is escaped; all six formats generate; whitespace-only, NFC/NFD, level, header, parents, added/removed changes show up (NFD/NFC differences look identical on screen).
- CR creation by 8 parallel processes produced 8 distinct ids; unknown item references are reported by validate as RVS-CR-ITEM; closed/unknown CRs refuse edit attribution.
- Reasons for baselined items are enforced for `EditService.update_item`, CSV import and ReqIF import (CLI `--reason` empty or blank is refused).
- Timestamps in manifest, history and CR log are timezone-aware ISO strings; list ordering uses UTC instants.

## Questions about intended behaviour
- Should deleting both the manifest and the tag be detectable (e.g. by an expected-baselines list in `rvs-project.yaml`)? Today it leaves no trace in the working copy.
- Are CR transitions meant to be free (closed -> open, rejected -> approved) and may a CR file be edited after it is listed in a manifest as deferred?
- Is a copied project folder in the same repository supposed to inherit the original's baselines through the digest fallback in `_tag_for`?
- Should `SOURCE_DATE_EPOCH` also pin manifest `created` and commit/tag times (rule 14), or are baselines exempt?
- Test judgement: mutation batch for `item_digest` fields, deep-verify comparison and `list_baselines` ordering was started but invalidated (the batch was killed and later tests stopped at an unrelated first failure); only M1-M3 results above are reliable.


Next: [AUDIT.md](../../AUDIT.md) · [Engineering audit](../AUDIT.md)
