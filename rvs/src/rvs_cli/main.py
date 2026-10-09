"""``rvs`` entry point."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import rvs_core
from rvs_cli import changecontrol
from rvs_core.changecontrol.baselines import BaselineError
from rvs_core.exporters import BINARY_FORMATS, TABLE_FORMATS
from rvs_core.exporters.export_request import ExportRequest, build_output
from rvs_core.exporters.itemsio import (
    apply_import,
    plan_import,
    read_csv,
    read_xlsx,
)
from rvs_core.findings import Severity
from rvs_core.matrices import (
    Provenance,
)
from rvs_core.validate import validate_project
from rvs_core.vcs.git import GitError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rvs", description="Requirements & Verification Studio")
    parser.add_argument("--version", action="store_true", help="print tool and framework versions")
    sub = parser.add_subparsers(dest="command")

    val = sub.add_parser("validate", help="validate a project folder (exit 0 ok, 1 errors, 3 project cannot be loaded)")
    val.add_argument("project", type=Path)
    val.add_argument("--format", choices=("text", "json"), default="text")
    val.add_argument("--strict", action="store_true", help="treat warnings as errors")
    val.add_argument("--fast", action="store_true", help="skip Doorstop's own tree validation (RVS checks still run)")

    exp = sub.add_parser("export", help="write a matrix or report (CSV or JSON; DOCX/PDF/HTML/XLSX arrive in M4)")
    exp.add_argument("project", type=Path)
    what = exp.add_mutually_exclusive_group(required=True)
    what.add_argument("--vcm", action="store_true", help="verification control matrix")
    what.add_argument("--trace", metavar="SRC:DST[:up|down]", help="traceability matrix between two documents")
    what.add_argument("--coverage", action="store_true", help="coverage per document")
    what.add_argument("--impact", metavar="UID", help="items affected by a change to UID")
    what.add_argument("--items", action="store_true", help="all items as a table (csv or xlsx; re-importable)")
    what.add_argument("--spec", action="store_true", help="specification document (html, docx or pdf); see --document")
    exp.add_argument("--format", choices=TABLE_FORMATS, default="csv")
    exp.add_argument("--output", "-o", type=Path, help="write to this file instead of standard output")
    exp.add_argument("--document", action="append", default=[], help="VCM and --spec: only this document (repeatable)")
    exp.add_argument("--method", action="append", default=[], help="VCM: only this verification method (repeatable)")
    exp.add_argument("--level", action="append", default=[], help="VCM: only this verification level (repeatable)")
    exp.add_argument("--status", action="append", default=[], help="VCM: only this verification status (repeatable)")
    exp.add_argument("--baseline", help="export the project as it was at this baseline")
    exp.add_argument("--only-gaps", action="store_true", help="VCM: only requirements that nothing verifies")

    changecontrol.add_parsers(sub)

    imp = sub.add_parser(
        "import", help="import items from a CSV or XLSX file written by 'export --items' (exit 0 ok, 1 errors)"
    )
    imp.add_argument("project", type=Path)
    imp.add_argument("file", type=Path)
    imp.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    imp.add_argument("--skip-errors", action="store_true", help="apply the valid rows even if some rows have errors")
    imp.add_argument("--reason", default="", help="why the items change (required for baselined items)")
    imp.add_argument("--cr", default=None, help="change request the imported edits belong to")
    imp.add_argument("--user", default=None, help="name recorded in the item history (default: login name)")
    return parser


def _validate(args: argparse.Namespace) -> int:
    report = validate_project(args.project, strict=args.strict, doorstop=not args.fast)
    errors, warnings = report.count(Severity.ERROR), report.count(Severity.WARNING)
    if args.format == "json":
        print(json.dumps({"exit_code": report.exit_code, "findings": [f.to_dict() for f in report.findings]}, indent=2))
    else:
        for finding in report.findings:
            print(finding.format())
        print(f"{errors} errors, {warnings} warnings, {report.count(Severity.INFO)} info")
    return report.exit_code


def _request(args: argparse.Namespace) -> ExportRequest:
    if args.items:
        kind = "items"
    elif args.spec:
        kind = "spec"
    elif args.vcm:
        kind = "vcm"
    elif args.trace:
        kind = "trace"
    elif args.coverage:
        kind = "coverage"
    else:
        kind = "impact"
    trace = ("", "", "down")
    if kind == "trace":
        parts = args.trace.split(":")
        if len(parts) not in (2, 3):
            raise ValueError("--trace needs SRC:DST or SRC:DST:up|down, for example SYS:EPS")
        trace = (parts[0], parts[1], parts[2] if len(parts) == 3 else "down")
    return ExportRequest(
        kind, args.format, tuple(args.document), tuple(args.method), tuple(args.level), tuple(args.status),
        args.only_gaps, trace, args.impact or "",
    )  # fmt: skip


def _export(args: argparse.Namespace) -> int:
    if args.format in BINARY_FORMATS and not args.output:
        print(f"rvs export: --format {args.format} writes a binary file; give --output FILE.", file=sys.stderr)
        return 2
    folder, label = args.project, None
    try:
        if args.baseline:
            from rvs_core.changecontrol.baselines import snapshot_dir

            folder, label = snapshot_dir(args.project, args.baseline), args.baseline
        report = validate_project(folder, doorstop=False)
        if report.exit_code == 3 or report.config is None:
            for f in report.findings:
                print(f.format(), file=sys.stderr)
            return 3
        assert report.graph is not None
        if label is None:
            from rvs_core.changecontrol.baselines import current_label

            label = current_label(args.project)
        data = build_output(
            _request(args), report.config, report.items, report.graph, Provenance.now(report.config, baseline=label)
        )
    except (ValueError, BaselineError, GitError) as exc:
        print(f"rvs export: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.write_bytes(data)
    else:
        sys.stdout.write(data.decode("utf-8"))
    return 0


def _import(args: argparse.Namespace) -> int:
    path: Path = args.file
    if not path.is_file():
        print(f"rvs import: the file {path} does not exist.", file=sys.stderr)
        return 2
    suffix = path.suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        print("rvs import: the file must be .csv or .xlsx (written by 'rvs export --items').", file=sys.stderr)
        return 2
    report = validate_project(args.project, doorstop=False)
    if report.exit_code == 3 or report.config is None:
        for f in report.findings:
            print(f.format(), file=sys.stderr)
        return 3
    try:
        data = path.read_bytes()
        rows = read_csv(data) if suffix == ".csv" else read_xlsx(data)
    except Exception as exc:  # noqa: BLE001 - corrupt or non-spreadsheet file: say so plainly
        print(f"rvs import: {path.name} could not be read ({exc}).", file=sys.stderr)
        return 2
    plan = plan_import(report.config, report.items, rows, why=args.reason)
    for r in plan.results:
        if r.action == "unchanged":
            continue
        if r.action == "error":
            print(f"row {r.row:>4}  ERROR   {r.message}")
        else:
            print(f"row {r.row:>4}  {r.action:<7} {r.uid or '(new)':<10} {', '.join(r.changes)}")
    if args.dry_run:
        print(
            f"Dry run: {plan.count('create')} to create, {plan.count('update')} to update, {plan.count('unchanged')} unchanged, {len(plan.errors)} errors."
        )
        return 1 if plan.errors else 0
    try:
        result = apply_import(
            args.project, plan, user=args.user, why=args.reason, skip_errors=args.skip_errors, change_request=args.cr
        )
    except ValueError as exc:
        print(f"rvs import: {exc}", file=sys.stderr)
        return 2
    if not result.applied:
        print(
            f"{result.errors} row(s) have errors, so nothing was imported. Fix them, or use --skip-errors to import the valid rows."
        )
        return 1
    print(
        f"{result.created} created, {result.updated} updated, {result.unchanged} unchanged, {result.errors} errors skipped."
    )
    return 1 if result.errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"rvs {rvs_core.__version__} (doorstop {rvs_core.framework_version()})")
        return 0
    if args.command == "validate":
        return _validate(args)
    if args.command == "export":
        return _export(args)
    if args.command == "import":
        return _import(args)
    if args.command in ("baseline", "cr", "diff"):
        return changecontrol.run(args)
    parser.print_help()
    return 0
