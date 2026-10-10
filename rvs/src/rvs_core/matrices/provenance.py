"""Provenance block carried by every output (spec rule 18)."""

import getpass
import os
from dataclasses import dataclass
from datetime import UTC, datetime

import rvs_core
from rvs_core.config import ProjectConfig


@dataclass(frozen=True)
class Provenance:
    tool_version: str
    framework_version: str
    project: str
    baseline: str
    generated: datetime
    user: str

    def lines(self) -> list[str]:
        return [
            f"Project: {self.project}",
            f"Baseline: {self.baseline}",
            f"Generated: {self.generated.strftime('%Y-%m-%d %H:%M:%S')} by {self.user}",
            f"Tool: rvs {self.tool_version} (doorstop {self.framework_version})",
        ]

    def to_dict(self) -> dict[str, str]:
        return {
            "project": self.project,
            "baseline": self.baseline,
            "generated": self.generated.strftime("%Y-%m-%d %H:%M:%S"),
            "user": self.user,
            "tool_version": self.tool_version,
            "framework_version": self.framework_version,
        }

    @classmethod
    def now(cls, cfg: ProjectConfig, user: str | None = None, baseline: str = "working copy") -> "Provenance":
        try:
            who = user or getpass.getuser()
        except Exception:  # noqa: BLE001 - no login name on locked-down hosts
            who = "unknown"
        return cls(rvs_core.__version__, rvs_core.framework_version(), cfg.project.name, baseline, _now(), who)


def _now() -> datetime:
    """The generation time. ``SOURCE_DATE_EPOCH`` (the reproducible-builds convention, UTC seconds) pins it, so two
    exports of the same project made with the same value are byte-identical."""
    raw = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if raw.isdigit():
        try:
            return datetime.fromtimestamp(int(raw), UTC).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            pass
    return datetime.now()  # noqa: DTZ005 - local wall-clock time, shown to the user as is
