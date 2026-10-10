"""Baselines: a named, immutable snapshot of the whole project, bound to an annotated Git tag.

A baseline is (1) a manifest ``baselines/<name>.yaml`` with a content digest per item, committed together with the
whole project directory, and (2) the tag ``rvs/baseline/[<project path>/]<name>`` on that commit. The tag message
records the manifest's SHA-256, so a later edit of the manifest file is detected."""

import contextlib
import hashlib
import json
import os
import re
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from rvs_core.adapter import DoorstopProject, ItemData, cache
from rvs_core.authoring import EditService, history_path
from rvs_core.changecontrol.changes import ChangeRequest, ChangeRequestError, ChangeRequestStore
from rvs_core.changecontrol.manifests import baselined_uids, manifest_names, manifest_path, read_manifest
from rvs_core.config import ProjectConfig, load_project_config
from rvs_core.findings import Finding, Severity
from rvs_core.schema.versioning import CURRENT_VERSION
from rvs_core.vcs.git import GitError, GitRepo

TAG_PREFIX = "rvs/baseline/"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CACHE = ".rvs-cache"
__all__ = [
    "Baseline", "BaselineError", "current_label", "OpenChangeRequestsError", "baselined_uids", "create_baseline", "item_digest",
    "list_baselines", "snapshot_dir", "verify_baseline",
]  # fmt: skip


class BaselineError(Exception):
    """A baseline operation failed; the message says what to do."""


class OpenChangeRequestsError(BaselineError):
    def __init__(self, open_requests: list[ChangeRequest]) -> None:
        self.open_requests = open_requests
        ids = ", ".join(f"{c.id} ({c.status})" for c in open_requests)
        super().__init__(
            f"A baseline cannot be created while change requests are open: {ids}. Close them, or defer each one "
            "explicitly with a reason."
        )


@dataclass(frozen=True)
class Baseline:
    name: str
    description: str
    created_by: str
    created: str
    commit: str
    tag: str
    items: int
    deferred: tuple[str, ...]
    manifest_sha256: str


_DIGEST_LINE = re.compile(r"^manifest-sha256: ([0-9a-f]{64})$", re.MULTILINE)


def manifest_digest(data: bytes) -> str:
    """SHA-256 of a manifest with line endings normalised (a Windows checkout may have turned LF into CRLF)."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def tag_project_path(message: str) -> str | None:
    """Where in the repository the project was when the baseline was made (None for tags without the line)."""
    found = re.findall(r"^project-path: (.*)$", message, re.MULTILINE)
    return found[-1] if found else None


def tag_digest(message: str) -> str:
    """The manifest digest recorded in a tag message: the last such line, so a description cannot shadow it."""
    found = _DIGEST_LINE.findall(message)
    return found[-1] if found else ""


def item_digest(item: ItemData) -> str:
    """SHA-256 of the item's content (not of stamps, review state, paths or file layout)."""
    attrs = {k: v for k, v in item.attrs.items() if k != "rvs_schema_version" and v not in (None, "", [])}
    payload = {
        "document": item.document, "level": item.level, "normative": item.normative, "derived": item.derived,
        "active": item.active, "header": item.header, "ref": item.ref, "text": item.text.strip(),
        "parents": sorted(item.links), "attrs": attrs,
    }  # fmt: skip
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _ref_safe(path: str) -> str:
    """Git ref components cannot contain spaces or other special characters, nor start with a dot. A component that
    needed changing gets a short hash of the original appended ('+' is legal in refs and never produced otherwise), so
    two different folders ('a b' and 'a_b') can never end up with the same tag."""
    parts = []
    for p in path.split("/"):
        if not p:
            continue
        safe = re.sub(r"\.{2,}", "_", re.sub(r"[^A-Za-z0-9._-]", "_", p)).lstrip(".") or "_"
        if safe != p or safe.endswith(".lock"):
            safe = f"{safe}+{hashlib.sha1(p.encode('utf-8'), usedforsecurity=False).hexdigest()[:8]}"  # noqa: S324 - a label
        parts.append(safe)
    return "/".join(parts)


def _tag_name(repo: GitRepo, root: Path, name: str) -> str:
    rel = _ref_safe(repo.relative(root))
    return f"rvs/baseline/{rel + '/' if rel else ''}{name}"


