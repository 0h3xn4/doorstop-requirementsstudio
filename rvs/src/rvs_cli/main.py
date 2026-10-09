"""``rvs`` entry point."""

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import rvs_core
from rvs_core.findings import Severity
from rvs_core.validate import validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rvs", description="Requirements & Verification Studio")
    parser.add_argument("--version", action="store_true", help="print tool and framework versions")
    sub = parser.add_subparsers(dest="command")
    val = sub.add_parser("validate", help="validate a project folder (exit 0 ok, 1 errors, 3 project cannot be loaded)")
    val.add_argument("project", type=Path)
    val.add_argument("--format", choices=("text", "json"), default="text")
    val.add_argument("--strict", action="store_true", help="treat warnings as errors")
    return parser


def _validate(args: argparse.Namespace) -> int:
    report = validate_project(args.project, strict=args.strict)
    errors, warnings = report.count(Severity.ERROR), report.count(Severity.WARNING)
    if args.format == "json":
        print(json.dumps({"exit_code": report.exit_code, "findings": [f.to_dict() for f in report.findings]}, indent=2))
    else:
        for finding in report.findings:
            print(finding.format())
        print(f"{errors} errors, {warnings} warnings, {report.count(Severity.INFO)} info")
    return report.exit_code


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"rvs {rvs_core.__version__} (doorstop {rvs_core.framework_version()})")
        return 0
    if args.command == "validate":
        return _validate(args)
    parser.print_help()
    return 0
