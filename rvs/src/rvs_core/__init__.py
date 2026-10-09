"""RVS headless core: no GUI imports, no network imports."""

__version__ = "0.1.0"


def framework_version() -> str:
    """Version of the Doorstop framework in use (read from Doorstop itself, so it also works in frozen builds)."""
    from rvs_core.adapter.doorstop_adapter import framework_version as _version

    return _version()
