#!/bin/sh
# Build the release folder and archive (release machine only; needs the `dev` extra).
#   1. build the offline guide      2. PyInstaller one-folder build      3. optional code signing
#   4. MANIFEST.sha256 (written AFTER signing)      5. selftest of the built program      6. archive
# Code signing is optional: set RVS_SIGN_CMD to a command that signs the file passed as its last argument,
# e.g.  RVS_SIGN_CMD="signtool sign /fd SHA256 /a"   or   RVS_SIGN_CMD="gpg --detach-sign --armor".
set -eu
cd "$(dirname "$0")/.."
python scripts/build_guide.py
rm -rf build dist/rvs-studio
pyinstaller packaging/rvs.spec --noconfirm
out=dist/rvs-studio

if [ -n "${RVS_SIGN_CMD:-}" ]; then
    for exe in "$out/rvs-studio" "$out/rvs" "$out/rvs-studio.exe" "$out/rvs.exe"; do
        [ -f "$exe" ] && $RVS_SIGN_CMD "$exe"
    done
else
    echo "build_release: RVS_SIGN_CMD is not set; the program is not code-signed."
fi

version=$(python -c "import rvs_core; print(rvs_core.__version__)")
python scripts/make_manifest.py "$out"
"$out/rvs" selftest --manifest "$out"

stage="dist/rvs-studio-$version"
rm -rf "$stage" && mkdir -p "$stage"
cp -R "$out" "$stage/rvs-studio"
cp packaging/install-linux.sh "$stage/install.sh"
cp packaging/uninstall-linux.sh "$stage/uninstall.sh"
cp packaging/install-windows.ps1 "$stage/install.ps1"
cp packaging/uninstall-windows.ps1 "$stage/uninstall.ps1"
cp src/rvs_core/guide/guide.html "$stage/user-guide.html"
tar -C dist -czf "dist/rvs-studio-$version.tar.gz" "rvs-studio-$version"
(cd dist && sha256sum "rvs-studio-$version.tar.gz" > "rvs-studio-$version.tar.gz.sha256")
echo "built dist/rvs-studio-$version.tar.gz"
