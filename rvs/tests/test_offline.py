"""Run the app with all networking disabled (spec rule 3, DEVIATIONS V01)."""

import subprocess
import sys
import textwrap
from pathlib import Path

PROBE = textwrap.dedent(
    """
    import os, sys, socket
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    opened = []
    def deny(*a, **k):
        opened.append(a); raise OSError("network disabled by test")
    for name in ("connect", "connect_ex", "bind", "listen", "sendto"):
        setattr(socket.socket, name, deny)
    socket.create_connection = deny
    socket.getaddrinfo = deny
    import rvs_core, rvs_cli, rvs_gui
    from rvs_gui.app import create_app, create_main_window
    app = create_app([])
    win = create_main_window()
    win.show()
    app.processEvents()
    win.close()
    from rvs_core.validate import validate_project
    report = validate_project(__import__("pathlib").Path(sys.argv[1]))
    assert report.exit_code == 0, [f.format() for f in report.findings]
    import json
    banned = sorted(m for m in sys.modules if m.split(".")[0] in {
        "requests", "urllib3", "bottle", "plantuml_markdown", "ftplib", "smtplib", "xmlrpc", "socketserver",
        "ssl", "asyncio", "telnetlib", "imaplib", "poplib"}
        or m in {"http.client", "http.server", "urllib.request", "PySide6.QtNetwork"})
    # RVS registers inert placeholders for bottle/plantuml_markdown; only real (file-backed) modules count.
    banned = [m for m in banned if getattr(sys.modules[m], "__file__", None)]
    print(json.dumps({"opened": opened, "network_modules": banned,
                      "doorstop_loaded": "doorstop" in sys.modules}))
    """
)


def test_app_starts_with_networking_disabled():
    import json

    project = Path(__file__).resolve().parents[1] / "examples" / "minimal10"
    out = subprocess.run(
        [sys.executable, "-I", "-c", PROBE, str(project)],
        capture_output=True, text=True, cwd=Path(__file__).parent, timeout=120, check=False,
    )  # fmt: skip
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert data["opened"] == []
    assert data["doorstop_loaded"]
    # Strict (V01 resolved): no network-capable module is imported at all, Doorstop included.
    assert data["network_modules"] == []
