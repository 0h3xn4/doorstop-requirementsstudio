"""The only package allowed to import Doorstop."""

from rvs_core.adapter import _offline_guard

_offline_guard.install()  # must run before the first Doorstop import

from rvs_core.adapter.doorstop_adapter import DocumentInfo, DoorstopProject, Issue, ItemData, ProjectError

__all__ = ["DocumentInfo", "DoorstopProject", "Issue", "ItemData", "ProjectError"]
