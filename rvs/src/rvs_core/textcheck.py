"""Text that cannot be stored or exchanged safely: control characters and lone surrogates.

They arrive by pasting from Word (U+000B soft break), terminals or binary data. YAML cannot hold a lone surrogate (the
item file becomes unreadable), XML 1.0 (ReqIF, DOCX) and XLSX cannot hold most control characters."""

import re
from collections.abc import Mapping
from typing import Any

_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")


def first_invalid(text: str) -> str | None:
    """'U+000B' for the first character that cannot be stored, else None."""
    found = _BAD.search(text)
    return f"U+{ord(found.group(0)):04X}" if found else None


def clean(text: str) -> str:
    """``text`` with such characters replaced by U+FFFD (for outputs that must stay well formed)."""
    return _BAD.sub("�", text)


def check(field: str, value: Any) -> None:
    """Raise ValueError naming ``field`` if a string inside ``value`` has an unstorable character."""
    if isinstance(value, str):
        bad = first_invalid(value)
        if bad:
            raise ValueError(
                f"The {field} contains the control character {bad}, which cannot be stored. "
                "Remove it; it usually comes from pasting out of Word or a terminal."
            )
    elif isinstance(value, Mapping):
        for k, v in value.items():
            check(f"{field} ({k})", v)
    elif isinstance(value, list | tuple):
        for v in value:
            check(field, v)
