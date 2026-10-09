"""Reference project 2: a small satellite (about 300 requirements). All data is fictional and generated.

Generation is fully deterministic (template + parameter cycling, no randomness). A few defects are seeded
on purpose so the Problems panel has something to show; ``SEEDED_DEFECTS`` lists them and a test checks that
the rule engine finds exactly these.
"""

from collections.abc import Sequence
from pathlib import Path

import yaml

from rvs_core.adapter import DoorstopProject
from rvs_core.config.model import DocumentDecl
from rvs_core.project import create_project

DOCS = (
    DocumentDecl("MIS", "requirements", "Mission requirements"),
    DocumentDecl("SYS", "requirements", "System requirements", parent="MIS"),
    DocumentDecl("EPS", "requirements", "Electrical power subsystem", parent="SYS"),
    DocumentDecl("OBC", "requirements", "On-board computer", parent="SYS"),
    DocumentDecl("AOCS", "requirements", "Attitude and orbit control", parent="SYS"),
    DocumentDecl("TTC", "requirements", "Telemetry, tracking and command", parent="SYS"),
    DocumentDecl("STR", "requirements", "Structure", parent="SYS"),
    DocumentDecl("THM", "requirements", "Thermal control", parent="SYS"),
    DocumentDecl("PLD", "requirements", "Payload", parent="SYS"),
    DocumentDecl("VER", "verification", "Verification plan", parent="SYS"),
)

ACRONYMS = {
    "EPS": "Electrical Power Subsystem", "OBC": "On-Board Computer", "AOCS": "Attitude and Orbit Control Subsystem",
    "TT&C": "Telemetry, Tracking and Command", "RF": "Radio Frequency", "UHF": "Ultra High Frequency",
    "GNSS": "Global Navigation Satellite System", "LEO": "Low Earth Orbit", "SSO": "Sun-Synchronous Orbit",
    "MLI": "Multi-Layer Insulation", "PCDU": "Power Control and Distribution Unit", "PLD": "Payload",
}  # fmt: skip

# (title, text template, type, verification method); "{v}" cycles through the values of the document.
Template = tuple[str, str, str, str]
SPEC: dict[str, tuple[int, Sequence[str], Sequence[Template]]] = {
    "MIS": (12, ["550", "600", "650", "5", "7"], [
        ("Orbit {v}", "The mission shall be conducted in a {v} km sun-synchronous LEO orbit.", "operational", "analysis"),
        ("Lifetime {v}", "The spacecraft shall operate for at least {v} years.", "performance", "analysis"),
        ("Data return {v}", "The mission shall return at least {v} GB of payload data per day.", "performance", "test"),
    ]),
    "SYS": (50, ["28", "40", "60", "95", "120", "15"], [
        ("Mass {v}", "The spacecraft launch mass shall not exceed {v} kg.", "design", "inspection"),
        ("Power {v}", "The spacecraft shall provide {v} W orbit-average power to the payload.", "performance", "analysis"),
        ("Autonomy {v}", "The spacecraft shall operate autonomously for {v} hours without ground contact.", "operational", "test"),
        ("Pointing {v}", "The spacecraft shall point the payload with an error below {v} arcseconds.", "performance", "analysis"),
        ("Temperature {v}", "The spacecraft shall survive a hot case of {v} degrees Celsius.", "environmental", "test"),
    ]),
    "EPS": (40, ["24", "28", "33", "5", "12", "50"], [
        ("Bus voltage {v}", "The EPS shall provide a regulated {v} V main bus.", "functional", "test"),
        ("Battery {v}", "The EPS shall store at least {v} Wh in the battery.", "performance", "test"),
        ("Array {v}", "The solar array shall deliver {v} W at end of life.", "performance", "analysis"),
        ("PCDU {v}", "The PCDU shall switch off non-essential loads below {v} percent state of charge.", "functional", "test"),
    ]),
    "OBC": (40, ["8", "64", "256", "100", "1000"], [
        ("Memory {v}", "The OBC shall provide at least {v} MB of non-volatile storage.", "performance", "inspection"),
        ("Cycle {v}", "The OBC shall execute the control cycle every {v} ms.", "performance", "test"),
        ("Housekeeping {v}", "The OBC shall collect housekeeping telemetry every {v} seconds.", "functional", "test"),
        ("Watchdog {v}", "The OBC shall reset itself if the watchdog is not serviced within {v} seconds.", "functional", "test"),
    ]),
    "AOCS": (40, ["0.1", "0.5", "1", "5", "10"], [
        ("Accuracy {v}", "The AOCS shall estimate attitude with an error below {v} degrees.", "performance", "analysis"),
        ("Detumble {v}", "The AOCS shall reduce the angular rate below {v} degrees per second after separation.", "functional", "test"),
        ("Slew {v}", "The AOCS shall slew the spacecraft by 30 degrees within {v} minutes.", "performance", "test"),
        ("GNSS {v}", "The AOCS shall obtain a GNSS position fix within {v} minutes after power-on.", "functional", "test"),
    ]),
    "TTC": (35, ["9.6", "38.4", "2", "20", "435"], [
        ("Downlink {v}", "The TT&C subsystem shall support a downlink rate of {v} kbit/s.", "performance", "test"),
        ("Uplink {v}", "The TT&C subsystem shall accept telecommands at {v} kbit/s.", "interface", "test"),
        ("Link margin {v}", "The UHF link shall have a margin of at least {v} dB.", "performance", "analysis"),
        ("RF output {v}", "The RF output power shall not exceed {v} dBm.", "design", "test"),
    ]),
    "STR": (25, ["3", "10", "100", "12", "45"], [
        ("Frequency {v}", "The structure shall have a first natural frequency above {v} Hz.", "performance", "test"),
        ("Load {v}", "The structure shall withstand a quasi-static load of {v} g.", "environmental", "analysis"),
        ("Mass {v}", "The primary structure mass shall not exceed {v} kg.", "design", "inspection"),
    ]),
    "THM": (25, ["-10", "50", "5", "-30", "70"], [
        ("Battery temp {v}", "The thermal control shall keep the battery above {v} degrees Celsius.", "performance", "analysis"),
        ("Heater {v}", "The thermal control shall limit heater power to {v} W.", "performance", "test"),
        ("MLI {v}", "The MLI blanket shall cover at least {v} percent of the external surface.", "design", "inspection"),
    ]),
    "PLD": (30, ["2", "5", "20", "500", "1000"], [
        ("Resolution {v}", "The payload shall achieve a ground sample distance of {v} m.", "performance", "analysis"),
        ("Swath {v}", "The payload shall image a swath of at least {v} km.", "performance", "test"),
        ("Data rate {v}", "The payload shall generate no more than {v} Mbit/s of raw data.", "interface", "test"),
    ]),
}  # fmt: skip

