from pathlib import Path

import pytest

from rvs_core.config import CONFIG_NAMES, ConfigError, load_project_config, packaged_default
from rvs_core.config.schema import validate_against_schema


def test_every_packaged_default_validates_against_its_schema():
    for name in CONFIG_NAMES:
        validate_against_schema(name, packaged_default(name), source=f"default {name}")


def test_unknown_key_is_rejected_with_location():
    data = packaged_default("numbering")
    data["digitz"] = 4
    with pytest.raises(ConfigError) as exc:
        validate_against_schema("numbering", data, source="config/numbering.yaml")
    assert "config/numbering.yaml" in str(exc.value) and "digitz" in str(exc.value)


def test_wrong_type_is_rejected():
    data = packaged_default("numbering")
    data["digits"] = "four"
    with pytest.raises(ConfigError, match="digits"):
        validate_against_schema("numbering", data, source="n.yaml")


def test_missing_config_files_fall_back_to_packaged_defaults(tmp_path: Path):
    (tmp_path / "rvs-project.yaml").write_text(
        "rvs_schema_version: 1\nname: Demo\ndocuments:\n  - {prefix: SYS, kind: requirements, title: System}\n"
    )
    cfg, findings = load_project_config(tmp_path)
    assert cfg.project.name == "Demo"
    assert cfg.vocab.values("status")[0] == "draft"
    assert {f.code for f in findings} >= {"RVS-CONFIG-DEFAULTED"}


def test_project_config_override_is_used(tmp_path: Path):
    (tmp_path / "rvs-project.yaml").write_text(
        "rvs_schema_version: 1\nname: Demo\ndocuments:\n  - {prefix: SYS, kind: requirements, title: System}\n"
    )
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "numbering.yaml").write_text("rvs_schema_version: 1\nsep: '-'\ndigits: 3\n")
    cfg, _ = load_project_config(tmp_path)
    assert cfg.numbering.digits_for("SYS") == 3


def test_standards_placeholders_are_listed_not_invented():
    cfg, findings = load_project_config_from_defaults()
    assert cfg.standards.unresolved()  # at least one TODO-STANDARD placeholder
    assert all(v is None for v in cfg.standards.unresolved().values())


def load_project_config_from_defaults():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        Path(d, "rvs-project.yaml").write_text(
            "rvs_schema_version: 1\nname: D\ndocuments:\n  - {prefix: SYS, kind: requirements, title: S}\n"
        )
        return load_project_config(Path(d))


def test_project_documents_must_form_a_single_rooted_tree(tmp_path: Path):
    (tmp_path / "rvs-project.yaml").write_text(
        "rvs_schema_version: 1\nname: D\ndocuments:\n"
        "  - {prefix: A, kind: requirements, title: A}\n  - {prefix: B, kind: requirements, title: B}\n"
    )
    with pytest.raises(ConfigError, match="root"):
        load_project_config(tmp_path)


def test_vocab_rejects_duplicates_and_empty_lists(tmp_path: Path):
    (tmp_path / "rvs-project.yaml").write_text(
        "rvs_schema_version: 1\nname: D\ndocuments:\n  - {prefix: SYS, kind: requirements, title: S}\n"
    )
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "vocab.yaml").write_text("rvs_schema_version: 1\nvalues:\n  status: []\n")
    with pytest.raises(ConfigError):
        load_project_config(tmp_path)


def test_attribute_names_reserved_by_doorstop_are_rejected(tmp_path: Path):
    (tmp_path / "rvs-project.yaml").write_text(
        "rvs_schema_version: 1\nname: D\ndocuments:\n  - {prefix: SYS, kind: requirements, title: S}\n"
        "free_attributes:\n  - {name: level, type: string}\n"
    )
    with pytest.raises(ConfigError, match="reserved"):
        load_project_config(tmp_path)