RESERVED_NAMES = {"working"}  # the diff commands use this word for the working copy
#: Names Windows refuses as file names (with or without an extension): ``baselines/<name>.yaml`` must be checkable there.
WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def _check_name(name: str) -> None:
    if (name or "").lower() in RESERVED_NAMES:
        raise BaselineError(f"'{name}' cannot be a baseline name: it stands for the working copy in comparisons.")
    if (name or "").split(".")[0].lower() in WINDOWS_RESERVED:
        raise BaselineError(f"'{name}' cannot be a baseline name: Windows reserves it as a device name.")
    if ".." in (name or "") or (name or "").endswith((".", ".lock")):
        raise BaselineError(
            f"'{name}' is not a valid baseline name: Git does not allow '..' or a name ending in '.' or '.lock'."
        )
    if not NAME_RE.match(name or ""):
        raise BaselineError(
            f"'{name}' is not a valid baseline name. Use 1-64 letters, digits, '.', '_' or '-' (no spaces or slashes)."
        )


def create_baseline(
    root: Path,
    name: str,
    description: str,
    *,
    user: str | None = None,
    defer: Mapping[str, str] | None = None,
    init_git: bool = False,
) -> Baseline:
    root = Path(root)
    _check_name(name)
    try:
        repo = GitRepo.discover(root)
    except GitError:
        if not init_git:
            raise
        repo = GitRepo.init(root)
    cfg, _ = load_project_config(root)
    tag_name = _tag_name(repo, root, name)
    if not repo.valid_tag_name(tag_name):
        raise BaselineError(f"Git does not accept '{tag_name}' as a tag name; choose another baseline name.")
    if manifest_path(root, name).exists() or repo.tag(tag_name) is not None:
        raise BaselineError(f"The baseline '{name}' already exists; baselines are immutable. Choose another name.")
    clash = [n for n in manifest_names(root) if n.lower() == name.lower()]
    if clash:  # 'BL1' and 'bl1' would be the same file on Windows and macOS
        raise BaselineError(
            f"The baseline '{name}' differs only in upper/lower case from the existing '{clash[0]}'. Choose another name."
        )

    store = ChangeRequestStore(root, cfg)
    open_requests = store.open_requests()
    defer = dict(defer or {})
    unknown = sorted(set(defer) - {c.id for c in open_requests})
    if unknown:
        raise BaselineError(f"{', '.join(unknown)} cannot be deferred: not an open change request.")
    undeferred = [c for c in open_requests if c.id not in defer]
    if undeferred:
        raise OpenChangeRequestsError(undeferred)
    empty = sorted(i for i, reason in defer.items() if not reason.strip())
    if empty:
        raise BaselineError(f"Deferring {', '.join(empty)} needs a reason; say why it can wait.")

    who = user or EditService(root).user
    promotions = _promotions(root, cfg)
    # Everything below touches files before the commit and the tag exist. If any step fails, the files are put back
    # (the status promotion, the history entries, the deferred change requests, the manifest) and a commit that was
    # already made is taken back, so the name is not burned.
    backup: dict[Path, bytes | None] = {root / rel: (root / rel).read_bytes() for _uid, rel in promotions}
    for uid, _rel in promotions:
        hist = history_path(root, uid)
        backup[hist] = hist.read_bytes() if hist.is_file() else None
    changes_dir = root / "changes"
    if changes_dir.is_dir():
        backup.update({f: f.read_bytes() for f in changes_dir.glob("*.yaml")})
    path = manifest_path(root, name)
    (root / "baselines").mkdir(exist_ok=True)
    try:  # reserve the name: of two processes creating the same baseline, only one gets past this line
        path.open("x", encoding="utf-8").close()
    except FileExistsError:
        raise BaselineError(
            f"The baseline '{name}' already exists; baselines are immutable. Choose another name."
        ) from None
    before = repo.head()
    commit = ""
    try:
        try:
            for cr_id, reason in sorted(defer.items()):
                store.defer(cr_id, reason, who)
        except ChangeRequestError as exc:
            raise BaselineError(str(exc)) from exc
        deferred_all = tuple(sorted(c.id for c in store.list() if c.status == cfg.changes.deferred_status))

        _promote(root, cfg, promotions)
        svc = EditService(root, user=who)
        for uid, _rel in promotions:
            svc.record(uid, "baseline", ["status"], f"Baseline {name}")
        items = DoorstopProject.open(root).items()
        created = datetime.now().astimezone().isoformat(timespec="microseconds")
        manifest = {
            "rvs_schema_version": CURRENT_VERSION,
            "name": name,
            "description": description,
            "created_by": who,
            "created": created,
            "deferred_change_requests": list(deferred_all),
            "items": {i.uid: item_digest(i) for i in sorted(items, key=lambda i: i.uid)},
        }
        text = yaml.safe_dump(manifest, sort_keys=True, allow_unicode=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        digest = manifest_digest(text.encode("utf-8"))

        commit = repo.commit_directory(root, f"Baseline {name}: {description}\n\nRVS-Baseline: {name}", who)
        _check_committed(repo, root, commit, name, items)
        message = f"{name}\n\n{description}\n\nitems: {len(items)}\nproject-path: {repo.relative(root)}\nmanifest-sha256: {digest}\n"
        repo.create_tag(tag_name, message, who, commit)
    except BaseException:
        _roll_back(backup, path, repo, root, commit, before)
        raise
    return Baseline(name, description, who, created, commit, tag_name, len(items), deferred_all, digest)


def _check_committed(repo: GitRepo, root: Path, commit: str, name: str, items: list[ItemData]) -> None:
    """The commit must hold the manifest and every item file, or the baseline could never be verified."""
    present = repo.tree_paths(commit, root)
    wanted = {f"baselines/{name}.yaml", *(i.path.replace("\\", "/") for i in items)}
    missing = sorted(wanted - present)
    if missing:
        shown = ", ".join(missing[:3]) + (f" and {len(missing) - 3} more" if len(missing) > 3 else "")
        raise BaselineError(
            f"The baseline commit would leave out project files ({shown}). Nothing was created. "
            "Check that Git does not ignore them (.gitignore, .git/info/exclude)."
        )


def _roll_back(
    backup: dict[Path, bytes | None], manifest: Path, repo: GitRepo, root: Path, commit: str, before: str | None
) -> None:
    """Put every touched file back, one at a time: a file that cannot be restored (locked on Windows) must not stop
    the others, and the error that caused the roll-back stays the one reported."""
    for file, data in backup.items():
        try:
            if data is None:
                file.unlink(missing_ok=True)
            else:
                file.write_bytes(data)
        except OSError:
            continue
    with contextlib.suppress(OSError):
        manifest.unlink(missing_ok=True)
        (root / "baselines").rmdir()  # only removed when this attempt created it (empty)
    if commit and commit != before:
        with contextlib.suppress(GitError):
            repo.undo_commit(root, commit, before)


def current_label(root: Path) -> str:
    """Provenance text for outputs generated from the working copy."""
    found = list_baselines(root)
    return f"working copy (latest baseline: {found[-1].name})" if found else "working copy (no baseline)"


def _promotions(root: Path, cfg: ProjectConfig) -> list[tuple[str, str]]:
    """(uid, file) of the items whose status is promoted when a baseline is created (approved -> baselined)."""
    if not cfg.changes.promote:
        return []
    return [
        (i.uid, i.path)
        for i in DoorstopProject.open(root).items()
        if cfg.changes.promote.get(str(i.attrs.get("status")))
    ]


def _promote(root: Path, cfg: ProjectConfig, promotions: list[tuple[str, str]]) -> None:
    proj = DoorstopProject.open(root)
    for uid, _rel in promotions:
        status = str(proj.get_item(uid).attrs.get("status"))
        proj.update_item(uid, attrs={"status": cfg.changes.promote[status]})


def _tag_for(root: Path, name: str, repo: GitRepo | None = None) -> tuple[GitRepo, Any]:
    """The baseline's tag. Tags are named after the project's folder inside the repository; if the folder was moved
    or renamed since, the tag of the same name whose recorded manifest digest matches this manifest is used."""
    repo = repo or GitRepo.discover(root)
    tag = repo.tag(_tag_name(repo, root, name))
    if tag is None and manifest_path(root, name).is_file():
        digest = manifest_digest(manifest_path(root, name).read_bytes())
        for candidate in repo.tags(TAG_PREFIX):
            if candidate.name.endswith(f"/{name}") and tag_digest(candidate.message) == digest:
                return repo, candidate
    return repo, tag


def orphan_tags(root: Path) -> list[str]:
    """Baseline tags of this project whose manifest file is gone (``baselines/<name>.yaml`` deleted or not checked out)."""
    try:
        repo = GitRepo.discover(root)
    except GitError:
        return []
    try:
        own = _tag_name(repo, Path(root), "")
        names = set(manifest_names(Path(root)))
        return sorted(
            t.name[len(own) :]
            for t in repo.tags(own)
            if "/" not in t.name[len(own) :] and t.name[len(own) :] not in names
        )
    except Exception:  # noqa: BLE001 - damaged Git metadata must not make the project unopenable; Git is not needed to edit
        return []


def _instant(created: str) -> datetime:
    """``created`` as a UTC instant, so baselines made in different time zones sort in the order they were made."""
    try:
        moment = datetime.fromisoformat(created)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)
    return moment.astimezone(UTC) if moment.tzinfo else moment.replace(tzinfo=UTC)


