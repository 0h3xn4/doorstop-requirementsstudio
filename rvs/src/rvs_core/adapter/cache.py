"""Per-document item cache (decision D27). Stored inside the project folder, git-ignored, best effort.

An entry is valid only while the item file's (mtime_ns, size) is unchanged AND the document's
``.doorstop.yml`` is unchanged (it holds the fingerprint attributes that feed ``reviewed``/``stamp``).
Files modified within the last ``RACY_SECONDS`` are never cached: two writes inside one filesystem
timestamp tick could otherwise leave a stale entry that looks valid.
"""

import contextlib
import hmac
import json
import os
import secrets
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rvs_core import userconfig
from rvs_core.adapter.model import ItemData

CACHE_DIR = ".rvs-cache"
CACHE_VERSION = 3
RACY_SECONDS = 2.0

StatKey = tuple[int, int]

_KEYS: dict[Path, bytes | None] = {}


def _key() -> bytes | None:
    """A secret that stays on this computer (next to the user's settings). Cache files and extracted baseline snapshots
    carry a signature made with it, so a ``.rvs-cache`` folder that arrived inside a zip or a clone (and could say
    anything about the items) is ignored. None when no key can be stored: then nothing is cached."""
    folder = userconfig.config_dir()
    if folder not in _KEYS:
        path = folder / "cache.key"
        key: bytes | None = None
        try:
            if path.is_file():
                key = bytes.fromhex(path.read_text(encoding="ascii").strip())
            if not key or len(key) < 16:
                folder.mkdir(parents=True, exist_ok=True)
                key = secrets.token_bytes(32)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="ascii") as fh:
                    fh.write(key.hex() + "\n")
        except (OSError, ValueError):
            key = None
        _KEYS[folder] = key
    return _KEYS[folder]


def sign(text: str) -> str:
    """Signature of ``text`` for this computer; empty when there is no key."""
    key = _key()
    return hmac.new(key, text.encode("utf-8"), "sha256").hexdigest() if key else ""


def verify(text: str, signature: str) -> bool:
    expected = sign(text)
    return bool(expected) and hmac.compare_digest(expected, str(signature))


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
    d["duplicate_keys"] = tuple(d.get("duplicate_keys", ()))
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
            signature = raw.pop("sig", "")
            if raw["v"] != CACHE_VERSION or tuple(raw["config"]) != config:
                return {}
            if not verify(json.dumps(raw, sort_keys=True, ensure_ascii=False), signature):
                return {}  # not written by this computer, or edited since
            return {rel: ((e["k"][0], e["k"][1]), _from_dict(e["d"])) for rel, e in raw["items"].items()}
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            return {}

    def save(self, prefix: str, config: StatKey, entries: dict[str, tuple[StatKey, ItemData]]) -> None:
        tmp: Path | None = None
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
            signature = sign(json.dumps(payload, sort_keys=True, ensure_ascii=False))
            if not signature:
                return  # no key: a cache nobody can vouch for is worse than none
            payload["sig"] = signature
            tmp = self._file(prefix).with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")  # one per writer
            tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8", newline="\n")
            os.replace(tmp, self._file(prefix))
        except (OSError, TypeError, ValueError):
            # read-only checkout, full disk or a value JSON cannot hold: the cache is only an optimisation
            if tmp is not None:
                with contextlib.suppress(OSError):
                    tmp.unlink(missing_ok=True)
