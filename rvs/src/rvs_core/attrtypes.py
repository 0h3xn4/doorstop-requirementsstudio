"""Attribute value types ("is this value a date / an item list / ..."), shared by validation and editing."""

import re
from datetime import date
from typing import Any

UID = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+\Z")


def is_str(v: Any) -> bool:
    return isinstance(v, str)


def is_iso_date(value: str) -> bool:
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def type_ok(kind: str, value: Any) -> bool:
    if kind in ("string", "text", "enum"):
        return is_str(value)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "date":
        return isinstance(value, date) or (is_str(value) and is_iso_date(value))
    if kind == "string-list":
        return isinstance(value, list) and all(is_str(v) for v in value)
    if kind == "uid-list":
        return isinstance(value, list) and all(is_str(v) and UID.match(v) for v in value)
    if kind == "ref-list":
        return isinstance(value, list) and all(
            isinstance(v, dict) and set(v) == {"docno", "revision"} and all(is_str(x) for x in v.values())
            for v in value
        )
    return False


TYPE_HINT = {
    "string": "text",
    "text": "text",
    "enum": "one of the allowed values",
    "int": "a whole number",
    "date": "a date written YYYY-MM-DD",
    "string-list": "a list of text values",
    "uid-list": "a list of item IDs such as SYS-0001",
    "ref-list": "a list of {docno, revision} entries",
}
