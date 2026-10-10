"""Doorstop reads items with libyaml (C) instead of pure-Python PyYAML: same data, much faster (V14)."""

from pathlib import Path

import pytest
import yaml
from doorstop import common

import rvs_core.adapter  # noqa: F401 - installs the loader
from conftest import EXAMPLES

pytestmark = pytest.mark.skipif(not hasattr(yaml, "CSafeLoader"), reason="PyYAML built without libyaml")


def test_doorstop_uses_the_c_loader():
    from rvs_core.adapter import yaml_parser_is_fast

    assert common.load_yaml.__defaults__ == (yaml.CSafeLoader,) and yaml_parser_is_fast()


@pytest.mark.parametrize("example", ["minimal10", "satellite300"])
def test_both_loaders_read_every_example_file_identically(example: str):
    files = [p for p in (EXAMPLES / example).rglob("*.y*ml") if ".rvs-cache" not in p.parts]
    assert len(files) > 5
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert yaml.load(text, Loader=yaml.CSafeLoader) == yaml.load(text, Loader=yaml.SafeLoader), path  # noqa: S506


def test_tricky_scalars_are_read_alike():
    text = (
        "a: yes\nb: 'no'\nc: 2024-01-02\nd: 1.0\ne: 0x1F\nf: ~\ng: |\n  line one\n  line two\nh: [a, 'b', 3]\n"
        "i: \"quoted \\u00e9\\n\"\nj: 12:30:45\nk: 010\nl: '☃'\n"
    )
    assert yaml.load(text, Loader=yaml.CSafeLoader) == yaml.load(text, Loader=yaml.SafeLoader)  # noqa: S506


def test_a_broken_item_file_is_still_a_plain_project_error(tmp_path: Path, minimal_project: Path):
    from rvs_core.adapter import DoorstopProject, ProjectError

    (minimal_project / "SYS" / "SYS-0001.yml").write_text("text: [unclosed\n", encoding="utf-8")
    with pytest.raises(ProjectError):
        DoorstopProject.open(minimal_project).items()


def test_validate_reports_a_broken_item_file_instead_of_crashing(minimal_project: Path, capsys):  # type: ignore[no-untyped-def]
    from rvs_cli.main import main
    from rvs_core.validate import validate_project

    (minimal_project / "EPS" / "EPS-0002.yml").write_text("text: [unclosed\n", encoding="utf-8")
    report = validate_project(minimal_project, doorstop=False)
    assert report.exit_code == 3
    finding = report.findings[0]
    assert finding.code == "RVS-ITEM-UNREADABLE" and "EPS-0002.yml" in finding.message and "YAML" in finding.hint
    capsys.readouterr()
    assert main(["validate", str(minimal_project)]) == 3
    captured = capsys.readouterr()
    assert "RVS-ITEM-UNREADABLE" in captured.err + captured.out
