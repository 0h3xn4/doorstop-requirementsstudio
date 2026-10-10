"""``rvs`` entry point."""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import rvs_core
from rvs_cli import changecontrol
from rvs_cli.output import emit
from rvs_core.adapter import ProjectError
from rvs_core.authoring import ReasonRequiredError
from rvs_core.changecontrol.baselines import BaselineError
from rvs_core.exporters import BINARY_FORMATS, TABLE_FORMATS
from rvs_core.exporters.export_request import ExportRequest, build_output
from rvs_core.exporters.itemsio import (
    apply_import,
    plan_import,
    read_csv,
    read_xlsx,
)
from rvs_core.exporters.reqif import read_reqif
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

    exp = sub.add_parser("export", help="write a matrix or report (CSV, JSON, XLSX, HTML, DOCX or PDF)")
    exp.add_argument("project", type=Path)
    what = exp.add_mutually_exclusive_group(required=True)
    what.add_argument("--vcm", action="store_true", help="verification control matrix")
    what.add_argument("--trace", metavar="SRC:DST[:up|down]", help="traceability matrix between two documents")
    what.add_argument("--coverage", action="store_true", help="coverage per document")
    what.add_argument("--impact", metavar="UID", help="items affected by a change to UID")
    what.add_argument("--items", action="store_true", help="all items as a table (csv or xlsx; re-importable)")
    what.add_argument("--spec", action="store_true", help="specification document (html, docx or pdf); see --document")
    what.add_argument(
        "--reqif", action="store_true", help="ReqIF exchange file with items, hierarchy and links; see --document"
    )
    exp.add_argument("--format", choices=(*TABLE_FORMATS, "reqif"), default="csv")
    exp.add_argument("--output", "-o", type=Path, help="write to this file instead of standard output")
    exp.add_argument(
        "--document", action="append", default=[], help="VCM, --spec and --reqif: only this document (repeatable)"
    )
    exp.add_argument("--method", action="append", default=[], help="VCM: only this verification method (repeatable)")
    exp.add_argument("--level", action="append", default=[], help="VCM: only this verification level (repeatable)")
    exp.add_argument("--status", action="append", default=[], help="VCM: only this verification status (repeatable)")
    exp.add_argument("--baseline", help="export the project as it was at this baseline")
    exp.add_argument("--only-gaps", action="store_true", help="VCM: only requirements that nothing verifies")

    changecontrol.add_parsers(sub)

    init = sub.add_parser("init", help="create a new project from a template")
    init.add_argument("project", type=Path, nargs="?")
    init.add_argument("--name", help="project name")
    init.add_argument("--template", default="minimal")
    init.add_argument("--git", action="store_true", help="also create a Git repository in the folder")
    init.add_argument("--list-templates", action="store_true")

    selftest = sub.add_parser("selftest", help="check the installation: bundled files, exports, Git, offline guard")
    selftest.add_argument(
        "--manifest", type=Path, help="also verify the files of this folder against its MANIFEST.sha256"
    )

    guide = sub.add_parser("guide", help="write the offline user guide (HTML) or print where it is")
    guide.add_argument("--output", "-o", type=Path, help="copy the guide to this file")

    imp = sub.add_parser(
        "import",
        help="import items from a CSV or XLSX file written by 'export --items', or from a ReqIF file (exit 0 ok, 1 errors)",
    )
    imp.add_argument("project", type=Path)
    imp.add_argument("file", type=Path)
    imp.add_argument("--dry-run", action="store_true", help="show what would change; write nothing")
    imp.add_argument("--skip-errors", action="store_true", help="apply the valid rows even if some rows have errors")
    imp.add_argument("--reason", default="", help="why the items change (required for baselined items)")
    imp.add_argument("--cr", default=None, help="change request the imported edits belong to")
    imp.add_argument("--user", default=None, help="name recorded in the item history (default: login name)")
    imp.add_argument("--document", default=None, help="ReqIF: import every specification into this document")
    imp.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="NAME=COLUMN",
        help="ReqIF: import the attribute NAME into the item column COLUMN (repeatable)",
    )
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
    if args.reqif:
        kind = "reqif"
    elif args.items:
        kind = "items"
    elif args.spec:
        kind = "spec"
    elif args.vcm:
        kind = "vcm"
    elif args.trace is not None:
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
        kind, "reqif" if kind == "reqif" else args.format, tuple(args.document), tuple(args.method), tuple(args.level), tuple(args.status),
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
        unknown = [d for d in args.document if d not in {x.prefix for x in report.config.project.documents}]
        if unknown:
            raise ValueError(f"The document {unknown[0]} does not exist in this project.")
        data = build_output(
            _request(args), report.config, report.items, report.graph, Provenance.now(report.config, baseline=label)
        )
    except (ValueError, BaselineError, GitError) as exc:
        print(f"rvs export: {exc}", file=sys.stderr)
        return 2
    emit(data, args.output)
    return 0