def list_baselines(root: Path) -> list[Baseline]:
    """Baselines in creation order. Works without Git (commit and tag stay empty)."""
    root = Path(root)
    try:
        repo: GitRepo | None = GitRepo.discover(root)
    except GitError:
        repo = None
    found = []
    for name in manifest_names(root):
        m = read_manifest(root, name)
        tag = _tag_for(root, name, repo)[1] if repo else None
        digest = ""
        if tag:
            digest = tag_digest(tag.message)
        found.append(
            Baseline(
                name=str(m.get("name", name)),
                description=str(m.get("description", "")),
                created_by=str(m.get("created_by", "")),
                created=str(m.get("created", "")),
                commit=tag.commit if tag else "",
                tag=tag.name if tag else "",
                items=len(m.get("items", {})),
                deferred=tuple(str(c) for c in m.get("deferred_change_requests", [])),
                manifest_sha256=digest,
            )
        )
    return sorted(found, key=lambda b: (_instant(b.created), b.name))


def verify_baseline(root: Path, name: str, *, deep: bool = True) -> list[Finding]:
    """Findings if the baseline was tampered with: manifest edited after tagging (cheap), or item digests that no
    longer match the tagged tree (``deep``)."""
    root = Path(root)
    if not manifest_path(root, name).is_file():
        raise BaselineError(
            f"The baseline '{name}' does not exist. Run 'rvs baseline list PROJECT' (or open the Baselines tab) to see the available names."
        )
    repo, tag = _tag_for(root, name)
    loc = f"baselines/{name}.yaml"
    if tag is None:
        return [Finding("RVS-BASELINE-NOTAG", Severity.ERROR, f"Baseline {name} has a manifest but no Git tag.",
                        "Restore the tag from the repository history (git fetch --tags, or the clone it was made in); baselines are never deleted.", loc)]  # fmt: skip
    actual = manifest_digest(manifest_path(root, name).read_bytes())
    if tag_digest(tag.message) != actual:
        return [
            Finding(
                "RVS-BASELINE-MODIFIED", Severity.ERROR,
                f"The manifest of baseline {name} was changed after the baseline was created.",
                f"Restore {loc} from the tagged commit (git checkout {tag.name} -- {loc}); baselines are immutable.", loc,
            )
        ]  # fmt: skip
    if not deep:
        return []
    from rvs_core.changecontrol.diff import load_snapshot

    snap = load_snapshot(root, name)
    manifest = read_manifest(root, name)["items"]
    actual_items = {u: item_digest(i) for u, i in snap.items.items()}
    if actual_items != manifest:
        bad = sorted(set(actual_items) ^ set(manifest) | {u for u in manifest if actual_items.get(u) != manifest[u]})
        return [
            Finding("RVS-BASELINE-CORRUPT", Severity.ERROR,
                    f"The tagged tree of baseline {name} does not match its manifest (items: {', '.join(bad[:5])}).",
                    "Do not use this baseline. Compare the tagged commit with the manifest (git diff on the tag) to see what changed, and restore it from a trusted clone.", loc)
        ]  # fmt: skip
    return []


