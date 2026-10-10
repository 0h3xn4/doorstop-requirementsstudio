"""JSON Schema validation of RVS configuration files (fastjsonschema: pure Python)."""

import json
from collections.abc import Callable
from functools import cache
from importlib import resources
from typing import Any

import fastjsonschema


class ConfigError(Exception):
    """A configuration or project file cannot be used. ``code`` is the finding code."""

    def __init__(self, message: str, code: str = "RVS-CONFIG-INVALID", location: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.location = location


@cache
def _validator(name: str) -> Callable[[Any], Any]:
    text = resources.files("rvs_core.config").joinpath(f"schemas/{name}.schema.json").read_text(encoding="utf-8")
    validator: Callable[[Any], Any] = fastjsonschema.compile(json.loads(text))
    return validator


def validate_against_schema(name: str, data: Any, *, source: str) -> None:
    try:
        _validator(name)(data)
    except fastjsonschema.JsonSchemaValueException as exc:
        raise ConfigError(
            f"{source}: {exc.message}. Fix this entry in the file; the schema is rvs_core/config/schemas/{name}.schema.json.",
            location=source,
        ) from None
