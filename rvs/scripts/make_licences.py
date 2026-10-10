"""Third-party licence report of the Python environment that runs this script (release time).

Run it with the interpreter of the *runtime* environment (a throwaway venv that holds only ``pip install .``), so the
report describes what the product really depends on:

    venv/bin/python scripts/make_licences.py OUT.txt [--json OUT.json]

Standard library only. The output is deterministic (sorted, no timestamps) and quotes every licence file that the
packages ship in their ``*.dist-info`` folder, verbatim.
"""

import argparse
import json
import re
import sys
from importlib import metadata
from pathlib import Path

#: Packages that pip installs as dependencies of Doorstop but that the release bundle does NOT contain
#: (packaging/rvs.spec excludes them; nothing in RVS imports them, see rvs_core/adapter/_offline_guard.py).
NETWORK_EXCLUDED = (
    "requests", "urllib3", "certifi", "idna", "charset-normalizer", "bottle", "plantuml-markdown",
)  # fmt: skip
#: Installer tooling that is part of every venv but never of the bundle.
TOOLING = ("pip", "setuptools", "wheel")
EXCLUDED_FROM_BUNDLE = (*NETWORK_EXCLUDED, *TOOLING)

_LICENCE_PREFIXES = ("license", "licence", "copying", "notice")

HEADER = """\
THIRD-PARTY LICENCES of Requirements & Verification Studio (RVS)

RVS itself is proprietary, internal software (see LICENSE). It is built on the open-source packages listed below.
Their licence texts follow, taken verbatim from each package's own distribution.

LGPL-3.0 components (PySide6 / Qt for Python, Shiboken6, Doorstop)
  PySide6-Essentials, shiboken6 and Doorstop are licensed under the GNU Lesser General Public Licence, version 3
  (LGPL-3.0-only; the Qt libraries are LGPL-3.0 or GPL, used under the LGPL). The licence text is quoted in the
  entries of those packages below.
  Relinking and replacement: the release is a one-folder bundle, so the Qt libraries (libQt6*.so* and the Qt plug-ins
  under _internal/PySide6/Qt) and the PySide6 / Shiboken6 modules are separate shared files, not linked into one
  executable. You can replace them with another build of the same version of the libraries; the installed files are
  listed in MANIFEST.sha256, so a replaced file is reported by `rvs selftest --manifest` (which is intended: it tells
  you the installation no longer matches the release). Source code of these libraries is available from
  https://www.qt.io/ and https://pypi.org/project/PySide6-Essentials/ and the Doorstop project (version 3.2).

Packages that pip installs with Doorstop but that are NOT part of this bundle (excluded; nothing imports them): {excluded}.
Installer tooling of the build environment ({tooling}) is not part of the bundle either.
"""


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _licence_of(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return str(expression)
    classifiers = [c.split("::")[-1].strip() for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")]
    declared = (meta.get("License") or "").strip()
    if declared and "\n" not in declared and len(declared) < 80:
        return declared
    return "; ".join(classifiers) or "(not stated in the package metadata)"


def _licence_files(dist: metadata.Distribution) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for f in sorted(dist.files or [], key=lambda p: p.as_posix()):
        parts = f.parts
        if not any(p.endswith(".dist-info") or p.endswith(".egg-info") for p in parts[:-1]):
            continue
        if not parts[-1].lower().startswith(_LICENCE_PREFIXES):
            continue
        try:
            text = Path(str(dist.locate_file(f))).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = text.replace("\r\n", "\n").strip("\n")
        if text and text not in seen:
            seen.add(text)
            out.append((f.as_posix(), text))
    return out


def collect() -> list[dict[str, object]]:
    seen: dict[str, dict[str, object]] = {}
    for dist in metadata.distributions():
        name = dist.metadata.get("Name")
        if not name:
            continue
        key = _normalise(name)
        seen[key] = {
            "name": name,
            "version": dist.version,
            "licence": _licence_of(dist),
            "url": dist.metadata.get("Home-page") or "",
            "files": _licence_files(dist),
        }
    return [seen[k] for k in sorted(seen)]


def render(packages: list[dict[str, object]]) -> str:
    chunks = [HEADER.format(excluded=", ".join(NETWORK_EXCLUDED), tooling=", ".join(TOOLING)), "PACKAGES\n"]
    for p in packages:
        chunks.append(f"  {p['name']} {p['version']}: {p['licence']}")
    chunks.append("")
    for p in packages:
        chunks.append("=" * 100)
        chunks.append(f"{p['name']} {p['version']}  -  {p['licence']}" + (f"  -  {p['url']}" if p["url"] else ""))
        chunks.append("=" * 100)
        files = p["files"]
        assert isinstance(files, list)
        if not files:
            chunks.append("(this package ships no licence file; the licence above is stated in its metadata)\n")
        for rel, text in files:
            chunks.append(f"--- {rel}\n{text}\n")
    return "\n".join(chunks) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("output", type=Path, help="text report to write")
    ap.add_argument("--json", type=Path, help="also write name/version/licence of every package as JSON")
    ap.add_argument(
        "--exclude", action="append", default=[], metavar="NAME", help="leave this package out (repeatable)"
    )
    ap.add_argument("--bundle", action="store_true", help="leave out what the release bundle does not contain")
    args = ap.parse_args(argv)
    skip = {_normalise(n) for n in [*args.exclude, *(EXCLUDED_FROM_BUNDLE if args.bundle else ())]}
    packages = [p for p in collect() if _normalise(str(p["name"])) not in skip]
    args.output.write_text(render(packages), encoding="utf-8", newline="\n")
    if args.json:
        listing = [{k: p[k] for k in ("name", "version", "licence", "url")} for p in packages]
        args.json.write_text(json.dumps(listing, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.output} ({len(packages)} packages)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
