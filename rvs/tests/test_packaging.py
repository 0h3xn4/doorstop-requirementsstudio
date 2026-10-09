"""Per-user install and uninstall scripts (Linux), manifest and optional signing hook of the release build."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from rvs_core.diagnostics import verify_manifest, write_manifest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("sh") is None or os.name == "nt", reason="POSIX shell scripts")


def _release(tmp_path: Path) -> Path:
    release = tmp_path / "release"
    app = release / "rvs-studio"
    (app / "_internal").mkdir(parents=True)
    for name in ("rvs-studio", "rvs"):
        exe = app / name
        exe.write_text('#!/bin/sh\necho "$0 $*" >> "$HOME/calls.log"\n', encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    (app / "_internal" / "data.bin").write_bytes(b"\x00\x01")
    write_manifest(app)
    shutil.copy(ROOT / "packaging" / "install-linux.sh", release / "install.sh")
    shutil.copy(ROOT / "packaging" / "uninstall-linux.sh", release / "uninstall.sh")
    return release


def _run(script: Path, home: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    return subprocess.run(["sh", str(script), *args], env=env, capture_output=True, text=True, check=False)  # noqa: S603


def test_install_copies_links_and_checks_the_installation(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    result = _run(release / "install.sh", home)
    assert result.returncode == 0, result.stderr
    prefix = home / ".local" / "opt" / "rvs-studio"
    assert (prefix / "rvs").is_file() and (prefix / "_internal" / "data.bin").is_file()
    assert (home / ".local" / "bin" / "rvs").resolve() == (prefix / "rvs").resolve()
    desktop = (home / ".local" / "share" / "applications" / "rvs-studio.desktop").read_text()
    assert f"Exec={prefix}/rvs-studio" in desktop
    assert "selftest" in (home / "calls.log").read_text()  # the installation check ran
    assert verify_manifest(prefix) == []  # the install marker is not part of the manifest


def test_install_refuses_damaged_files_and_installs_nothing(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    (release / "rvs-studio" / "_internal" / "data.bin").write_bytes(b"tampered")
    result = _run(release / "install.sh", home)
    assert result.returncode == 1 and "MANIFEST" in result.stderr
    assert not (home / ".local" / "opt").exists()


def test_install_twice_replaces_and_uninstall_keeps_projects_and_settings(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    (home / ".config" / "rvs").mkdir(parents=True)
    (home / ".config" / "rvs" / "settings.json").write_text("{}")
    project = home / "my-project"
    project.mkdir()
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    assert _run(release / "uninstall.sh", home).returncode == 0
    assert not (home / ".local" / "opt" / "rvs-studio").exists()
    assert not (home / ".local" / "bin" / "rvs").exists() and not (home / ".local" / "bin" / "rvs-studio").exists()
    assert not (home / ".local" / "share" / "applications" / "rvs-studio.desktop").exists()
    assert (home / ".config" / "rvs" / "settings.json").exists() and project.exists()
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    assert _run(release / "uninstall.sh", home, "--purge-settings").returncode == 0
    assert not (home / ".config" / "rvs").exists()


def test_uninstall_refuses_a_folder_it_did_not_install(tmp_path: Path):
    home = tmp_path / "home"
    foreign = home / ".local" / "opt" / "rvs-studio"
    foreign.mkdir(parents=True)
    (foreign / "precious.txt").write_text("keep")
    result = _run(ROOT / "packaging" / "uninstall-linux.sh", home)
    assert result.returncode == 1 and (foreign / "precious.txt").exists()


def test_scripts_are_syntactically_valid_and_documented_in_the_release_script():
    for script in (
        "packaging/install-linux.sh", "packaging/uninstall-linux.sh", "scripts/build_release.sh", "scripts/build_wheelhouse.sh",
    ):  # fmt: skip
        assert subprocess.run(["sh", "-n", str(ROOT / script)], check=False).returncode == 0  # noqa: S603, S607
    release = (ROOT / "scripts" / "build_release.sh").read_text()
    assert "RVS_SIGN_CMD" in release and release.index("RVS_SIGN_CMD") < release.index("make_manifest.py")
    for file in ("install-windows.ps1", "uninstall-windows.ps1"):
        assert (ROOT / "packaging" / file).read_text().startswith("#")