def snapshot_dir(root: Path, name: str) -> Path:
    """The project as it was at baseline ``name``, extracted inside the project's cache folder (reused afterwards)."""
    root = Path(root)
    if not manifest_path(root, name).is_file():
        raise BaselineError(
            f"The baseline '{name}' does not exist. Run 'rvs baseline list PROJECT' (or open the Baselines tab) to see the available names."
        )
    repo, tag = _tag_for(root, name)
    if tag is None:
        raise BaselineError(f"The Git tag of baseline '{name}' is missing; the snapshot cannot be restored.")
    snapshots = root / CACHE / "snapshots"
    if snapshots.is_symlink() or (root / CACHE).is_symlink():
        raise BaselineError("The snapshot cache folder is a symbolic link; remove it and try again.")
    target = snapshots / tag.commit[:16]
    marker = target / ".complete"
    signature = cache.sign(tag.commit)
    if marker.is_file() and cache.verify(tag.commit, marker.read_text(encoding="utf-8")):
        return Path(target)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)  # incomplete, unsigned or foreign: extract again from the repository
    (root / CACHE).mkdir(exist_ok=True)
    for guard, content in ((".gitignore", "*\n"), (".doorstop.skip-all", "")):
        if not (root / CACHE / guard).exists():
            (root / CACHE / guard).write_text(content, encoding="utf-8", newline="\n")
    when = repo.commit_time(tag.commit)
    for rel, data in repo.read_tree(tag.commit, root, tag_project_path(tag.message)).items():
        if rel.startswith(f"{CACHE}/"):
            continue
        dest = target / rel
        if not dest.resolve().is_relative_to(target.resolve()):
            raise BaselineError(
                f"The tagged tree has a path ({rel}) that leaves the snapshot folder; the baseline is not trusted."
            )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        os.utime(dest, (when, when))  # old timestamps: the item cache may store these files straight away
    marker.write_text(signature, encoding="utf-8")
    return Path(target)
