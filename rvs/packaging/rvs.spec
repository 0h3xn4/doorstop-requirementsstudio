# PyInstaller spec: one-folder build (portable, no admin rights) with two programs: rvs-studio (GUI) and rvs (CLI).
# Run: pyinstaller packaging/rvs.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

root = Path(SPECPATH).parent  # noqa: F821
datas = [
    (str(root / "src" / "rvs_gui" / "assets"), "rvs_gui/assets"),
    *collect_data_files("rvs_core"),  # config defaults, JSON schemas, export fonts
    *copy_metadata("doorstop"),  # Doorstop reads its own version from package metadata
    *collect_data_files("docx"),  # python-docx default template
    # python-docx opens "docx/parts/../templates/...": the (otherwise empty) parts folder must exist on disk
    (str(root / "packaging" / "keep"), "docx/parts"),
]
# Never ship Doorstop's network server / Tk GUI, nor Qt network/web modules, nor the network libraries Doorstop
# depends on (RVS replaces them with inert placeholders, see rvs_core/adapter/_offline_guard.py).
excludes = ["tkinter", "doorstop.server", "doorstop.gui", "PySide6.QtNetwork",
            "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
            "PySide6.QtQuick", "PySide6.QtPdf", "PySide6.QtSvg",
            "requests", "urllib3", "bottle", "plantuml_markdown", "certifi", "idna", "charset_normalizer",
            "ssl", "_ssl",
            # standard-library network servers and clients nothing imports (the offline guard would refuse them anyway)
            "http.server", "socketserver", "xmlrpc", "xmlrpc.client", "xmlrpc.server"]  # fmt: skip

gui = Analysis([str(root / "packaging" / "launch.py")], pathex=[str(root / "src")], datas=datas, excludes=excludes)  # noqa: F821
cli = Analysis([str(root / "packaging" / "launch_cli.py")], pathex=[str(root / "src")], datas=datas, excludes=excludes)  # noqa: F821
# No network-capable library may ship, even unused: Qt's network module and OpenSSL's TLS library (libcrypto stays:
# hashlib needs it).
_NETWORK_LIBS = ("libQt6Network", "libssl", "_ssl.")
def _is_network(entry):  # entry = (destination, source, type); symbolic links to these libraries count too
    return any(Path(entry[0]).name.startswith(n) or n in Path(entry[0]).name or n in Path(str(entry[1])).name for n in _NETWORK_LIBS)


# Qt parts the application never loads (it is a QtWidgets program that runs on X11/xcb, or offscreen in tests and
# scripts): translations, the other platform back ends (EGLFS, LinuxFB, VNC, Wayland, minimal), PDF and SVG support.
# Matched against the path inside the bundle, with '/' separators. `rvs selftest --manifest` and an offscreen start
# of rvs-studio are part of scripts/build_release.sh, so a pruned file that was needed fails the release build.
_UNUSED_QT = (
    "PySide6/Qt/translations/",
    "PySide6/Qt/plugins/platforms/libqeglfs", "PySide6/Qt/plugins/platforms/libqlinuxfb",
    "PySide6/Qt/plugins/platforms/libqminimal", "PySide6/Qt/plugins/platforms/libqvnc",
    "PySide6/Qt/plugins/platforms/libqwayland", "PySide6/Qt/plugins/platforms/libqvkkhrdisplay",
    "PySide6/Qt/plugins/wayland-", "PySide6/Qt/plugins/egldeviceintegrations/",
    "PySide6/Qt/plugins/iconengines/", "PySide6/Qt/plugins/imageformats/libqsvg", "PySide6/Qt/plugins/imageformats/libqpdf",
    "libQt6EglFSDeviceIntegration", "libQt6EglFsKmsSupport", "libQt6WaylandClient", "libQt6WaylandEglClientHwIntegration",
    "libQt6WlShellIntegration", "libQt6Pdf", "libQt6Svg", "libwayland-",
)  # fmt: skip
def _is_unused_qt(entry):
    dest = entry[0].replace("\\", "/")
    return any(token in dest for token in _UNUSED_QT)


for analysis in (gui, cli):
    analysis.binaries = [b for b in analysis.binaries if not _is_network(b) and not _is_unused_qt(b)]
    analysis.datas = [d for d in analysis.datas if not _is_network(d) and not _is_unused_qt(d)]
gui_pyz, cli_pyz = PYZ(gui.pure), PYZ(cli.pure)  # noqa: F821
gui_exe = EXE(gui_pyz, gui.scripts, [], exclude_binaries=True, name="rvs-studio", console=False)  # noqa: F821
cli_exe = EXE(cli_pyz, cli.scripts, [], exclude_binaries=True, name="rvs", console=True)  # noqa: F821
coll = COLLECT(  # noqa: F821
    gui_exe, cli_exe,
    gui.binaries + cli.binaries, gui.datas + cli.datas,
    name="rvs-studio",
)  # fmt: skip
