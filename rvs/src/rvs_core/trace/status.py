"""Verification status conventions of this tool (not taken from a standard; see decision D38)."""

from collections.abc import Iterable

NOT_VERIFIED = "not verified"
ORDER = ("passed", "in-progress", "planned", "failed", "waived", NOT_VERIFIED)


def aggregate_status(statuses: Iterable[str]) -> str:
    """One status for a requirement from the statuses of all items verifying it.

    failed if any failed; passed if all passed; waived if all waived; planned if all planned;
    nothing verifying it: 'not verified'; any other mixture: in-progress.
    """
    s = [x for x in statuses if x]
    if not s:
        return NOT_VERIFIED
    if "failed" in s:
        return "failed"
    for single in ("passed", "waived", "planned"):
        if all(x == single for x in s):
            return single
    return "in-progress"
