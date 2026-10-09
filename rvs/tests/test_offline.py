"""Run the app with all networking disabled (spec rule 3, DEVIATIONS V01)."""

import subprocess
import sys
import textwrap
from pathlib import Path

# Doorstop 3.2's own transitive imports (reviewed, see docs/DEVIATIONS.md V01).
ALLOWED_TRANSITIVE = {"requests", "urllib3", "bottle", "http", "http.client", "http.server",
                      "http.cookiejar", "http.cookies", "urllib", "urllib.request",
                      "urllib.error", "urllib.response", "urllib.parse", "ssl",
                      "socket", "socketserver", "asyncio"}  # fmt: skip

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
        "requests", "urllib3", "bottle", "ftplib", "smtplib", "xmlrpc"}
        or m in {"http.client", "http.server", "ssl", "PySide6.QtNetwork"})
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
    allowed = ALLOWED_TRANSITIVE if data["doorstop_loaded"] else set()
    unexpected = [m for m in data["network_modules"] if m not in allowed
                  and m.split(".")[0] not in allowed]  # fmt: skip
    assert not unexpected, unexpected
    assert "PySide6.QtNetwork" not in data["network_modules"]
