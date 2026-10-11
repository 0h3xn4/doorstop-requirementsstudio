import subprocess
import sys

import rvs_core


def test_version_exposes_tool_and_framework():
    assert rvs_core.__version__
    assert rvs_core.framework_version() == "3.2"


def test_cli_version_flag():
    out = subprocess.run([sys.executable, "-m", "rvs_cli", "--version"], capture_output=True, text=True, check=False)
    assert out.returncode == 0
    assert rvs_core.__version__ in out.stdout
    assert "doorstop 3.2" in out.stdout


def test_every_argument_and_command_has_help_text() -> None:
    import argparse

    from rvs_cli.main import build_parser

    missing: list[str] = []

    def walk(parser: argparse.ArgumentParser, path: list[str]) -> None:
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                described = {a.dest for a in action._choices_actions if a.help}
                for name, sub in action.choices.items():
                    if name not in described:
                        missing.append(" ".join([*path, name]))
                    walk(sub, [*path, name])
            elif not isinstance(action, argparse._HelpAction) and not action.help:
                missing.append(" ".join([*path, action.dest]))

    walk(build_parser(), ["rvs"])
    assert not missing, f"no help text for: {missing}"