def _import(args: argparse.Namespace) -> int:
    path: Path = args.file
    if not path.is_file():
        print(f"rvs import: the file {path} does not exist.", file=sys.stderr)
        return 2
    suffix = path.suffix.lower()
    if suffix not in (".csv", ".xlsx", ".reqif"):
        print("rvs import: the file must be .csv, .xlsx (written by 'rvs export --items') or .reqif.", file=sys.stderr)
        return 2
    report = validate_project(args.project, doorstop=False)
    if report.exit_code == 3 or report.config is None:
        for f in report.findings:
            print(f.format(), file=sys.stderr)
        return 3
    try:
        data = path.read_bytes()
        if suffix == ".reqif":
            bad = [m for m in args.map if "=" not in m]
            if bad:
                raise ValueError(f"--map needs NAME=COLUMN, not '{bad[0]}'")
            mapping = dict(m.split("=", 1) for m in args.map)
            read = read_reqif(data, report.config, report.items, document=args.document, mapping=mapping)
            rows = read.rows
            for note in read.notes:
                print(f"note: {note}")
            if read.unmapped:
                print(f"note: not imported (no matching column; use --map NAME=COLUMN): {', '.join(read.unmapped)}")
        else:
            rows = read_csv(data) if suffix == ".csv" else read_xlsx(data)
    except Exception as exc:  # noqa: BLE001 - corrupt or non-spreadsheet file: say so plainly
        print(f"rvs import: {path.name} could not be read ({exc}).", file=sys.stderr)
        return 2
    plan = plan_import(report.config, report.items, rows, why=args.reason, root=args.project)
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
    except (ValueError, ProjectError, ReasonRequiredError) as exc:
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


def _init(args: argparse.Namespace) -> int:
    from rvs_core.project_templates import TEMPLATES, create_from_template

    if args.list_templates:
        for t in TEMPLATES.values():
            print(f"{t.key:<10} {t.title}: {t.description}")
        return 0
    if args.project is None or not args.name:
        print('rvs init: give a folder and --name, for example: rvs init my-sat --name "My satellite"', file=sys.stderr)
        return 2
    parent_projects = [
        p for p in (args.project.resolve(), *args.project.resolve().parents) if (p / "rvs-project.yaml").is_file()
    ]
    if parent_projects:
        print(
            f"rvs init: {parent_projects[0]} is already an RVS project; a project cannot be created inside another.",
            file=sys.stderr,
        )
        return 2
    try:
        create_from_template(args.project, args.name, args.template, git=args.git)
    except (ValueError, OSError) as exc:
        print(f"rvs init: {exc}", file=sys.stderr)
        return 2
    print(f"Project '{args.name}' created in {args.project} from the {args.template} template.")
    return 0


def _selftest(args: argparse.Namespace) -> int:
    from rvs_core import diagnostics

    results = diagnostics.selftest()
    for r in results:
        print(f"{'ok  ' if r.ok else 'FAIL'} {r.name}" + (f"  ({r.detail})" if r.detail else ""))
    failed = [r for r in results if not r.ok]
    problems = diagnostics.verify_manifest(args.manifest) if args.manifest else []
    for p in problems:
        print(f"FAIL file integrity: {p}")
    if failed or problems:
        print(f"{len(failed) + len(problems)} problem(s) found.")
        return 1
    print("All checks passed.")
    return 0


def _guide(args: argparse.Namespace) -> int:
    from rvs_core.guide import guide_path

    path = guide_path()
    if path is None:
        print("rvs guide: the user guide is not part of this installation.", file=sys.stderr)
        return 2
    if args.output:
        args.output.write_bytes(path.read_bytes())
        print(f"Guide written to {args.output}.")
    else:
        print(path)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line. Expected failures are messages with exit code 2, never tracebacks."""
    for stream in (sys.stdout, sys.stderr):  # a Windows console or pipe may default to a legacy code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        return _main(argv)
    except BrokenPipeError:  # `rvs ... | head`
        sys.stdout = open(os.devnull, "w")  # noqa: SIM115, PTH123 - keeps interpreter shutdown from complaining
        return 0
    except OSError as exc:
        print(f"rvs: {exc.strerror or exc}{f' ({exc.filename})' if exc.filename else ''}", file=sys.stderr)
        return 2


def _main(argv: Sequence[str] | None = None) -> int:
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
    if args.command == "init":
        return _init(args)
    if args.command == "selftest":
        return _selftest(args)
    if args.command == "guide":
        return _guide(args)
    if args.command in ("baseline", "cr", "diff"):
        return changecontrol.run(args)
    parser.print_help()
    return 0