SEEDED_DEFECTS = {
    "RVS-RULE-SHALL-PRESENT": ["EPS-0001"],
    "RVS-RULE-VAGUE-WORDS": ["OBC-0001"],
    "RVS-RULE-SINGLE-STATEMENT": ["AOCS-0001"],
    "RVS-RULE-HAS-PARENT": ["TTC-0001"],
    "RVS-RULE-VERIFIED-WHEN-APPROVED": ["THM-0001"],
    "RVS-RULE-UNDEFINED-ACRONYM": ["PLD-0001"],
    "RVS-RULE-VERIFY-METHOD-SET": ["STR-0001"],
}  # fmt: skip

_VER_STATUS = ("planned", "in-progress", "passed", "failed", "waived", "passed", "planned")


def _text(prefix: str, n: int) -> tuple[str, str, str, str]:
    count, values, templates = SPEC[prefix]
    title, text, rtype, method = templates[n % len(templates)]
    v = values[(n // len(templates)) % len(values)]
    return f"{title.format(v=v)} #{n + 1}", text.format(v=v), rtype, method


def _level_for(prefix: str) -> str:
    return {"EPS": "subsystem", "OBC": "subsystem", "AOCS": "subsystem", "TTC": "subsystem", "STR": "subsystem",
            "THM": "subsystem", "PLD": "subsystem", "SYS": "system", "MIS": "system"}[prefix]  # fmt: skip


def build_satellite_project(root: Path) -> DoorstopProject:
    proj = create_project(root, "Example satellite (fictional data)", DOCS)
    glossary = {
        "rvs_schema_version": 1,
        "terms": [{"term": "Eclipse", "definition": "Period in which the spacecraft is in the shadow of the Earth."}],
        "acronyms": [{"acronym": a, "expansion": e} for a, e in sorted(ACRONYMS.items())],
    }
    (root / "config" / "glossary.yaml").write_text(
        yaml.safe_dump(glossary, sort_keys=True), encoding="utf-8", newline="\n"
    )
    uids: dict[str, list[str]] = {}
    parent_of = {"SYS": "MIS", **{p: "SYS" for p in ("EPS", "OBC", "AOCS", "TTC", "STR", "THM", "PLD")}}
    for prefix, (count, _values, _templates) in SPEC.items():
        uids[prefix] = []
        for n in range(count):
            title, text, rtype, method = _text(prefix, n)
            attrs = {
                "title": title, "type": rtype, "verify_method": method, "verify_level": _level_for(prefix),
                "owner": prefix.lower(), "priority": ("high", "medium", "low")[n % 3],
                "status": "draft" if n % 5 else "reviewed",
            }  # fmt: skip
            if prefix == "EPS" and n == 0:
                text = "The EPS provides a regulated 28 V main bus."  # seeded: no 'shall'
            if prefix == "OBC" and n == 0:
                text = "The OBC shall provide adequate non-volatile storage."  # seeded: vague word
            if prefix == "AOCS" and n == 0:
                text = "The AOCS shall estimate attitude. The AOCS shall report the estimate every second."  # seeded
            if prefix == "THM" and n == 0:
                attrs["status"] = "approved"  # seeded: approved but nothing verifies it
            if prefix == "PLD" and n == 0:
                text = "The payload shall provide a LIDAR altimeter mode."  # seeded: undefined acronym
            if prefix == "STR" and n == 0:
                attrs["verify_method"] = ""  # seeded: no verification method
            item = proj.add_item(prefix, text, attrs=attrs, level=f"1.{n + 1}")
            uids[prefix].append(item.uid)
            parent = parent_of.get(prefix)
            if parent and not (prefix == "TTC" and n == 0):  # TTC-0001 seeded without a parent
                proj.link(item.uid, uids[parent][n % len(uids[parent])])
    # Verification plan: one item per 5th subsystem requirement; verified requirements may be approved.
    targets = [u for p in ("EPS", "OBC", "AOCS", "TTC", "STR", "PLD") for u in uids[p][1::5]]
    for n, target in enumerate(targets):
        item = proj.get_item(target)
        method = str(item.attrs["verify_method"])
        proj.add_item(
            "VER",
            f"Verify {target} by {method}.",
            attrs={
                "title": f"Verify {target}", "proc_id": f"VER-{target}", "verify_method": method,
                "verify_level": "subsystem", "v_status": _VER_STATUS[n % len(_VER_STATUS)],
                "link_verifies": [target],
            },
            level=f"1.{n + 1}",
            derived=True,
        )  # fmt: skip
        if n % 3 == 0:
            proj.update_item(target, attrs={"status": "approved"})
    return proj
