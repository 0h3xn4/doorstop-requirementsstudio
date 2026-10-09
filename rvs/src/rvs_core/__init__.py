"""RVS headless core: no GUI imports, no network imports."""

from importlib.metadata import version as _dist_version

__version__ = "0.1.0"


def framework_version() -> str:
    """Installed Doorstop version, read from package metadata (does not import Doorstop)."""
    return _dist_version("doorstop")
