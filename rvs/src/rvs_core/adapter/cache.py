"""Per-document item cache (decision D27). Stored inside the project folder, git-ignored, best effort.

An entry is valid only while the item file's (mtime_ns, size) is unchanged AND the document's
``.doorstop.yml`` is unchanged (it holds the fingerprint attributes that feed ``reviewed``/``stamp``).
Files modified within the last ``RACY_SECONDS`` are never cached: two writes inside one filesystem
timestamp tick could otherwise leave a stale entry that looks valid.
"""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rvs_core.adapter.model import ItemData

CACHE_DIR = ".rvs-cache"
CACHE_VERSION = 1
RACY_SECONDS = 2.0

StatKey = tuple[int, int]


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0


def stat_key(path: Path | str) -> StatKey:
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size)


def is_racy(key: StatKey, now_ns: int) -> bool:
    return now_ns - key[0] < int(RACY_SECONDS * 1e9)


def _to_dict(item: ItemData) -> dict[str, Any]:
    return asdict(item)


def _from_dict(d: dict[str, Any]) -> ItemData:
    d = dict(d)
    d["links"] = tuple(d["links"])
    return ItemData(**d)


class ItemCache:
    def __init__(self, root: Path) -> None:
        self.dir = root / CACHE_DIR

    def _file(self, prefix: str) -> Path:
        return self.dir / f"{prefix}.json"

    def load(self, prefix: str, config: StatKey) -> dict[str, tuple[StatKey, ItemData]]:
        """Entries of ``prefix`` that are still trustworthy; empty on any problem."""
        try:
            raw = json.loads(self._file(prefix).read_text(encoding="utf-8"))
            if raw["v"] != CACHE_VERSION or tuple(raw["config"]) != config:
                return {}
            return {rel: ((e["k"][0], e["k"][1]), _from_dict(e["d"])) for rel, e in raw["items"].items()}
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            return {}

    def save(self, prefix: str, config: StatKey, entries: dict[str, tuple[StatKey, ItemData]]) -> None:
        try:
            self.dir.mkdir(exist_ok=True)
            ignore = self.dir / ".gitignore"
            if not ignore.exists():
                ignore.write_text("*\n", encoding="utf-8", newline="\n")
            skip = self.dir / ".doorstop.skip-all"  # Doorstop must not scan extracted baseline snapshots as documents
            if not skip.exists():
                skip.write_text("", encoding="utf-8")
            payload = {
                "v": CACHE_VERSION,
                "config": list(config),
                "items": {rel: {"k": list(k), "d": _to_dict(d)} for rel, (k, d) in sorted(entries.items())},
            }
            tmp = self._file(prefix).with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
            os.replace(tmp, self._file(prefix))
        except (OSError, TypeError, ValueError):
            pass  # read-only checkout, full disk or a value JSON cannot hold: the cache is only an optimisation
