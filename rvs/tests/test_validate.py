import shutil
from pathlib import Path

import yaml

from rvs_core.findings import Severity
from rvs_core.validate import validate_project


def _codes(report) -> set[str]:  # type: ignore[no-untyped-def]
    return {f.code for f in report.findings}


def test_minimal_project_has_no_errors(minimal_project: Path):
    report = validate_project(minimal_project)
    assert report.exit_code == 0, [f.format() for f in report.findings]
    assert not [f for f in report.findings if f.severity is Severity.ERROR]


def test_missing_project_file(tmp_path: Path):
    report = validate_project(tmp_path)
    assert report.exit_code == 3 and "RVS-PROJECT-MISSING" in _codes(report)


def test_newer_project_schema_version_is_refused(minimal_project: Path):
    p = minimal_project / "rvs-project.yaml"
    data = yaml.safe_load(p.read_text())
    data["rvs_schema_version"] = 99
    p.write_text(yaml.safe_dump(data))
    report = validate_project(minimal_project)
    assert report.exit_code == 3 and "RVS-SCHEMA-NEWER" in _codes(report)
    assert "99" in report.findings[0].message


def test_newer_item_schema_version_is_refused(minimal_project: Path):
    item = minimal_project / "SYS" / "SYS-0001.yml"
    item.write_text(item.read_text().replace("rvs_schema_version: 1", "rvs_schema_version: 42"))
    report = validate_project(minimal_project)
    assert report.exit_code == 3 and "RVS-SCHEMA-NEWER" in _codes(report)


def test_value_outside_vocabulary_is_an_error_with_uid_and_hint(minimal_project: Path):
    item = minimal_project / "SYS" / "SYS-0001.yml"
    item.write_text(item.read_text().replace("status: draft", "status: finished"))
    report = validate_project(minimal_project)
    f = next(f for f in report.findings if f.code == "RVS-ATTR-VOCAB")
    assert f.uid == "SYS-0001" and "finished" in f.message and "draft" in f.hint
    assert report.exit_code == 1


def test_unknown_extended_attribute_warns(minimal_project: Path):
    item = minimal_project / "SYS" / "SYS-0001.yml"
    item.write_text(item.read_text() + "mystery: 1\n")
    report = validate_project(minimal_project)
    f = next(f for f in report.findings if f.code == "RVS-ATTR-UNKNOWN")
    assert f.severity is Severity.WARNING and f.uid == "SYS-0001"
    assert report.exit_code == 0


def test_declared_free_attribute_is_accepted(minimal_project: Path):
    p = minimal_project / "rvs-project.yaml"
    data = yaml.safe_load(p.read_text())
    data["free_attributes"] = [{"name": "mystery", "type": "string"}]
    p.write_text(yaml.safe_dump(data))
    item = minimal_project / "SYS" / "SYS-0001.yml"
    item.write_text(item.read_text() + "mystery: hello\n")
    assert "RVS-ATTR-UNKNOWN" not in _codes(validate_project(minimal_project))


def test_wrong_attribute_type_is_an_error(minimal_project: Path):
    item = minimal_project / "SYS" / "SYS-0001.yml"
    item.write_text(item.read_text().replace("title:", "title: [a, b]\nold_title:", 1))
    report = validate_project(minimal_project)
    assert "RVS-ATTR-TYPE" in _codes(report)


def test_document_not_declared_in_project_file(minimal_project: Path):
    p = minimal_project / "rvs-project.yaml"
    data = yaml.safe_load(p.read_text())
    data["documents"] = [d for d in data["documents"] if d["prefix"] != "EPS"]
    p.write_text(yaml.safe_dump(data))
    assert "RVS-DOC-UNDECLARED" in _codes(validate_project(minimal_project))


def test_declared_document_missing_on_disk(minimal_project: Path):
    shutil.rmtree(minimal_project / "EPS")
    assert "RVS-DOC-MISSING" in _codes(validate_project(minimal_project))


def test_numbering_mismatch_is_reported(minimal_project: Path):
    cfg = minimal_project / "config"
    cfg.mkdir(exist_ok=True)
    (cfg / "numbering.yaml").write_text("rvs_schema_version: 1\nsep: '-'\ndigits: 5\n")
    assert "RVS-DOC-NUMBERING" in _codes(validate_project(minimal_project))


def test_fingerprint_attributes_must_match_template(minimal_project: Path):
    doc = minimal_project / "SYS" / ".doorstop.yml"
    doc.write_text(doc.read_text().replace("  - verify_level\n", ""))
    assert "RVS-DOC-FINGERPRINT" in _codes(validate_project(minimal_project))


def test_doorstop_own_findings_are_included(minimal_project: Path):
    # break a link target: Doorstop reports it, RVS surfaces it with a code and the item uid
    item = minimal_project / "EPS" / "EPS-0001.yml"
    text = item.read_text()
    assert "SYS-0002" in text
    item.write_text(text.replace("- SYS-0002", "- SYS-0099", 1))
    report = validate_project(minimal_project)
    # Doorstop's "linked to unknown item" is reported once, with RVS's own code
    assert any(
        f.code == "RVS-LINK-TARGET-MISSING" and "SYS-0099" in f.message and f.uid == "EPS-0001" for f in report.findings
    )
    assert not any(f.code.startswith("DOORSTOP-") and "SYS-0099" in f.message for f in report.findings)


def test_unresolved_standard_placeholders_are_info(minimal_project: Path):
    report = validate_project(minimal_project)
    f = next(f for f in report.findings if f.code == "RVS-STD-PLACEHOLDER")
    assert f.severity is Severity.INFO


def test_validation_is_deterministic(minimal_project: Path):
    a = [f.format() for f in validate_project(minimal_project).findings]
    b = [f.format() for f in validate_project(minimal_project).findings]
    assert a == b


def test_validation_does_not_modify_any_file(minimal_project: Path):
    def snap() -> dict[str, bytes]:
        return {
            str(p): p.read_bytes()
            for p in sorted(minimal_project.rglob("*"))
            if p.is_file() and ".rvs-cache" not in p.parts
        }

    before = snap()
    validate_project(minimal_project)
    assert snap() == before
