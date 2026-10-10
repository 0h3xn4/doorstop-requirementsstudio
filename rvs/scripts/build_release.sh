#!/bin/sh
# Build the release folder and archive (release machine only; needs the `dev` extra for cyclonedx-bom, and the package
# index or a wheelhouse for the clean build environment, see RVS_PIP_ARGS).
#   1. a throwaway clean venv with only the runtime dependencies (`pip install .` from a clean copy of the project)
#   2. licence report + SBOM of exactly that venv        3. check that the bundled offline guide is current
#   4. PyInstaller one-folder build with a pinned PyInstaller (installed into the venv after step 2)
#   5. optional code signing        6. MANIFEST.sha256 (written AFTER signing, covers licences and SBOM)
#   7. selftest and an offscreen start of the built program        8. deterministic archive + checksum
# Code signing is optional: set RVS_SIGN_CMD to a command that signs the file passed as its last argument,
# e.g.  RVS_SIGN_CMD="signtool sign /fd SHA256 /a"   or   RVS_SIGN_CMD="gpg --detach-sign --armor".
# Reproducibility: PYTHONHASHSEED=0 and SOURCE_DATE_EPOCH (default: the time of the last commit) are exported; the
# archive is sorted, owned by root and gzip'd without a name or timestamp. See docs/RELEASE.md for what is not pinned.
# Environment: RVS_PIP_ARGS (extra pip options, e.g. "--no-index --find-links wheelhouse"), RVS_PYINSTALLER (the pinned
# PyInstaller requirement), RVS_SIGN_CMD, SOURCE_DATE_EPOCH.
set -eu
. "$(dirname "$0")/_common.sh"
rvs_enter_project

PYINSTALLER=${RVS_PYINSTALLER:-pyinstaller==6.22.3}
if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
    SOURCE_DATE_EPOCH=$(git log -1 --format=%ct 2>/dev/null) || {
        echo "build_release: SOURCE_DATE_EPOCH is not set and the time of the last commit is not available (no Git history)." >&2
        exit 1
    }
fi
case $SOURCE_DATE_EPOCH in '' | *[!0-9]*) echo "build_release: SOURCE_DATE_EPOCH must be a number of seconds." >&2; exit 1 ;; esac
export SOURCE_DATE_EPOCH PYTHONHASHSEED=0
python -c "import cyclonedx_py" 2>/dev/null || { echo "build_release: cyclonedx-bom is missing; install the dev extra:  pip install -e '.[dev]'" >&2; exit 1; }

version=$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | sed -n '1p')
[ -n "$version" ] || { echo "build_release: cannot read the version from pyproject.toml." >&2; exit 1; }

rm -rf build "dist/rvs-studio" "dist/rvs-studio-$version" "dist/rvs-studio-$version.tar.gz" "dist/rvs-studio-$version.tar.gz.sha256"
mkdir -p build/release dist
work=$PWD/build/release
out=$work/dist/rvs-studio

echo "build_release: clean build environment ..."
rvs_runtime_venv "$work/venv" "$work"
venv=$work/venv/bin

echo "build_release: licence report and SBOM of the runtime environment ..."
"$venv/python" scripts/make_licences.py "$work/THIRD-PARTY-LICENSES.txt" --bundle
python -m cyclonedx_py environment --output-reproducible --pyproject pyproject.toml --of JSON \
    -o "$work/sbom.cdx.json" "$venv/python"
python scripts/sbom_post.py "$work/sbom.cdx.json"

echo "build_release: is the bundled guide current? ..."
"$venv/python" scripts/build_guide.py --check

echo "build_release: PyInstaller ($PYINSTALLER) ..."
# shellcheck disable=SC2086  # RVS_PIP_ARGS is a list of options
"$venv/python" -m pip install --quiet --disable-pip-version-check ${RVS_PIP_ARGS:-} "$PYINSTALLER"
"$venv/pyinstaller" "$work/src/packaging/rvs.spec" --noconfirm --distpath "$work/dist" --workpath "$work/pyi"

# What the bundle documents about itself: licences, SBOM, and the C library it was built against.
cp LICENSE "$out/LICENSE"
cp "$work/THIRD-PARTY-LICENSES.txt" "$out/THIRD-PARTY-LICENSES.txt"
cp "$work/sbom.cdx.json" "$out/sbom.cdx.json"
if command -v objdump >/dev/null 2>&1; then
    glibc_min=$(find "$out" -type f \( -name '*.so' -o -name '*.so.*' -o -perm -u+x \) -exec objdump -T {} + 2>/dev/null |
        grep -o 'GLIBC_[0-9][0-9.]*' | sed 's/^GLIBC_//' | LC_ALL=C sort -u -V | sed -n '$p')
    if [ -n "$glibc_min" ]; then
        printf '%s\n' "$glibc_min" > "$out/GLIBC-MIN"
        echo "build_release: the bundle needs glibc $glibc_min or newer"
    fi
else
    echo "build_release: objdump is not available; GLIBC-MIN is not written, so install.sh cannot check the C library." >&2
fi

if [ -n "${RVS_SIGN_CMD:-}" ]; then
    for name in rvs-studio rvs rvs-studio.exe rvs.exe; do
        if [ -f "$out/$name" ]; then
            sh -c "$RVS_SIGN_CMD \"\$1\"" sign "$out/$name"
        fi
    done
else
    echo "build_release: RVS_SIGN_CMD is not set; the program is not code-signed."
fi

"$venv/python" scripts/make_manifest.py "$out"
"$out/rvs" selftest --manifest "$out"

echo "build_release: starting the GUI offscreen ..."
mkdir -p "$work/home"
rc=0
HOME="$work/home" RVS_CONFIG_DIR="$work/home/rvs" QT_QPA_PLATFORM=offscreen timeout 10 "$out/rvs-studio" >/dev/null 2>"$work/gui.err" || rc=$?
if [ "$rc" != 124 ]; then   # 124: still running when the timeout ended, which is what a started window does
    echo "build_release: rvs-studio did not start offscreen (exit $rc):" >&2
    cat "$work/gui.err" >&2
    exit 1
fi

rm -rf dist/rvs-studio && cp -R "$out" dist/rvs-studio
stage="dist/rvs-studio-$version"
mkdir -p "$stage"
cp -R "$out" "$stage/rvs-studio"
cp packaging/install-linux.sh "$stage/install.sh"
cp packaging/uninstall-linux.sh "$stage/uninstall.sh"
cp packaging/install-windows.ps1 "$stage/install.ps1"
cp packaging/uninstall-windows.ps1 "$stage/uninstall.ps1"
cp src/rvs_core/guide/guide.html "$stage/user-guide.html"
cp LICENSE "$work/THIRD-PARTY-LICENSES.txt" "$stage/"
find "$stage" -type d -exec chmod 755 {} +
find "$stage" -type f -exec chmod go-w,go+r {} +
tar --sort=name --owner=0 --group=0 --numeric-owner --mtime="@$SOURCE_DATE_EPOCH" --format=gnu \
    -C dist -cf - "rvs-studio-$version" | gzip -n -9 > "dist/rvs-studio-$version.tar.gz"
(cd dist && sha256sum "rvs-studio-$version.tar.gz" > "rvs-studio-$version.tar.gz.sha256")
echo "built dist/rvs-studio-$version.tar.gz"
