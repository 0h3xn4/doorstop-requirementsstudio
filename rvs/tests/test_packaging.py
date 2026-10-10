"""Per-user install and uninstall scripts (Linux), manifest and optional signing hook of the release build."""

import os
import shutil
import stat
import subprocess
import sys
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


# packaging review ---------------------------------------------------------------------------------------------------------------------
def _run_env(
    script: Path, home: Path, extra: dict[str, str], *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": os.environ["PATH"], **extra}
    return subprocess.run(["sh", str(script), *args], env=env, cwd=cwd, capture_output=True, text=True, check=False)  # noqa: S603


def _siblings(prefix: Path) -> list[str]:
    return sorted(p.name for p in prefix.parent.iterdir() if p.name != prefix.name)


def test_install_never_touches_a_folder_that_has_the_old_staging_name(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "ho me"
    prefix = home / ".local" / "opt" / "rvs-studio"
    for leftover in (prefix.with_name("rvs-studio.new"), prefix.with_name("rvs-studio.old")):
        leftover.mkdir(parents=True)
        (leftover / "important.txt").write_text("not ours")
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0  # and over an existing installation
    for leftover in (prefix.with_name("rvs-studio.new"), prefix.with_name("rvs-studio.old")):
        assert (leftover / "important.txt").read_text() == "not ours"
    assert _siblings(prefix) == ["rvs-studio.new", "rvs-studio.old"]  # no temporary folder is left behind
    assert (prefix / "rvs").is_file() and (prefix / ".install-prefix").is_file()
    mode = prefix.stat().st_mode & 0o777
    umask = os.umask(0)
    os.umask(umask)
    assert mode == 0o777 & ~umask  # mktemp makes a private folder; the installed one follows the umask


def test_install_cut_short_in_the_swap_puts_the_previous_installation_back(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    prefix = home / ".local" / "opt" / "rvs-studio"
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    (prefix / "marker-of-the-old-installation").write_text("old")
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    fake = bin_dir / "mv"  # the move of the new files into place receives SIGTERM, as if the user pressed Ctrl+C
    fake.write_text(
        '#!/bin/sh\nfor last; do :; done\n[ "$last" = "$RVS_TEST_PREFIX" ] && [ ! -e "$RVS_TEST_FLAG" ] && { : > "$RVS_TEST_FLAG"; kill -TERM $PPID; exit 0; }\nexec "$RVS_TEST_MV" "$@"\n'
    )
    fake.chmod(0o755)
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "RVS_TEST_PREFIX": str(prefix),
        "RVS_TEST_FLAG": str(tmp_path / "signal-sent"),  # the signal is sent once, not again by the clean-up's own move
        "RVS_TEST_MV": shutil.which("mv") or "/bin/mv",
    }
    result = _run_env(release / "install.sh", home, env, "--no-selftest")
    assert result.returncode == 1
    assert (prefix / "marker-of-the-old-installation").read_text() == "old"
    assert _siblings(prefix) == []  # neither the staging folder nor the folder for the old installation is left


def test_install_cut_short_while_copying_leaves_nothing_behind(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    fake = bin_dir / "cp"
    fake.write_text("#!/bin/sh\nkill -INT $PPID\nsleep 1\nexit 0\n")
    fake.chmod(0o755)
    result = _run_env(
        release / "install.sh", home, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}, "--no-selftest"
    )
    assert result.returncode == 1
    opt = home / ".local" / "opt"
    assert not opt.exists() or list(opt.iterdir()) == []


def test_uninstall_twice_says_there_is_nothing_to_remove(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "ho me"
    home.mkdir()
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    first = _run(release / "uninstall.sh", home)
    assert first.returncode == 0 and "was removed" in first.stdout
    second = _run(release / "uninstall.sh", home)
    assert second.returncode == 0 and "Nothing to remove" in second.stdout
    assert str(home / ".local" / "opt" / "rvs-studio") in second.stdout and second.stderr == ""


def test_install_warns_about_missing_system_libraries_and_an_old_glibc_but_still_installs(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    app = release / "rvs-studio"
    plugin = app / "_internal" / "PySide6" / "Qt" / "plugins" / "platforms"
    plugin.mkdir(parents=True)
    (plugin / "libqxcb.so").write_bytes(b"\x7fELF")
    (app / "GLIBC-MIN").write_text("2.38\n")
    write_manifest(app)
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    (bin_dir / "ldd").write_text(
        "#!/bin/sh\nprintf '\\tlibc.so.6 => /lib/libc.so.6 (0x1)\\n\\tlibxcb-cursor.so.0 => not found\\n"
        "\\tlibxkbcommon-x11.so.0 => not found\\n'\n"
    )
    (bin_dir / "getconf").write_text("#!/bin/sh\necho 'glibc 2.31'\n")
    for tool in bin_dir.iterdir():
        tool.chmod(0o755)
    result = _run_env(
        release / "install.sh", home, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}, "--no-selftest"
    )
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr
    assert "libxcb-cursor0" in result.stderr and "libxkbcommon-x11-0" in result.stderr
    assert "glibc 2.31" in result.stderr and "2.38" in result.stderr
    assert (home / ".local" / "opt" / "rvs-studio" / "rvs").is_file()
    (bin_dir / "getconf").write_text("#!/bin/sh\necho 'glibc 2.39'\n")
    (bin_dir / "ldd").write_text("#!/bin/sh\nprintf '\\tlibc.so.6 => /lib/libc.so.6 (0x1)\\n'\n")
    quiet = _run_env(
        release / "install.sh", home, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}, "--no-selftest"
    )
    assert quiet.returncode == 0 and "WARNING" not in quiet.stderr


def test_menu_entry_has_an_icon_line_only_when_the_bundle_has_an_icon(tmp_path: Path):
    release, home = _release(tmp_path), tmp_path / "home"
    home.mkdir()
    desktop = home / ".local" / "share" / "applications" / "rvs-studio.desktop"
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    assert "Icon=" not in desktop.read_text()
    (release / "rvs-studio" / "rvs-studio.png").write_bytes(b"\x89PNG")
    write_manifest(release / "rvs-studio")
    assert _run(release / "install.sh", home, "--no-selftest").returncode == 0
    prefix = home / ".local" / "opt" / "rvs-studio"
    assert f"Icon={prefix}/rvs-studio.png" in desktop.read_text()


def test_windows_installer_uses_fresh_staging_folders_and_deletes_only_what_it_created():
    text = (ROOT / "packaging" / "install-windows.ps1").read_text()
    assert "NewGuid" in text and "-ErrorAction Stop" in text  # a fresh name, and creation fails if it exists
    assert 'Join-Path $parent "$leaf.$token.new"' in text
    assert "Remove-Item -LiteralPath $staging -Recurse -Force }\n" not in text.split("# 2.")[1].split("try {")[0]
    assert "$movedOld" in text  # the previous installation is put back when the swap fails


def test_release_script_is_deterministic_clean_and_refuses_to_run_elsewhere(tmp_path: Path):
    text = (ROOT / "scripts" / "build_release.sh").read_text()
    for needle in (
        "PYTHONHASHSEED=0", "SOURCE_DATE_EPOCH", "--sort=name", "--owner=0", "--group=0", "--numeric-owner",
        "gzip -n", "rm -rf build", "rvs_runtime_venv", "THIRD-PARTY-LICENSES.txt", "sbom.cdx.json", "GLIBC-MIN",
        "--output-reproducible", "selftest --manifest", "QT_QPA_PLATFORM=offscreen",
    ):  # fmt: skip
        assert needle in text, needle
    assert "$RVS_SIGN_CMD " not in text.replace('"$RVS_SIGN_CMD \\"', "")  # never expanded unquoted
    assert text.index("RVS_SIGN_CMD") < text.index("make_manifest.py")
    assert text.index('THIRD-PARTY-LICENSES.txt" "$out') < text.index(
        "make_manifest.py"
    )  # licences are in the manifest
    stray = tmp_path / "elsewhere" / "scripts"
    stray.mkdir(parents=True)
    for name in ("build_release.sh", "_common.sh"):
        shutil.copy(ROOT / "scripts" / name, stray / name)
    result = subprocess.run(
        ["sh", str(stray / "build_release.sh")], capture_output=True, text=True, check=False, cwd=tmp_path
    )  # noqa: S603, S607
    assert result.returncode == 1 and "belongs to the rvs project folder" in result.stderr
    assert not (tmp_path / "elsewhere" / "build").exists() and not (tmp_path / "elsewhere" / "dist").exists()


def test_spec_prunes_unused_qt_parts_and_unused_network_modules():
    spec = (ROOT / "packaging" / "rvs.spec").read_text()
    for needle in (
        "translations", "libqeglfs", "libqwayland", "libqvnc", "libQt6Pdf", "http.server", "socketserver", "xmlrpc",
        "libQt6Network",
    ):  # fmt: skip
        assert needle in spec, needle
    for keep in ("libqxcb", "libqoffscreen"):
        assert keep not in spec.split("_UNUSED_QT")[1].split("def _is_unused_qt")[0], keep  # the back ends in use stay


def test_licence_report_names_the_excluded_packages_and_the_relinking_rule(tmp_path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("make_licences", ROOT / "scripts" / "make_licences.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rvs_spec = (ROOT / "packaging" / "rvs.spec").read_text().replace("charset_normalizer", "charset-normalizer")
    for name in module.NETWORK_EXCLUDED:
        assert name.replace("-", "_") in rvs_spec.replace("-", "_"), (
            f"{name} is excluded in the report but not in rvs.spec"
        )
    out = tmp_path / "licences.txt"
    assert module.main([str(out), "--bundle", "--json", str(tmp_path / "licences.json")]) == 0
    text = out.read_text()
    assert "LGPL" in text and "Relinking" in text and "one-folder bundle" in text
    assert "Doorstop" in text or "doorstop" in text
    listed = {p["name"].lower() for p in __import__("json").loads((tmp_path / "licences.json").read_text())}
    assert not listed & {"requests", "urllib3", "bottle", "pip", "setuptools"}


def test_sdist_contains_what_is_needed_to_run_the_tests(tmp_path: Path):
    setuptools = pytest.importorskip("setuptools")
    if int(setuptools.__version__.split(".")[0]) < 77:
        pytest.skip("setuptools 77 or newer is needed for the licence expression")
    src = tmp_path / "src"
    shutil.copytree(
        ROOT, src,
        ignore=shutil.ignore_patterns(
            "build", "dist", "wheelhouse", ".git", ".venv*", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
            ".hypothesis", ".rvs-cache", "*.egg-info", ".coverage", "htmlcov",
        ),
    )  # fmt: skip
    out = tmp_path / "out"
    script = "import setuptools.build_meta as b, sys; print(b.build_sdist(sys.argv[1]))"
    done = subprocess.run(
        [sys.executable, "-c", script, str(out)], cwd=src, capture_output=True, text=True, check=False
    )  # noqa: S603
    assert done.returncode == 0, done.stderr[-2000:]
    import tarfile

    with tarfile.open(out / done.stdout.strip().splitlines()[-1]) as tar:
        names = {n.split("/", 1)[1] for n in tar.getnames() if "/" in n}
    for needed in (
        "LICENSE", "README.md", "MANIFEST.in", "pyproject.toml", "tests/conftest.py", "tests/golden_support.py",
        "tests/golden/minimal10/vcm.csv", "examples/minimal10/rvs-project.yaml", "scripts/build_release.sh",
        "scripts/_common.sh", "packaging/rvs.spec", "docs/RELEASE.md", "src/rvs_core/guide/guide.html",
    ):  # fmt: skip
        assert needed in names, needed
    assert not [n for n in names if ".rvs-cache" in n or "__pycache__" in n or ".hypothesis" in n]
    assert not (src / "build").exists()  # building the sdist left no build folder in the copy either
    assert not (ROOT / "build" / "lib").exists()


def test_project_metadata_is_a_proprietary_spdx_licence_with_a_licence_file():
    import tomllib

    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["license"] == "LicenseRef-Proprietary"
    assert data["project"]["license-files"] == ["LICENSE"]
    requires = data["build-system"]["requires"]
    assert any(
        r.replace(" ", "").startswith("setuptools>=") and int(r.split(">=")[1].split(".")[0]) >= 77 for r in requires
    )
    assert (ROOT / "LICENSE").is_file() and (ROOT / "README.md").is_file() and (ROOT / "MANIFEST.in").is_file()
    ignore = (ROOT / ".gitignore").read_text().split()
    for entry in (".venv/", "venv/", ".coverage", "htmlcov/", ".vscode/", ".idea/", "build/", "dist/"):
        assert entry in ignore, entry


def test_scripts_work_in_temporary_folders_and_the_lock_script_never_invents_hashes():
    for name in ("sbom.sh", "build_wheelhouse.sh", "build_release.sh"):
        text = (ROOT / "scripts" / name).read_text()
        assert "_common.sh" in text and "rvs_enter_project" in text, name
        assert subprocess.run(["sh", "-n", str(ROOT / "scripts" / name)], check=False).returncode == 0  # noqa: S603, S607
    lock = (ROOT / "scripts" / "make_lock.sh").read_text()
    assert "--generate-hashes" in lock and "network" in lock.lower() and "sha256:" not in lock
    assert subprocess.run(["sh", "-n", str(ROOT / "scripts" / "make_lock.sh")], check=False).returncode == 0  # noqa: S603, S607


def test_ci_workflow_runs_three_pythons_and_starts_the_gui_offscreen():
    import yaml

    workflow = yaml.safe_load((ROOT.parent / ".github" / "workflows" / "rvs-ci.yml").read_text())
    assert workflow["jobs"]["test"]["strategy"]["matrix"]["python"] == ["3.11", "3.12", "3.13"]
    steps = " ".join(str(s.get("run", "")) for s in workflow["jobs"]["test"]["steps"])
    assert "QT_QPA_PLATFORM" in str(workflow["jobs"]["test"]["env"]) and "rvs_gui" in steps
    assert "libxcb-cursor0" in steps


def test_wheelhouse_script_extracts_the_build_requirement_from_pyproject():
    script = (ROOT / "scripts" / "build_wheelhouse.sh").read_text()
    line = next(ln for ln in script.splitlines() if ln.startswith('pip download -d wheelhouse "$(sed'))
    expression = line.split("sed -n '", 1)[1].split("' pyproject.toml", 1)[0]
    done = subprocess.run(
        ["sed", "-n", expression, "pyproject.toml"], cwd=ROOT, capture_output=True, text=True, check=False
    )  # noqa: S603, S607
    assert done.stdout.strip().startswith("setuptools>=")
