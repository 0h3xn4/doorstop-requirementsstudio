"""Doorstop 3.2 adapter: all reads and writes of the document tree go through Doorstop's Python API."""

import logging
import os
import shutil
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import doorstop
import yaml
from doorstop import common as _doorstop_common
from doorstop import settings as _settings
from doorstop.common import DoorstopError, DoorstopInfo, DoorstopWarning
from doorstop.core import builder

from rvs_core.adapter.cache import CacheStats, ItemCache, is_racy, stat_key
from rvs_core.adapter.model import DocumentInfo, Issue, ItemData, ProjectError, UnreadableItemError
from rvs_core.findings import Finding
from rvs_core.schema.versioning import CURRENT_VERSION, VERSION_KEY

# Doorstop logs item details at debug level; project content must never reach a log sink (spec rule 11).
logging.getLogger("doorstop").setLevel(logging.CRITICAL)

# Validation must never rewrite files (DEVIATIONS V09 / spec rule 14): Doorstop would otherwise stamp
# unstamped links, reformat link lists and auto-review new items while validating. RVS stamps links explicitly in link().
_settings.REORDER = False
_settings.REFORMAT = False
_settings.STAMP_NEW_LINKS = False
_settings.REVIEW_NEW_ITEMS = False
# Doorstop would otherwise run `git add/rm` through a subprocess on every save when the project is in a Git
# repository: it needs a `git` executable, and it uses the process's working directory, not the project's repository.
_settings.ADDREMOVE_FILES = False
# Project files are LF on every system (Doorstop defaults to the OS line ending: CRLF on Windows would make every item
# differ from the same project made on Linux, and from the committed examples).
_settings.WRITE_LINESEPERATOR = "\n"

# Doorstop parses every item with PyYAML's pure-Python SafeLoader; libyaml's C parser reads the same documents about
# three times faster (cold open of 5,000 items: 6.6 s -> 2.0 s, DEVIATIONS V14). Same data model; tests compare both
# loaders on every example item. Without libyaml (some platforms) Doorstop's default stays.
if getattr(yaml, "CSafeLoader", None) is not None:
    _doorstop_common.load_yaml.__defaults__ = (yaml.CSafeLoader,)


MAX_ITEM_FILE_BYTES = 64 * 1024 * 1024
MAX_YAML_EXPANSION = 2_000_000  # nodes after every alias is expanded: a few thousand is typical, millions is a bomb
_YAML_CORE_TAG = "tag:yaml.org,2002:"


def _loader() -> Any:
    return getattr(yaml, "CSafeLoader", yaml.SafeLoader)  # the C parser: the pure-Python composer tripled the cold open


def _expansion(node: yaml.Node, limit: int) -> int:
    """Number of nodes in ``node`` with aliases expanded (what a naive walk of the loaded data would visit), stopping
    once it exceeds ``limit``. Shared nodes are counted once, then reused, so the scan itself stays linear."""
    sizes: dict[int, int] = {}
    started: set[int] = set()  # a recursive anchor makes a node its own descendant: visit each node once
    stack: list[tuple[yaml.Node, bool]] = [(node, False)]
    while stack:
        current, done = stack.pop()
        key = id(current)
        if key in sizes or (not done and key in started):
            continue
        started.add(key)
        children: list[yaml.Node] = []
        if isinstance(current, yaml.MappingNode):
            children = [n for pair in current.value for n in pair]
        elif isinstance(current, yaml.SequenceNode):
            children = list(current.value)
        if not done:
            stack.append((current, True))
            stack.extend((c, False) for c in children if id(c) not in sizes)
        else:
            total = 1 + sum(sizes.get(id(c), 1) for c in children)
            sizes[key] = total
            if total > limit:
                return total
    return sizes.get(id(node), 1)


