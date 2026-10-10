"""Item cache (D27): warm opens skip Doorstop's YAML parsing; never serves stale data."""

import os
import time
from pathlib import Path

from rvs_core.adapter import DoorstopProject


def _age_files(root: Path, seconds: float = 60) -> None:
    old = time.time() - seconds
    for p in root.rglob("*.yml"):
        os.utime(p, (old, old))


def test_warm_open_serves_every_item_from_the_cache(minimal_project: Path):
    _age_files(minimal_project)
    first = DoorstopProject.open(minimal_project)
    items1 = first.items()
    assert first.cache_stats.misses == 10 and first.cache_stats.hits == 0
    second = DoorstopProject.open(minimal_project)
    items2 = second.items()
    assert second.cache_stats.hits == 10 and second.cache_stats.misses == 0
    assert items1 == items2


def test_recently_modified_files_are_never_cached(minimal_project: Path):
    DoorstopProject.open(minimal_project).items()  # files are fresh: timestamps could be ambiguous
    again = DoorstopProject.open(minimal_project)
    again.items()
    assert again.cache_stats.hits == 0 and again.cache_stats.misses == 10


def test_changed_file_is_reloaded_others_stay_cached(minimal_project: Path):
    _age_files(minimal_project)
    DoorstopProject.open(minimal_project).items()
    path = minimal_project / "SYS" / "SYS-0001.yml"
    path.write_text(path.read_text().replace("title: Payload power", "title: Payload powerX"))  # size changes
    proj = DoorstopProject.open(minimal_project)
    items = {i.uid: i for i in proj.items()}
    assert items["SYS-0001"].attrs["title"] == "Payload powerX"
    assert proj.cache_stats.misses == 1 and proj.cache_stats.hits == 9


def test_same_size_edit_with_new_mtime_is_detected(minimal_project: Path):
    _age_files(minimal_project)
    DoorstopProject.open(minimal_project).items()
    path = minimal_project / "SYS" / "SYS-0001.yml"
    path.write_text(path.read_text().replace("owner: systems", "owner: systemz"))  # same size
    os.utime(path, (time.time() - 30, time.time() - 30))
    items = {i.uid: i for i in DoorstopProject.open(minimal_project).items()}
    assert items["SYS-0001"].attrs["owner"] == "systemz"


def test_document_config_change_invalidates_its_items(minimal_project: Path):
    _age_files(minimal_project)
    DoorstopProject.open(minimal_project).items()
    cfg = minimal_project / "EPS" / ".doorstop.yml"
    cfg.write_text(cfg.read_text().replace("  - verify_level\n", ""))  # fingerprint attributes change `reviewed`
    os.utime(cfg, (time.time() - 5, time.time() - 5))
    proj = DoorstopProject.open(minimal_project)
    proj.items()
    assert proj.cache_stats.misses == 3  # the three EPS items


def test_deleted_item_disappears(minimal_project: Path):
    _age_files(minimal_project)
    DoorstopProject.open(minimal_project).items()
    (minimal_project / "EPS" / "EPS-0003.yml").unlink()
    items = DoorstopProject.open(minimal_project).items()
    assert "EPS-0003" not in {i.uid for i in items} and len(items) == 9


def test_cache_lives_inside_the_project_and_is_git_ignored(minimal_project: Path):
    _age_files(minimal_project)
    DoorstopProject.open(minimal_project).items()
    cache = minimal_project / ".rvs-cache"
    assert (cache / ".gitignore").read_text().strip() == "*"
    assert any(p.suffix == ".json" for p in cache.iterdir())


def test_corrupt_cache_is_ignored(minimal_project: Path):
    _age_files(minimal_project)
    DoorstopProject.open(minimal_project).items()
    for p in (minimal_project / ".rvs-cache").glob("*.json"):
        p.write_text("{ not json")
    proj = DoorstopProject.open(minimal_project)
    assert len(proj.items()) == 10 and proj.cache_stats.misses == 10


def test_cache_does_not_alter_validation_results(minimal_project: Path):
    from rvs_core.validate import validate_project

    cold = [f.format() for f in validate_project(minimal_project, doorstop=False).findings]
    _age_files(minimal_project)
    DoorstopProject.open(minimal_project).items()
    warm = [f.format() for f in validate_project(minimal_project, doorstop=False).findings]
    assert cold == warm


def test_one_edit_parses_one_item_file_not_the_whole_document(tmp_path: Path, monkeypatch):  # type: ignore[no-untyped-def]
    """Editing one item of a big document must not re-parse its other items (each parse is ~1 ms; 1,300 per document)."""
    import shutil

    from doorstop.core.item import Item

    from conftest import EXAMPLES
    from rvs_core.authoring import EditService
    from rvs_core.validate import validate_project

    root = tmp_path / "sat"
    shutil.copytree(EXAMPLES / "satellite300", root, ignore=shutil.ignore_patterns(".rvs-cache"))
    old = time.time() - 600
    for p in root.rglob("*.yml"):
        os.utime(p, (old, old))
    validate_project(root, doorstop=False)  # warm the cache
    parses: list[str] = []
    original = Item.load

    def counting(self, reload=False):  # type: ignore[no-untyped-def]
        if reload or not self._loaded:
            parses.append(str(self.uid))
        return original(self, reload=reload)

    monkeypatch.setattr(Item, "load", counting)
    uid = next(i.uid for i in validate_project(root, doorstop=False).items if i.document == "EPS")
    parses.clear()
    EditService(root).update_item(uid, attrs={"owner": "someone"})
    validate_project(root, doorstop=False)
    assert 1 <= len(set(parses)) <= 3, sorted(set(parses))
