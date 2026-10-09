"""Schema versions: older files are migrated in memory, newer files are refused (spec rule 13)."""

from collections.abc import Callable
from typing import Any

CURRENT_VERSION = 1
VERSION_KEY = "rvs_schema_version"

Migration = Callable[[dict[str, Any]], dict[str, Any]]


class SchemaVersionError(Exception):
    """Raised when a file's schema version cannot be handled. ``code`` is the finding code."""

    def __init__(self, message: str, code: str = "RVS-SCHEMA-INVALID") -> None:
        super().__init__(message)
        self.code = code


class MigrationRegistry:
    """Migration steps per file kind: ``from_version`` -> ``from_version + 1``."""

    def __init__(self) -> None:
        self._steps: dict[tuple[str, int], Migration] = {}

    def register(self, kind: str, from_version: int) -> Callable[[Migration], Migration]:
        def deco(fn: Migration) -> Migration:
            self._steps[(kind, from_version)] = fn
            return fn

        return deco

    def step(self, kind: str, from_version: int) -> Migration | None:
        return self._steps.get((kind, from_version))


DEFAULT_REGISTRY = MigrationRegistry()  # empty: schema version 1 is the first release


def migrate(
    kind: str,
    data: dict[str, Any],
    *,
    path: str,
    current: int = CURRENT_VERSION,
    registry: MigrationRegistry = DEFAULT_REGISTRY,
) -> tuple[dict[str, Any], int]:
    """Return ``(data at the current version, version found in the file)``; the input is not modified."""
    found = data.get(VERSION_KEY)
    if found is None:
        raise SchemaVersionError(
            f"{path} has no '{VERSION_KEY}'. Add '{VERSION_KEY}: {current}' to the file.", "RVS-SCHEMA-MISSING"
        )
    if isinstance(found, bool) or not isinstance(found, int) or found < 0:
        raise SchemaVersionError(
            f"{path} has an invalid '{VERSION_KEY}' ({found!r}); it must be a whole number such as {current}.",
            "RVS-SCHEMA-INVALID",
        )
    if found > current:
        raise SchemaVersionError(
            f"{path} was written by a newer RVS (schema version {found}); this RVS supports up to version "
            f"{current}. Install a newer RVS to open it; do not edit the file by hand.",
            "RVS-SCHEMA-NEWER",
        )
    out = dict(data)
    version = found
    while version < current:
        step = registry.step(kind, version)
        if step is None:
            raise SchemaVersionError(
                f"{path} is schema version {found} and there is no migration from version {version} for "
                f"'{kind}' files. Open it with the RVS release that wrote it.",
                "RVS-SCHEMA-NOMIGRATION",
            )
        out = step(out)
        version += 1
        out[VERSION_KEY] = version
    return out, found
