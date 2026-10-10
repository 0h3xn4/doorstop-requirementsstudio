"""Findings: plain-language results of validation and rule checks (spec rule 19)."""

from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"error": 0, "warning": 1, "info": 2}[self.value]


@dataclass(frozen=True)
class Finding:
    """What is wrong (message), where (location/uid) and what to do (hint)."""

    code: str
    severity: Severity
    message: str
    hint: str = ""
    location: str = ""  # path relative to the project folder
    uid: str = ""

    def format(self) -> str:
        where = " ".join(p for p in (self.uid, f"({self.location})" if self.location else "") if p)
        head = f"{self.severity.value.upper():7} {self.code}" + (f" {where}" if where else "")
        lines = [f"{head}: {self.message}"]
        if self.hint:
            lines.append(f"        -> {self.hint}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "hint": self.hint,
            "location": self.location,
            "uid": self.uid,
        }


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (f.severity.rank, f.location, f.uid, f.code, f.message))
