"""Acronym detection shared by the undefined-acronym rule and the editor's highlighting."""

import re
from collections.abc import Collection
from dataclasses import dataclass

# An all-caps token (digits and '&' allowed inside, e.g. TT&C, S2), not part of a longer word,
# and not an item ID such as EPS-0001 (a prefix followed by '-' and digits).
_ACRONYM = re.compile(r"(?<![\w&])[A-Z][A-Z0-9&]*[A-Z0-9](?![\w&])(?!-\d)")


@dataclass(frozen=True)
class AcronymHit:
    text: str
    start: int
    end: int
    defined: bool


def find_acronyms(
    text: str, known: Collection[str], *, min_length: int = 2, ignore: Collection[str] = ()
) -> list[AcronymHit]:
    hits = []
    for m in _ACRONYM.finditer(text):
        token = m.group(0)
        if len(token) < min_length or token in ignore or token.isdigit():
            continue
        hits.append(AcronymHit(token, m.start(), m.end(), token in known))
    return hits
