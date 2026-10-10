"""Crash reports without project content, a self-test of the installation, and file manifests for integrity checks."""

import hashlib
import os
import shutil
import sys
import tempfile
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import TracebackType

import rvs_core
from rvs_core import userconfig

MANIFEST = "MANIFEST.sha256"
INSTALL_MARKER = ".install-prefix"


# crash reports ################################################################################
def crash_report(exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> str:
    """Exception class and stack frames only. Messages, locals and source lines are left out on purpose: they may
    contain project content (spec rule 11)."""
    lines = [
        "RVS crash report",
        f"rvs {rvs_core.__version__}, python {sys.version.split()[0]}, platform {sys.platform}",
        f"time {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"exception {exc_type.__name__ if exc_type else 'unknown'}",
        "frames (most recent call last):",
    ]
    for frame in traceback.extract_tb(tb):
        name = frame.filename
        for marker in ("site-packages/", "src/", "_internal/"):
            if marker in name.replace("\\", "/"):
                name = name.replace("\\", "/").split(marker, 1)[1]
                break
        lines.append(f"  {name}:{frame.lineno} in {frame.name}")
    return "\n".join(lines) + "\n"


def save_crash_report(
    exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
) -> Path | None:
    try:
        folder = userconfig.config_dir() / "crash"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"crash-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.txt"
        path.write_text(crash_report(exc_type, exc, tb), encoding="utf-8", newline="\n")
        return path
    except OSError:
        return None


# self-test ###########################################################################################
@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


def _check(name: str, fn: Callable[[], str]) -> CheckResult:
    try:
        return CheckResult(name, True, fn())
    except Exception as exc:  # noqa: BLE001 - the self-test reports every failure plainly
        return CheckResult(name, False, f"{type(exc).__name__}: {exc}")


def selftest() -> list[CheckResult]:
    """Exercise every bundled component. Works in a scratch folder and removes it."""
    from datetime import datetime as dt

    from rvs_core.config import CONFIG_NAMES, load_project_config, packaged_default
    from rvs_core.config.schema import validate_against_schema

    scratch = Path(
        tempfile.mkdtemp(prefix="rvs-selftest-")
    )  # the system temp folder: the current folder may be read-only
    results: list[CheckResult] = []
    state: dict[str, object] = {}

    def defaults() -> str:
        for name in CONFIG_NAMES:
            validate_against_schema(name, packaged_default(name), source=name)
        return f"{len(CONFIG_NAMES)} files"

    def fonts() -> str:
        from importlib import resources

        names = ["IBMPlexSans-Regular", "IBMPlexSans-SemiBold", "IBMPlexSans-Italic", "IBMPlexMono-Regular"]
        base = resources.files("rvs_core.exporters")
        for n in names:
            for ext in ("ttf", "subset.woff"):
                if not base.joinpath(f"fonts/{n}.{ext}").read_bytes():
                    raise FileNotFoundError(f"{n}.{ext}")
        return f"{len(names) * 2} font files"

    def sample() -> str:
        from rvs_core.examples.minimal import build_minimal_project
        from rvs_core.validate import validate_project

        root = scratch / "p"
        build_minimal_project(root)
        report = validate_project(root, doorstop=False)
        if report.exit_code != 0:
            raise RuntimeError(f"validation exit code {report.exit_code}")
        state["root"], state["report"] = root, report
        return f"{len(report.items)} items validated"

    def render(fmt: str) -> Callable[[], str]:
        def run() -> str:
            from rvs_core.exporters.export_request import ExportRequest, build_output
            from rvs_core.matrices import Provenance

            report = state["report"]
            cfg, _ = load_project_config(state["root"])  # type: ignore[arg-type]
            prov = Provenance("selftest", "-", "selftest", "-", dt(2026, 1, 1), "selftest")
            data = build_output(ExportRequest("vcm", fmt), cfg, report.items, report.graph, prov)  # type: ignore[attr-defined]
            if len(data) < 200:
                raise RuntimeError("output is empty")
            return f"{len(data)} bytes"

        return run

    def reqif() -> str:
        from rvs_core.exporters.itemsio import plan_import
        from rvs_core.exporters.reqif import export_reqif, read_reqif
        from rvs_core.matrices import Provenance

        report = state["report"]
        cfg, _ = load_project_config(state["root"])  # type: ignore[arg-type]
        prov = Provenance("selftest", "-", "selftest", "-", dt(2026, 1, 1), "selftest")
        data = export_reqif(cfg, report.items, prov)  # type: ignore[attr-defined]
        rows = read_reqif(data, cfg, report.items).rows  # type: ignore[attr-defined]
        plan = plan_import(cfg, report.items, rows)  # type: ignore[attr-defined]
        if plan.errors or {r.action for r in plan.results} != {"unchanged"}:
            raise RuntimeError("an exported ReqIF file does not read back unchanged")
        return f"{len(data)} bytes, reads back unchanged"

    def yaml_parser() -> str:
        from rvs_core.adapter import yaml_parser_is_fast

        return "libyaml (fast)" if yaml_parser_is_fast() else "pure Python (slower on large projects)"

    def baseline() -> str:
        from rvs_core.changecontrol.baselines import create_baseline, verify_baseline

        root: Path = state["root"]  # type: ignore[assignment]
        from rvs_core.vcs.git import GitRepo

        GitRepo.init(root)  # its own repository, even when the scratch folder sits inside another one
        b = create_baseline(root, "SELFTEST", "installation check", user="selftest")
        if verify_baseline(root, "SELFTEST"):
            raise RuntimeError("verify failed")
        return f"tag {b.tag}"

    def guard() -> str:
        from rvs_core.adapter import doorstop_adapter  # noqa: F401  (imports Doorstop through the guard)

        loaded = [m for m in ("requests", "urllib3", "bottle") if getattr(sys.modules.get(m), "__file__", None)]
        if loaded:
            raise RuntimeError(f"network library loaded: {', '.join(loaded)}")
        return "no network library is loaded"

    try:
        results.append(_check("configuration defaults and schemas", defaults))
        results.append(_check("fonts", fonts))
        results.append(_check("sample project", sample))
        if "report" in state:
            results.append(_check("XLSX export", render("xlsx")))
            results.append(_check("DOCX export", render("docx")))
            results.append(_check("PDF export", render("pdf")))
            results.append(_check("HTML export", render("html")))
            results.append(_check("ReqIF export and import", reqif))
            results.append(_check("YAML parser", yaml_parser))
            results.append(_check("baseline (Git)", baseline))
        results.append(_check("offline guard", guard))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return results


# manifests #############################################################################################
def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(root: Path) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for f in sorted(filenames):
            rel = Path(dirpath, f).relative_to(root).as_posix()
            if rel not in (MANIFEST, INSTALL_MARKER):  # the marker is written by the installer, after the manifest
                out.append(rel)
    return out


def write_manifest(root: Path) -> None:
    lines = [f"{_digest(root / rel)}  {rel}" for rel in _files(root)]
    (root / MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def verify_manifest(root: Path) -> list[str]:
    """Problems found comparing the folder with its MANIFEST.sha256 (empty list: intact)."""
    path = root / MANIFEST
    if not path.is_file():
        return [f"{MANIFEST} is missing"]
    expected: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, _, rel = line.partition("  ")
        if rel:
            expected[rel] = digest
    problems = []
    for rel, digest in expected.items():
        file = root / rel
        if not file.is_file():
            problems.append(f"{rel} is missing")
        elif _digest(file) != digest:
            problems.append(f"{rel} has changed")
    for rel in _files(root):
        if rel not in expected:
            problems.append(f"{rel} is unexpected")
    return problems
