"""The offline user guide: built from docs/guide, current, and in step with the application."""

import argparse
import importlib.util
import re
from pathlib import Path

import pytest

from rvs_cli.main import build_parser
from rvs_core.guide import guide_path

ROOT = Path(__file__).resolve().parents[1]


def _builder():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("build_guide", ROOT / "scripts" / "build_guide.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built() -> str:
    return _builder().build()


@pytest.fixture(scope="module")
def sources() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "docs" / "guide").glob("*.md")))


def test_bundled_guide_is_current(built: str):
    path = guide_path()
    assert path is not None, "run python scripts/build_guide.py"
    assert path.read_text(encoding="utf-8") == built, "docs/guide changed: run python scripts/build_guide.py"


def test_guide_is_self_contained_and_offline(built: str):
    assert not re.search(r"""(?:src|href)=["'](?:https?:)?//""", built)
    assert "<script" not in built and "<link" not in built
    for needle in ("http://", "https://"):
        assert needle not in built


def test_guide_has_both_walkthroughs_and_a_contents_list(built: str):
    for anchor in ("guided-walkthrough", "expert-walkthrough", "change-control", "command-reference"):
        assert f'id="{anchor}"' in built and f'href="#{anchor}"' in built


def test_every_cli_command_is_documented(sources: str):
    def paths(parser: argparse.ArgumentParser, prefix: str) -> list[str]:
        out = []
        for action in parser._actions:  # noqa: SLF001
            if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
                for name, sub in action.choices.items():
                    out.append(f"{prefix} {name}".strip())
                    out += paths(sub, f"{prefix} {name}")
        return out

    commands = paths(build_parser(), "rvs")
    assert len(commands) > 10
    missing = [c for c in commands if f"`{c}" not in sources and f"{c} " not in sources and f"### {c}" not in sources]
    assert not missing, f"commands missing from docs/guide/06-command-reference.md: {missing}"


def test_every_cli_option_is_documented(sources: str):
    flags = set()

    def walk(parser: argparse.ArgumentParser) -> None:
        for action in parser._actions:  # noqa: SLF001
            if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
                for sub in action.choices.values():
                    walk(sub)
            else:
                flags.update(o for o in action.option_strings if o.startswith("--") and o != "--help")

    walk(build_parser())
    missing = sorted(f for f in flags if f not in sources)
    assert not missing, f"options missing from the guide: {missing}"


def test_every_config_file_rule_and_finding_code_is_documented(sources: str):
    config = ROOT / "src" / "rvs_core" / "config" / "defaults"
    missing = [f"config/{p.name}" for p in sorted(config.glob("*.yaml")) if f"config/{p.name}" not in sources]
    assert not missing, missing
    import yaml

    rules = [r["id"] for r in yaml.safe_load((config / "rules.yaml").read_text())["rules"]]
    code_missing = [r for r in rules if f"`{r}`" not in sources or f"RVS-RULE-{r.upper()}" not in sources]
    assert not code_missing, code_missing
    codes = set()
    for path in (ROOT / "src").rglob("*.py"):
        if path.name == "reqif.py":  # its RVS-xx-... strings are ReqIF identifiers, not finding codes
            continue
        codes |= set(re.findall(r'"(RVS-[A-Z0-9]+-[A-Z0-9-]*[A-Z0-9])"', path.read_text(encoding="utf-8")))
    undocumented = sorted(c for c in codes if c not in sources)
    assert not undocumented, f"finding codes missing from docs/guide/07-reference.md: {undocumented}"


def test_every_shortcut_is_in_the_guide(built: str):
    from rvs_gui.shortcuts import SHORTCUTS

    for key, _description in SHORTCUTS.values():
        assert f"<strong>{key}</strong>" in built


def test_every_template_attribute_has_help():
    from rvs_core.config.loader import packaged_default

    for kind in packaged_default("templates")["kinds"].values():
        for attr in kind["attributes"]:
            if attr["name"] not in ("rvs_schema_version", "link_refs"):
                assert attr.get("help"), attr["name"]


def test_cli_guide_command_copies_the_guide(tmp_path: Path):
    from rvs_cli.main import main

    out = tmp_path / "guide.html"
    assert main(["guide", "-o", str(out)]) == 0
    assert "Expert walkthrough" in out.read_text(encoding="utf-8")
