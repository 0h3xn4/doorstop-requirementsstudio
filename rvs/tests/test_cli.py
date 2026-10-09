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
