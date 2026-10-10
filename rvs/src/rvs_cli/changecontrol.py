"""``rvs baseline``, ``rvs cr`` and ``rvs diff``."""

import argparse
import json
import sys
from pathlib import Path

from rvs_cli.output import emit
from rvs_core.changecontrol.baselines import (
    BaselineError,
    OpenChangeRequestsError,
    create_baseline,
    list_baselines,
    verify_baseline,
)
from rvs_core.changecontrol.changes import ChangeRequestError, ChangeRequestStore
from rvs_core.changecontrol.diff import DiffResult, diff_doc, diff_snapshots, diff_table, load_snapshot
from rvs_core.config import ConfigError, ProjectConfig, load_project_config
from rvs_core.exporters import BINARY_FORMATS, render_doc
from rvs_core.matrices import Provenance
from rvs_core.matrices.render import to_csv
from rvs_core.schema.versioning import SchemaVersionError
from rvs_core.vcs.git import GitError


def add_parsers(sub: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    base = sub.add_parser("baseline", help="named, immutable snapshots of the project (Git tags)")
    bsub = base.add_subparsers(dest="baseline_command", required=True)
    create = bsub.add_parser("create", help="create a baseline (commits the project and tags it)")
    create.add_argument("project", type=Path)
    create.add_argument("name")
    create.add_argument("-m", "--message", required=True, help="why this baseline exists")
    create.add_argument("--defer", action="append", default=[], metavar="CR-ID=REASON",
                        help="defer an open change request so it does not block the baseline (repeatable)")  # fmt: skip
    create.add_argument(
        "--init-git", action="store_true", help="create a Git repository in the project folder if none exists"
    )
    create.add_argument("--user")
    lst = bsub.add_parser("list", help="list the baselines")
    lst.add_argument("project", type=Path)
    lst.add_argument("--format", choices=("text", "json"), default="text")
    ver = bsub.add_parser("verify", help="check that a baseline has not been tampered with")
    ver.add_argument("project", type=Path)
    ver.add_argument("name")

    cr = sub.add_parser("cr", help="change requests")
    csub = cr.add_subparsers(dest="cr_command", required=True)
    new = csub.add_parser("new", help="raise a change request")
    new.add_argument("project", type=Path)
    new.add_argument("title")
    new.add_argument("-d", "--description", default="")
    new.add_argument("--item", action="append", default=[], help="affected item (repeatable)")
    new.add_argument("--user")
    for name in ("list", "show", "status", "defer"):
        sp = csub.add_parser(name)
        sp.add_argument("project", type=Path)
        if name != "list":
            sp.add_argument("id")
        if name == "status":
            sp.add_argument("status")
            sp.add_argument("--note", default="")
        if name == "defer":
            sp.add_argument("--reason", required=True)
        if name in ("status", "defer"):
            sp.add_argument("--user")

    diff = sub.add_parser(
        "diff", help="differences between two baselines, or a baseline and the working copy ('working')"
    )
    diff.add_argument("project", type=Path)
    diff.add_argument("left")
    diff.add_argument("right")
    diff.add_argument("--document", help="only this document")
    diff.add_argument("--format", choices=("text", "json", "csv", "html", "docx", "pdf"), default="text")
    diff.add_argument("--output", "-o", type=Path)


def _store(root: Path) -> ChangeRequestStore:
    cfg, _ = load_project_config(root)
    return ChangeRequestStore(root, cfg)


def _fail(message: str, code: int = 2) -> int:
    print(f"rvs: {message}", file=sys.stderr)
    return code


def run(args: argparse.Namespace) -> int:
    try:
        if args.command == "baseline":
            return _baseline(args)
        if args.command == "cr":
            return _cr(args)
        return _diff(args)
    except (BaselineError, ChangeRequestError, GitError, ValueError) as exc:
        return _fail(str(exc))
    except (ConfigError, SchemaVersionError) as exc:
        return _fail(str(exc), 3)


def _baseline(args: argparse.Namespace) -> int:
    root: Path = args.project
    if args.baseline_command == "create":
        defer = {}
        for spec in args.defer:
            cr_id, _, reason = spec.partition("=")
            defer[cr_id.strip()] = reason
        try:
            b = create_baseline(root, args.name, args.message, user=args.user, defer=defer, init_git=args.init_git)
        except OpenChangeRequestsError as exc:
            print(f'{exc}\nExample: --defer {exc.open_requests[0].id}="after PDR"')
            return 1
        extra = f" Deferred change requests: {', '.join(b.deferred)}." if b.deferred else ""
        print(f"Baseline {b.name} created: {b.items} items, tag {b.tag}, commit {b.commit[:10]}.{extra}")
        return 0
    if args.baseline_command == "list":
        found = list_baselines(root)
        if args.format == "json":
            print(json.dumps([b.__dict__ | {"deferred": list(b.deferred)} for b in found], indent=2))
        else:
            for b in found:
                print(f"{b.name:<20} {b.created[:19]}  {b.created_by:<12} {b.items:>5} items  {b.description}")
            if not found:
                print("No baselines yet.")
        return 0
    findings = verify_baseline(root, args.name)
    for f in findings:
        print(f.format())
    if not findings:
        print(f"Baseline {args.name} is intact.")
    return 1 if findings else 0


def _cr(args: argparse.Namespace) -> int:
    store = _store(args.project)
    who = getattr(args, "user", None) or Provenance.now(load_project_config(args.project)[0]).user
    cmd = args.cr_command
    if cmd == "new":
        cr = store.create(args.title, args.description, who, args.item)
        print(f"{cr.id} created ({cr.status}).")
    elif cmd == "list":
        found = store.list()
        for c in found:
            print(f"{c.id}  {c.status:<12} {c.title}")
        if not found:
            print("No change requests.")
    elif cmd == "show":
        c = store.get(args.id)
        print(f"{c.id}  {c.status}\n{c.title}\nraised by {c.raised_by}\nitems: {', '.join(c.items) or '-'}")
        if c.description:
            print(f"\n{c.description}")
        edited = store.edited_items(c.id)
        if edited:
            print(f"edited under this change request: {', '.join(edited)}")
        for e in c.log:
            print(f"  {e.get('when', '')[:19]}  {e.get('who', '')}  {e.get('status', '')}  {e.get('note', '')}")
    elif cmd == "status":
        c = store.set_status(args.id, args.status, who, args.note)
        print(f"{c.id} is now {c.status}.")
    else:
        c = store.defer(args.id, args.reason, who)
        print(f"{c.id} deferred.")
    return 0


def _segments_text(segments: tuple[tuple[str, str], ...]) -> str:
    return "".join({"insert": f"{{+{t}+}}", "delete": f"[-{t}-]"}.get(op, t) for op, t in segments)


def _diff_text(diff: DiffResult) -> str:
    lines = [
        f"Changes: {diff.left} -> {diff.right}: {diff.added} added, {diff.removed} removed, {diff.changed} changed"
    ]
    for c in diff.changes:
        lines.append(f"{c.kind:<8} {c.uid:<10} {c.title}  {', '.join(f.name for f in c.fields)}".rstrip())
        for f in c.fields:
            lines.append(f"    {f.name}: {_segments_text(f.segments)}")
    return "\n".join(lines) + "\n"


def _diff(args: argparse.Namespace) -> int:
    root: Path = args.project
    refs = [None if r == "working" else r for r in (args.left, args.right)]
    snaps = [load_snapshot(root, r) for r in refs]
    diff = diff_snapshots(snaps[0], snaps[1])
    if args.document:
        diff = DiffResult(diff.left, diff.right, diff.for_document(args.document))
    cfg: ProjectConfig = snaps[1].cfg
    prov = Provenance.now(cfg, baseline=f"{diff.left} → {diff.right}")
    fmt = args.format
    if fmt == "text":
        out: bytes = _diff_text(diff).encode("utf-8")
    elif fmt == "json":
        payload = {
            "left": diff.left, "right": diff.right,
            "summary": {"added": diff.added, "removed": diff.removed, "changed": diff.changed},
            "changes": [
                {"uid": c.uid, "kind": c.kind, "document": c.document, "title": c.title,
                 "fields": [{"name": f.name, "before": f.before, "after": f.after} for f in c.fields]}
                for c in diff.changes
            ],
        }  # fmt: skip
        out = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    elif fmt == "csv":
        out = to_csv(diff_table(diff, prov)).encode("utf-8")
    else:
        out = render_doc(diff_doc(diff, prov), fmt)
    if not args.output and fmt in BINARY_FORMATS:
        return _fail(f"--format {fmt} writes a binary file; give --output FILE.")
    emit(out, args.output)
    return 0
