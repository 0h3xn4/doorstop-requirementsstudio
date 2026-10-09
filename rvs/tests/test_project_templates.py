from pathlib import Path

from rvs_cli.main import main
from rvs_core.project_templates import TEMPLATES, create_from_template
from rvs_core.validate import validate_project


def test_templates_are_shipped_with_their_document_trees():
    assert {"minimal", "satellite", "software"} <= set(TEMPLATES)
    sat = TEMPLATES["satellite"]
    assert [d.prefix for d in sat.documents][:2] == ["MIS", "SYS"] and sat.documents[-1].prefix == "VER"
    for t in TEMPLATES.values():
        roots = [d for d in t.documents if d.parent is None]
        assert len(roots) == 1 and t.description


def test_create_from_template_makes_a_valid_empty_project(tmp_path: Path):
    for key in TEMPLATES:
        root = tmp_path / key
        create_from_template(root, "My project", key)
        report = validate_project(root, doorstop=False)
        assert report.exit_code == 0, [f.format() for f in report.findings if f.severity.value == "error"]
        assert (root / "config" / "rules.yaml").is_file() and (root / "rvs-project.yaml").is_file()


def test_unknown_template_and_existing_project_are_refused(tmp_path: Path):
    import pytest

    with pytest.raises(ValueError, match="nope"):
        create_from_template(tmp_path / "a", "x", "nope")
    create_from_template(tmp_path / "b", "x", "minimal")
    with pytest.raises(ValueError, match="already"):
        create_from_template(tmp_path / "b", "x", "minimal")


def test_cli_init(tmp_path: Path, capsys):  # type: ignore[no-untyped-def]
    target = tmp_path / "new"
    assert main(["init", str(target), "--name", "Demo", "--template", "satellite", "--git"]) == 0
    assert "created" in capsys.readouterr().out.lower() and (target / ".git").is_dir()
    assert main(["init", str(target), "--name", "Demo"]) == 2
    assert main(["init", str(tmp_path / "x"), "--name", "D", "--template", "nope"]) == 2
    assert main(["init", "--list-templates"]) == 0


def test_a_new_project_validates_without_warnings(tmp_path):  # type: ignore[no-untyped-def]
    """Empty documents are normal in a new project: information, not a warning."""
    from rvs_core.validate import validate_project

    create_from_template(tmp_path / "p", "P", "satellite")
    report = validate_project(tmp_path / "p")
    assert report.exit_code == 0
    assert not [f for f in report.findings if f.severity.value in ("error", "warning")], report.findings
    assert any(f.code == "DOORSTOP-EMPTY-DOCUMENT" for f in report.findings)
