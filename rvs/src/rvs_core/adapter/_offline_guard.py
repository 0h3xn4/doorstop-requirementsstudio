"""Keep network-capable libraries out of the RVS process (spec rule 1/3, DEVIATIONS V01).

Doorstop 3.2 imports ``bottle`` (for its HTML publisher) and ``plantuml_markdown`` (which pulls in
``requests``/``urllib3``/``ssl``/``http.client``) at import time, although RVS never publishes through
them. Before Doorstop is imported we register inert placeholder modules under those names, so none of the
real libraries is ever loaded. Doorstop's source is not modified; any use of a placeholder raises.
"""

import sys
from types import ModuleType
from typing import Any

BLOCKED = ("bottle", "plantuml_markdown")


class OfflineModuleError(RuntimeError):
    pass


def _refuse(name: str) -> Any:
    raise OfflineModuleError(f"'{name}' is disabled in RVS: the application never uses the network.")


class _Disabled:
    """Instantiable (Doorstop builds one at import time) but unusable placeholder object."""

    def __init__(self, *_a: Any, **_k: Any) -> None:
        pass

    def __getattr__(self, attr: str) -> Any:
        return _refuse(attr)


class _Placeholder(ModuleType):
    def __getattr__(self, attr: str) -> Any:
        if attr.startswith("__"):
            raise AttributeError(attr)
        if attr[:1].isupper():
            return _Disabled  # classes: creatable, never usable

        def blocked(*_a: Any, **_k: Any) -> Any:
            return _refuse(f"{self.__name__}.{attr}")

        return blocked


def install() -> None:
    for name in BLOCKED:
        if name not in sys.modules:
            sys.modules[name] = _Placeholder(name)
