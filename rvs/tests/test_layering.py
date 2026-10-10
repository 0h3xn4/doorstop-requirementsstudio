"""Architecture rules: dependency direction, Doorstop confinement, no network imports in rvs_*."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
NETWORK_MODULES = {
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "ftplib", "smtplib",
    "socketserver", "xmlrpc", "telnetlib", "asyncio", "bottle", "PySide6.QtNetwork",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
}  # fmt: skip


def _imports(pkg: str) -> list[tuple[Path, str]]:
    found = []
    for path in (SRC / pkg).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found += [(path, a.name) for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.append((path, node.module))
    return found


def _top(name: str) -> str:
    return name.split(".")[0]


def test_core_has_no_gui_or_cli_imports():
    bad = [(p.name, m) for p, m in _imports("rvs_core") if _top(m) in {"PySide6", "rvs_gui", "rvs_cli"}]
    assert not bad, bad


def test_cli_does_not_import_gui():
    assert not [m for _, m in _imports("rvs_cli") if _top(m) in {"PySide6", "rvs_gui"}]


def test_nothing_depends_on_gui_except_gui():
    for pkg in ("rvs_core", "rvs_cli"):
        assert not [m for _, m in _imports(pkg) if _top(m) == "rvs_gui"]


def test_only_adapter_imports_doorstop():
    for pkg in ("rvs_core", "rvs_cli", "rvs_gui"):
        for path, mod in _imports(pkg):
            if _top(mod) == "doorstop":
                assert path.parts[-3:-1] == ("rvs_core", "adapter"), (path, mod)


def test_rvs_packages_import_no_network_modules():
    for pkg in ("rvs_core", "rvs_cli", "rvs_gui"):
        bad = [(p.name, m) for p, m in _imports(pkg) if m in NETWORK_MODULES or _top(m) in NETWORK_MODULES]
        assert not bad, bad


def test_only_the_vcs_package_imports_dulwich():
    for pkg in ("rvs_core", "rvs_cli", "rvs_gui"):
        for path, mod in _imports(pkg):
            if _top(mod) == "dulwich":
                assert path.parts[-3:-1] == ("rvs_core", "vcs"), (path, mod)
