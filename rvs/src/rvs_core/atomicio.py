"""Write a file so that a failure (full disk, killed process) leaves the previous file intact, never half of a new one."""

import os
import threading
from pathlib import Path


def write_bytes(path: Path | str, data: bytes) -> None:
    """Replace ``path`` with ``data`` via a temporary file next to it. An existing file keeps its permissions."""
    target = Path(os.path.realpath(path))
    tmp = target.with_name(f".{target.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with tmp.open("wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if target.exists():
            tmp.chmod(target.stat().st_mode & 0o7777)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)


def write_text(path: Path | str, text: str, encoding: str = "utf-8") -> None:
    write_bytes(path, text.replace("\r\n", "\n").encode(encoding))
