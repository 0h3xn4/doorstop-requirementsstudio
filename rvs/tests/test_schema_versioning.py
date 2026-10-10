import pytest

from rvs_core.schema.versioning import MigrationRegistry, SchemaVersionError, migrate


def _reg() -> MigrationRegistry:
    reg = MigrationRegistry()

    @reg.register("project", 0)
    def _v0_to_v1(data: dict) -> dict:  # type: ignore[type-arg]
        data = dict(data)
        data["name"] = data.pop("title")
        return data

    return reg


def test_current_version_passes_through():
    data = {"rvs_schema_version": 1, "name": "x"}
    out, found = migrate("project", data, path="p.yaml", current=1, registry=_reg())
    assert out == data and found == 1


def test_older_version_is_migrated_in_memory():
    data = {"rvs_schema_version": 0, "title": "x"}
    out, found = migrate("project", data, path="p.yaml", current=1, registry=_reg())
    assert out == {"rvs_schema_version": 1, "name": "x"}
    assert found == 0
    assert data == {"rvs_schema_version": 0, "title": "x"}  # input untouched


def test_newer_version_fails_with_clear_message():
    with pytest.raises(SchemaVersionError) as exc:
        migrate("project", {"rvs_schema_version": 7}, path="proj/rvs-project.yaml", current=1, registry=_reg())
    msg = str(exc.value)
    assert "proj/rvs-project.yaml" in msg and "7" in msg and "1" in msg
    assert "newer" in msg.lower()


def test_missing_version_is_an_error():
    with pytest.raises(SchemaVersionError, match="rvs_schema_version"):
        migrate("project", {"name": "x"}, path="p.yaml", current=1, registry=_reg())


def test_missing_migration_step_is_an_error():
    with pytest.raises(SchemaVersionError, match="no migration"):
        migrate("project", {"rvs_schema_version": 0}, path="p.yaml", current=2, registry=MigrationRegistry())


def test_non_integer_version_is_an_error():
    with pytest.raises(SchemaVersionError):
        migrate("project", {"rvs_schema_version": "one"}, path="p.yaml", current=1, registry=_reg())
