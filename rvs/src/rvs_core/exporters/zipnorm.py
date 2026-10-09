"""Make ZIP-based outputs (DOCX, XLSX) byte-identical for identical content: fixed member timestamps and no
compression (deflate output can differ between zlib builds, so storing keeps files identical across platforms)."""

import io
import zipfile
from collections.abc import Callable

_EPOCH = (1980, 1, 1, 0, 0, 0)


def normalize_zip(data: bytes, patches: dict[str, Callable[[bytes], bytes]] | None = None) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as dst:
        for info in src.infolist():
            fresh = zipfile.ZipInfo(info.filename, date_time=_EPOCH)
            fresh.compress_type = zipfile.ZIP_STORED
            fresh.external_attr = 0o600 << 16
            blob = src.read(info.filename)
            if patches and info.filename in patches:
                blob = patches[info.filename](blob)
            dst.writestr(fresh, blob)
    return out.getvalue()
