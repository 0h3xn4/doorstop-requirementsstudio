"""``rvs`` entry point."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import rvs_core
from rvs_core.findings import Severity
from rvs_core.matrices import (
    MatrixTable,
    Provenance,
    VcmFilter,
    build_traceability,
    build_vcm,
    coverage_table,
    impact_table,
)
from rvs_core.matrices.render import render
from rvs_core.trace import coverage, impact
from rvs_core.validate import ValidationReport, validate_project


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
    exp.add_argument("--format", choices=("csv", "json"), default="csv")
    exp.add_argument("--output", "-o", type=Path, help="write to this file instead of standard output")
    exp.add_argument("--document", action="append", default=[], help="VCM: only this document (repeatable)")
    exp.add_argument("--method", action="append", default=[], help="VCM: only this verification method (repeatable)")
    exp.add_argument("--level", action="append", default=[], help="VCM: only this verification level (repeatable)")
    exp.add_argument("--status", action="append", default=[], help="VCM: only this verification status (repeatable)")
    exp.add_argument("--only-gaps", action="store_true", help="VCM: only requirements that nothing verifies")
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


def _build_table(args: argparse.Namespace, report: ValidationReport) -> MatrixTable:
    cfg, items, graph = report.config, report.items, report.graph
    assert cfg is not None and graph is not None
    prov = Provenance.now(cfg)
    if args.vcm:
        flt = VcmFilter(tuple(args.document), tuple(args.method), tuple(args.level), tuple(args.status), args.only_gaps)
        return build_vcm(cfg, items, graph, flt, provenance=prov)
    if args.trace:
        parts = args.trace.split(":")
        if len(parts) not in (2, 3):
            raise ValueError("--trace needs SRC:DST or SRC:DST:up|down, for example SYS:EPS")
        return build_traceability(
            cfg, items, graph, parts[0], parts[1], parts[2] if len(parts) == 3 else "down", provenance=prov
        )
    if args.coverage:
        return coverage_table(cfg, coverage(cfg, items, graph), prov)
    if args.impact not in graph.uids:
        raise ValueError(f"Item {args.impact} does not exist in this project.")
    return impact_table(items, impact(graph, args.impact), prov)


def _export(args: argparse.Namespace) -> int:
    report = validate_project(args.project, doorstop=False)
    if report.exit_code == 3 or report.config is None:
        for f in report.findings:
            print(f.format(), file=sys.stderr)
        return 3
    try:
        text = render(_build_table(args, report), args.format)
    except ValueError as exc:
        print(f"rvs export: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


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
    parser.print_help()
    return 0