def _scan_item(path: Path) -> tuple[tuple[str, ...], str]:
    """(top-level keys that occur twice, problem text or '') for an item file. YAML loaders keep the last duplicate
    silently; a document whose aliases expand beyond ``MAX_YAML_EXPANSION`` would hang any later walk of its data."""
    try:
        if path.stat().st_size > MAX_ITEM_FILE_BYTES:
            return (), f"is larger than {MAX_ITEM_FILE_BYTES // (1024 * 1024)} MB"
        node = yaml.compose(path.read_text(encoding="utf-8", errors="replace"), Loader=_loader())
    except (yaml.YAMLError, OSError):
        return (), ""
    if not isinstance(node, yaml.MappingNode):
        return (), ""
    if _expansion(node, MAX_YAML_EXPANSION) > MAX_YAML_EXPANSION:
        return (), "uses YAML aliases that expand to an unreasonable size"
    seen: set[str] = set()
    dups: list[str] = []
    for key, _value in node.value:
        if isinstance(key, yaml.ScalarNode):
            if key.value in seen and key.value not in dups:
                dups.append(key.value)
            seen.add(key.value)
    return tuple(dups), ""


def _atomic_write_text(text: str, path: str, end: str = "\n") -> str:
    """Doorstop writes item files in place, so a crash half way leaves a truncated file. Write a temporary file next to
    it and swap it in instead; the file keeps its permissions, and a symbolic link stays a link to the updated file."""
    target = os.path.realpath(path)
    tmp = f"{target}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline=end) as fh:  # noqa: PTH123, SIM115 - same call as Doorstop's
            fh.write(text)
        if os.path.exists(target):
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


_doorstop_common.write_text = _atomic_write_text


def _refuse_includes(root: Path) -> None:
    """Doorstop lets a document's .doorstop.yml pull in any file with ``!include``; a project from elsewhere could use
    that to read local files into findings and exports. RVS projects never need it. The file is composed (not just
    searched for the word), so ``%TAG`` handles and other spellings of the tag are caught too."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".rvs-cache")]
        if ".doorstop.yml" in filenames:
            config = Path(dirpath, ".doorstop.yml")
            text = config.read_text(encoding="utf-8", errors="replace")
            if "!include" in text or _custom_tags(text):
                raise ProjectError(
                    f"{config.relative_to(root)} uses a custom YAML tag such as '!include', which RVS does not allow: "
                    "remove it from the file."
                )


def _custom_tags(text: str) -> bool:
    """Whether the YAML text uses any tag other than the standard ones."""
    try:
        nodes = [yaml.compose(text, Loader=_loader())]
    except yaml.YAMLError:
        return "%TAG" in text or "!<" in text  # unparsable anyway; Doorstop will report it
    seen: set[int] = set()
    while nodes:
        node = nodes.pop()
        if node is None or id(node) in seen:
            continue
        seen.add(id(node))
        if not node.tag.startswith(_YAML_CORE_TAG):
            return True
        if isinstance(node, yaml.MappingNode):
            nodes.extend(n for pair in node.value for n in pair)
        elif isinstance(node, yaml.SequenceNode):
            nodes.extend(node.value)
    return False


def yaml_parser_is_fast() -> bool:
    """True when Doorstop reads items with libyaml's C parser (see above)."""
    return getattr(yaml, "CSafeLoader", None) is not None and _doorstop_common.load_yaml.__defaults__ == (
        yaml.CSafeLoader,
    )


# Doorstop item fields that are not RVS extended attributes.
_CORE_FIELDS = frozenset({"level", "active", "normative", "derived", "reviewed", "text", "ref", "links", "header"})


ItemCheck = Callable[[ItemData, DocumentInfo], Iterable[Finding]]
DocCheck = Callable[[DocumentInfo], Iterable[Finding]]


def _plain(value: Any) -> Any:
    """Convert Doorstop value wrappers (Text, ...) to plain Python types for stable comparison."""
    if isinstance(value, str):
        return str(value)
    if isinstance(value, date):  # also datetime: JSON-safe and identical on every read path
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return value


def _item_objects(doc: Any) -> list[Any]:
    """The document's Item objects *without* parsing their files (``Document.items`` parses every item to test
    ``active``, which made one edit in a 1,300-item document cost a second). Files are parsed on first attribute use."""
    return list(doc._iter())  # noqa: SLF001 - Doorstop offers no public lazy listing (docs/DEVIATIONS.md V21)


