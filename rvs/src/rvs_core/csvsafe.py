"""Protection against spreadsheet formula injection in CSV files, reversible so item tables still round-trip.

A cell that starts with = + - @ (or a tab or carriage return) is run as a formula by Excel when the CSV is opened.
Such cells get a leading apostrophe; reading removes exactly one. A value that already starts with apostrophes before such a
character gets one more, so the pair is lossless for every string."""

import re

_TRIGGER = re.compile(r"^'*[=+\-@\t\r]")


def protect(value: str) -> str:
    return "'" + value if _TRIGGER.match(value) else value


def unprotect(value: str) -> str:
    return value[1:] if value.startswith("'") and _TRIGGER.match(value) else value
