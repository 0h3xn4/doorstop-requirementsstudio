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
    assert f'Exec="{prefix}/rvs-studio"' in desktop
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


# review pass --------------------------------------------------------------------------------------------------------------------------
def test_install_never_replaces_a_folder_it_did_not_create(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    docs = home / "Documents"
    docs.mkdir(parents=True)
    (docs / "thesis.txt").write_text("years of work")
    result = _run(release / "install.sh", home, "--prefix", str(docs), "--no-selftest")
    assert result.returncode == 1 and (docs / "thesis.txt").read_text() == "years of work"
    afile = home / "afile"
    afile.write_text("x")
    assert (
        _run(release / "install.sh", home, "--prefix", str(afile), "--no-selftest").returncode == 1
        and afile.read_text() == "x"
    )
    for bad in ("", "/", str(home)):
        assert _run(release / "install.sh", home, "--prefix", bad, "--no-selftest").returncode == 2
    empty = home / "empty"
    empty.mkdir()
    assert (
        _run(release / "install.sh", home, "--prefix", str(empty), "--no-selftest").returncode == 0
    )  # an empty folder is fine


def test_install_over_an_existing_install_with_a_trailing_slash_or_a_relative_prefix(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "ho me"  # a space in the path as well
    home.mkdir()
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    prefix = home / ".local" / "opt" / "rvs-studio"
    assert _run(release / "install.sh", home, "--prefix", f"{prefix}/", "--no-selftest").returncode == 0
    assert (prefix / "rvs").is_file() and not (home / ".local" / "opt" / "rvs-studio.new").exists()
    env = {"HOME": str(home), "PATH": os.environ["PATH"]}
    rel = subprocess.run(
        ["sh", str(release / "install.sh"), "--prefix", "inst/rvs", "--no-selftest"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )  # noqa: S603, S607
    assert rel.returncode == 0 and (tmp_path / "inst" / "rvs" / "rvs").is_file()
    desktop = (home / ".local" / "share" / "applications" / "rvs-studio.desktop").read_text()
    assert 'Exec="' in desktop  # quoted, because the path has a space


def test_install_refuses_extra_files_and_unreadable_manifest_lines(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    (release / "rvs-studio" / "_internal" / "injected.so").write_bytes(b"evil")
    result = _run(release / "install.sh", home, "--no-selftest")
    assert result.returncode == 1 and "not in MANIFEST" in result.stderr and not (home / ".local" / "opt").exists()
    (release / "rvs-studio" / "_internal" / "injected.so").unlink()
    manifest = release / "rvs-studio" / "MANIFEST.sha256"
    manifest.write_text(manifest.read_text() + "this line is not a digest\n")
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 1


def test_install_without_a_manifest_needs_an_explicit_choice(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    (release / "rvs-studio" / "MANIFEST.sha256").unlink()
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 1
    assert _run(release / "install.sh", home, "--no-selftest", "--skip-verify").returncode == 0


def test_uninstall_only_removes_what_install_made(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    notes = home / "notes.txt"
    notes.write_text("keep")
    assert _run(release / "uninstall.sh", home, "--prefix", str(notes)).returncode == 1 and notes.exists()
    assert _run(release / "uninstall.sh", home, "--prefix", "").returncode == 2
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    other = home / ".local" / "bin"
    (other / "rvs").unlink()
    (other / "rvs").symlink_to(notes)  # a launcher that is not ours
    assert _run(release / "uninstall.sh", home).returncode == 0
    assert (other / "rvs").is_symlink() and notes.exists()  # left alone: it does not point into the prefix
    assert not (other / "rvs-studio").exists() and not (home / ".local" / "opt" / "rvs-studio").exists()


def test_manifest_handles_awkward_names_and_refuses_links_it_cannot_cover(tmp_path: Path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "plain.txt").write_text("a")
    (app / "odd name.txt").write_text("b")  # U+2028 is a line break to str.splitlines()
    write_manifest(app)
    assert verify_manifest(app) == []
    (app / "odd name.txt").write_text("changed")
    assert verify_manifest(app) == ["odd name.txt has changed"]
    (app / "odd name.txt").write_text("b")
    (app / "dir").mkdir()
    (app / "linkdir").symlink_to(app / "dir")
    with pytest.raises(ValueError, match="link to a folder"):
        write_manifest(app)
    (app / "linkdir").unlink()
    (app / "dangling").symlink_to(app / "nowhere")
    with pytest.raises(ValueError, match="broken link"):
        write_manifest(app)


def test_crash_reports_do_not_reveal_folder_names(tmp_path: Path):
    from rvs_core.diagnostics import crash_report

    script = tmp_path / "alice-private" / "thesis.py"
    script.parent.mkdir()
    script.write_text("def boom():\n    raise ValueError('secret text')\nboom()\n")
    try:
        exec(compile(script.read_text(), str(script), "exec"), {})  # noqa: S102
    except ValueError:
        import sys

        report = crash_report(*sys.exc_info())
    assert "alice-private" not in report and "secret" not in report and "thesis.py" in report


def test_projects_cannot_pull_in_local_files_with_include(minimal_project: Path):
    from rvs_core.adapter import DoorstopProject, ProjectError

    config = minimal_project / "SYS" / ".doorstop.yml"
    config.write_text(config.read_text().replace("sep: ''", "sep: !include /etc/hostname"))
    config.write_text(config.read_text() + "# x: !include /etc/hostname\n")
    with pytest.raises(ProjectError, match="!include"):
        DoorstopProject.open(minimal_project)
