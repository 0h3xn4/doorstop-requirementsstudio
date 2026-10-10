"""The only package allowed to import Doorstop."""

from rvs_core.adapter import _offline_guard

_offline_guard.install()  # must run before the first Doorstop import

from rvs_core.adapter.doorstop_adapter import DoorstopProject, yaml_parser_is_fast
from rvs_core.adapter.model import DocumentInfo, Issue, ItemData, ProjectError, UnreadableItemError

__all__ = [
    "DocumentInfo",
    "DoorstopProject",
    "Issue",
    "ItemData",
    "ProjectError",
    "UnreadableItemError",
    "yaml_parser_is_fast",
]