class DoorstopProject:
    """A project folder, i.e. a Doorstop tree. Not thread-safe; create one per worker."""

    def __init__(self, root: Path, tree: Any) -> None:
        self.root = root
        self._tree = tree
        self._cache = ItemCache(root)
        self.cache_stats = CacheStats()
        self._index: dict[str, Any] = {}  # uid -> Doorstop item, filled per document on first lookup

    # construction ###########################################################

    @classmethod
    def open(cls, root: Path) -> "DoorstopProject":
        root = Path(root)
        if not root.is_dir():
            raise ProjectError(f"Project folder {root} does not exist. Check the path or create a project first.")
        _refuse_includes(root)
        try:
            return cls(root, builder.build(root=str(root)))
        except DoorstopError as exc:
            raise ProjectError(f"The document tree in {root} cannot be loaded: {exc}") from exc

    @classmethod
    def create(cls, root: Path) -> "DoorstopProject":
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        return cls.open(root)

    # documents ##############################################################

    def _doc(self, prefix: str) -> Any:
        try:
            return self._tree.find_document(prefix)
        except DoorstopError:
            raise ProjectError(f"Document '{prefix}' does not exist. Declare it in rvs-project.yaml first.") from None

    def _info(self, doc: Any) -> DocumentInfo:
        return DocumentInfo(
            prefix=str(doc.prefix),
            parent=str(doc.parent) if doc.parent else None,
            path=Path(doc.path).relative_to(self.root).as_posix(),
            sep=str(doc.sep),
            digits=int(doc.digits),
            itemformat=str(doc.itemformat),
            defaults=dict(doc._attribute_defaults or {}),  # no public getter in Doorstop 3.2 (DEVIATIONS V08)
            fingerprint=tuple(doc.extended_reviewed),
        )

    def documents(self) -> list[DocumentInfo]:
        return sorted((self._info(d) for d in self._tree), key=lambda d: d.prefix)

    def create_document(
        self,
        prefix: str,
        *,
        parent: str | None = None,
        sep: str = "-",
        digits: int = 4,
        defaults: Mapping[str, Any] | None = None,
        fingerprint: Iterable[str] = (),
    ) -> DocumentInfo:
        try:
            doc = self._tree.create_document(str(self.root / prefix), prefix, parent=parent, sep=sep, digits=digits)
        except DoorstopError as exc:
            raise ProjectError(f"Document '{prefix}' cannot be created: {exc}") from exc
        # Doorstop 3.2 has no public API to set attribute defaults or fingerprint attributes (DEVIATIONS V08);
        # the document is then saved through Doorstop itself.
        doc._attribute_defaults = dict(defaults) if defaults else None
        doc._extended_reviewed = sorted(set(fingerprint))
        doc.save()
        return self._info(doc)

    # items ##################################################################

    def _item(self, uid: str) -> Any:
        if uid not in self._index:
            prefix = uid.rsplit("-", 1)[0] if "-" in uid else ""
            try:
                doc = self._doc(prefix)
            except ProjectError:
                raise ProjectError(f"Item '{uid}' does not exist. Check the ID or refresh the project.") from None
            for item in _item_objects(doc):  # one pass per document; later lookups are dictionary hits
                self._index[str(item.uid)] = item
        try:
            item = self._index[uid]
        except KeyError:
            raise ProjectError(f"Item '{uid}' does not exist. Check the ID or refresh the project.") from None
        try:
            item.load()  # Doorstop's plain setters save without loading first: an unloaded item would overwrite its file
        except DoorstopError as exc:
            raise UnreadableItemError(f"The file of {uid} cannot be read. {str(exc).strip()}") from None
        return item

    def _data(self, item: Any) -> ItemData:
        attrs = {k: _plain(item.get(k)) for k in sorted(item.extended)}
        return ItemData(
            uid=str(item.uid),
            document=str(item.document.prefix),
            level=str(item.level),
            text=str(item.text),
            header=str(item.header or ""),
            normative=bool(item.normative),
            derived=bool(item.derived),
            active=bool(item.active),
            reviewed=bool(item.reviewed),
            ref=str(item.ref or ""),
            links=tuple(sorted(str(u) for u in item.links)),
            stamp=str(item.stamp()),
            link_stamps={str(u): str(u.stamp) for u in sorted(item.links, key=str)},
            attrs=attrs,
            path=Path(item.path).relative_to(self.root).as_posix(),
        )

    def items(self, prefix: str | None = None) -> list[ItemData]:
        docs = [self._doc(prefix)] if prefix else sorted(self._tree, key=lambda d: str(d.prefix))
        try:
            return [item for d in docs for item in self._items_of(d)]
        except DoorstopError as exc:
            raise UnreadableItemError(f"An item file cannot be read. {str(exc).strip()}") from None
        except (ValueError, TypeError, AttributeError, KeyError, yaml.YAMLError, RecursionError) as exc:
            # hand-edited YAML that parses but is wrong (an impossible date, a number where text belongs, ...)
            raise UnreadableItemError(
                f"An item file has content RVS cannot read ({type(exc).__name__}). Check the most recently edited item files."
            ) from None

    def _item_files(self, doc_dir: Path) -> list[Path]:
        """Item files of a document the way Doorstop finds them (recursive, embedded documents skipped)."""
        found: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(doc_dir):
            dirnames[:] = sorted(d for d in dirnames if not os.path.exists(os.path.join(dirpath, d, ".doorstop.yml")))
            found += [Path(dirpath, f) for f in filenames if f.endswith(".yml") and f != ".doorstop.yml"]
        return sorted(found)

    def _items_of(self, doc: Any) -> list[ItemData]:
        prefix = str(doc.prefix)
        if str(doc.itemformat) != "yaml":  # the cache only understands YAML items
            return [self._data(i) for i in sorted(doc.items, key=lambda i: str(i.uid))]
        doc_dir = Path(doc.path)
        config = stat_key(doc_dir / ".doorstop.yml")
        cached = self._cache.load(prefix, config)
        now_ns = time.time_ns()
        entries: dict[str, tuple[tuple[int, int], ItemData]] = {}
        result: dict[str, ItemData] = {}
        missing: list[tuple[Path, str, tuple[int, int]]] = []
        for path in self._item_files(doc_dir):
            rel = path.relative_to(doc_dir).as_posix()
            key = stat_key(path)
            hit = cached.get(rel)
            if hit is not None and hit[0] == key:
                # the cached path may be from before the document folder was moved: recompute it
                data = replace(hit[1], path=(doc_dir / rel).relative_to(self.root).as_posix())
                result[rel] = data
                entries[rel] = (hit[0], data)
                self.cache_stats.hits += 1
            else:
                missing.append((path, rel, key))
        if missing:
            objects = {os.path.normpath(str(i.path)): i for i in _item_objects(doc)}
            for path, rel, key in missing:
                obj = objects.get(os.path.normpath(str(path)))
                if obj is None or not obj.active:
                    continue  # not an item file, or an inactive item (Document.items skips those too)
                dups, problem = _scan_item(path)
                if problem:
                    raise UnreadableItemError(
                        f"{path.relative_to(self.root).as_posix()} {problem}. Fix or remove the file."
                    )
                try:
                    data = self._data(obj)
                except (ValueError, TypeError, AttributeError, KeyError, yaml.YAMLError, RecursionError) as exc:
                    raise UnreadableItemError(
                        f"{path.relative_to(self.root).as_posix()} has content RVS cannot read ({type(exc).__name__}): "
                        "check its fields (dates, numbers and lists) after your last hand edit."
                    ) from None
                if dups:
                    data = replace(data, duplicate_keys=dups)
                self.cache_stats.misses += 1
                result[rel] = data
                if not is_racy(key, now_ns):
                    entries[rel] = (key, data)
        if {r: v[0] for r, v in entries.items()} != {r: v[0] for r, v in cached.items()}:
            self._cache.save(prefix, config, entries)
        return sorted(result.values(), key=lambda i: i.uid)

    def discard_item(self, uid: str) -> None:
        """Delete an item file that was just created by mistake (never used for items the user has seen)."""
        item = self._item(uid)
        item.delete()
        self._index.pop(uid, None)

    def all_uids(self) -> set[str]:
        """Every item ID that has a file, inactive items included (``items()`` lists active items only). The file name
        is the ID, so no item is parsed."""
        found: set[str] = set()
        for doc in self._tree:
            if str(doc.itemformat) == "yaml":
                found.update(p.stem for p in self._item_files(Path(doc.path)))
        return found

    def get_item(self, uid: str) -> ItemData:
        return self._data(self._item(uid))

    def add_item(
        self,
        prefix: str,
        text: str,
        *,
        attrs: Mapping[str, Any] | None = None,
        level: str | None = None,
        normative: bool = True,
        derived: bool = False,
        header: str = "",
        number: int | None = None,
        active: bool = True,
        ref: str = "",
    ) -> ItemData:
        doc = self._doc(prefix)
        try:
            item = doc.add_item(number=number, level=level, reorder=False)  # reorder would rewrite every item file
        except DoorstopError as exc:
            raise ProjectError(f"The item cannot be created in {prefix}: {exc}") from exc
        self._index[str(item.uid)] = item
        item.text = text
        item.normative = normative
        item.derived = derived
        if header:
            item.header = header
        if not active:
            item.active = False
        if ref:
            item.ref = ref
        merged = {VERSION_KEY: CURRENT_VERSION, **(attrs or {})}
        item.set_attributes(merged)
        return self._data(item)

    def update_item(
        self,
        uid: str,
        *,
        text: str | None = None,
        attrs: Mapping[str, Any] | None = None,
        normative: bool | None = None,
        derived: bool | None = None,
        active: bool | None = None,
        header: str | None = None,
        level: str | None = None,
        ref: str | None = None,
    ) -> ItemData:
        item = self._item(uid)
        if text is not None:
            item.text = text
        for name, value in (
            ("normative", normative),
            ("derived", derived),
            ("active", active),
            ("header", header),
            ("level", level),
            ("ref", ref),
        ):
            if value is not None:
                setattr(item, name, value)
        if attrs:
            item.set_attributes(dict(attrs))
        return self._data(item)

    # links, suspect links, review ###########################################

    def link(self, child_uid: str, parent_uid: str) -> None:
        self._item(parent_uid)
        child = self._item(child_uid)
        child.link(parent_uid)
        child.clear([parent_uid])  # stamp the new link so it is not suspect

    def set_links(self, uid: str, parents: Iterable[str]) -> None:
        """Replace the item's Doorstop parent links; each new link is stamped so it is not suspect."""
        item = self._item(uid)
        wanted = sorted(set(parents))
        for parent in wanted:
            self._item(parent)
        for current in [str(u) for u in item.links]:
            if current not in wanted:
                item.unlink(current)
        added = [p for p in wanted if p not in [str(u) for u in item.links]]
        for parent in added:
            item.link(parent)
        if added:
            item.clear(added)  # only the new links are stamped; a link that was already suspect stays suspect

    def suspect_links(self, uid: str) -> tuple[str, ...]:
        item = self._item(uid)
        return tuple(
            sorted(
                str(link)
                for link, parent in zip(item.links, item.parent_items, strict=True)
                if link.stamp != parent.stamp()
            )
        )

    def clear_suspect(self, uid: str) -> None:
        self._item(uid).clear()

    def review_item(self, uid: str) -> None:
        self._item(uid).review()

    # validation #############################################################

    def issues(self, item_check: ItemCheck | None = None, doc_check: DocCheck | None = None) -> list[Issue]:
        """Run Doorstop's tree validation, with RVS checks attached as document and item hooks."""
        hook_findings: list[Finding] = []

        def document_hook(document: Any, tree: Any) -> list[Any]:
            if doc_check is not None:
                hook_findings.extend(doc_check(self._info(document)))
            return []

        def item_hook(item: Any, document: Any, tree: Any) -> list[Any]:
            if item_check is not None:
                hook_findings.extend(item_check(self._data(item), self._info(document)))
            return []

        out: list[Issue] = []
        try:
            for exc in self._tree.get_issues(document_hook=document_hook, item_hook=item_hook):
                level = (
                    "info"
                    if isinstance(exc, DoorstopInfo)
                    else "warning"
                    if isinstance(exc, DoorstopWarning)
                    else "error"
                )
                out.append(Issue(level, str(exc)))
        except DoorstopError as exc:
            raise ProjectError(f"Doorstop validation stopped: {exc}") from exc
        out.extend(Issue(f.severity.value, f.message, f) for f in hook_findings)
        return out


def framework_version() -> str:
    return str(doorstop.__version__)
