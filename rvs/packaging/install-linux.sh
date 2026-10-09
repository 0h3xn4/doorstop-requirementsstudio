#!/bin/sh
# Install Requirements & Verification Studio for the current user (no administrator rights, no network).
# Run from the unpacked release folder:   ./install.sh [--prefix DIR] [--no-selftest]
# Default prefix: ~/.local/opt/rvs-studio ; launchers in ~/.local/bin ; menu entry in ~/.local/share/applications.
set -eu

here=$(cd "$(dirname "$0")" && pwd)
prefix="$HOME/.local/opt/rvs-studio"
selftest=1
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) prefix="$2"; shift 2 ;;
        --no-selftest) selftest=0; shift ;;
        -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
        *) echo "install: unknown option $1" >&2; exit 2 ;;
    esac
done

app="$here/rvs-studio"
[ -d "$app" ] || app="$here"          # the script may sit inside the program folder itself
if [ ! -x "$app/rvs-studio" ] || [ ! -x "$app/rvs" ]; then
    echo "install: rvs-studio and rvs were not found next to this script. Run it from the unpacked release." >&2
    exit 1
fi

# 1. The files must be exactly what was released.
if [ -f "$app/MANIFEST.sha256" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$app" && sha256sum -c --quiet MANIFEST.sha256) || {
            echo "install: some files differ from MANIFEST.sha256; the download is damaged or was altered. Nothing was installed." >&2
            exit 1
        }
    else
        echo "install: sha256sum is not available; skipping the integrity check." >&2
    fi
else
    echo "install: no MANIFEST.sha256 found; skipping the integrity check." >&2
fi

# 2. Copy the program (an existing installation is replaced; projects and settings live elsewhere).
mkdir -p "$(dirname "$prefix")"
rm -rf "$prefix.new"
cp -R "$app" "$prefix.new"
rm -rf "$prefix"
mv "$prefix.new" "$prefix"

# 3. Launchers and menu entry.
bin="$HOME/.local/bin"
apps="$HOME/.local/share/applications"
mkdir -p "$bin" "$apps"
ln -sf "$prefix/rvs-studio" "$bin/rvs-studio"
ln -sf "$prefix/rvs" "$bin/rvs"
cat > "$apps/rvs-studio.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Requirements & Verification Studio
Comment=Offline requirements and verification management
Exec=$prefix/rvs-studio
Terminal=false
Categories=Development;Engineering;
DESKTOP
printf '%s\n' "$prefix" > "$prefix/.install-prefix"

echo "Installed to $prefix"
echo "Start it from the application menu or with: rvs-studio   (command line: rvs --help)"
case ":$PATH:" in *":$bin:"*) ;; *) echo "Note: add $bin to your PATH to use the 'rvs' command." ;; esac

if [ "$selftest" = 1 ]; then
    echo "Running the installation check ..."
    "$prefix/rvs" selftest || { echo "install: the installation check reported a problem (see above)." >&2; exit 1; }
fi
