#!/bin/sh
# Install Requirements & Verification Studio for the current user (no administrator rights, no network).
# Run from the unpacked release folder:   ./install.sh [--prefix DIR] [--no-selftest] [--skip-verify]
# Default prefix: ~/.local/opt/rvs-studio ; launchers in ~/.local/bin ; menu entry in ~/.local/share/applications.
# The prefix is only ever replaced if it is missing, empty, or was installed by this script (marker .install-prefix).
set -eu

here=$(cd "$(dirname "$0")" && pwd)
prefix="$HOME/.local/opt/rvs-studio"
selftest=1
verify=1
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) [ $# -ge 2 ] || { echo "install: --prefix needs a folder" >&2; exit 2; }; prefix="$2"; shift 2 ;;
        --no-selftest) selftest=0; shift ;;
        --skip-verify) verify=0; shift ;;
        -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
        *) echo "install: unknown option $1" >&2; exit 2 ;;
    esac
done

# --- the prefix: absolute, no trailing slash, never empty, '/' or the home folder itself ------------------------------
[ -n "$prefix" ] || { echo "install: the prefix is empty." >&2; exit 2; }
case "$prefix" in /*) ;; *) prefix="$PWD/$prefix" ;; esac
while [ "$prefix" != "/" ] && [ "${prefix%/}" != "$prefix" ]; do prefix="${prefix%/}"; done
if [ "$prefix" = "/" ] || [ "$prefix" = "$HOME" ] || [ "$prefix" = "${HOME%/}" ]; then
    echo "install: refusing to use $prefix as the installation folder." >&2
    exit 2
fi
if [ -e "$prefix" ] || [ -L "$prefix" ]; then
    if [ ! -d "$prefix" ] || [ -L "$prefix" ]; then
        echo "install: $prefix exists and is not a folder; nothing was changed." >&2
        exit 1
    fi
    if [ ! -f "$prefix/.install-prefix" ] && [ -n "$(ls -A "$prefix" 2>/dev/null)" ]; then
        echo "install: $prefix is not empty and was not installed by this script, so it is left alone. Choose another --prefix." >&2
        exit 1
    fi
fi

app="$here/rvs-studio"
[ -d "$app" ] || app="$here"          # the script may sit inside the program folder itself
if [ ! -x "$app/rvs-studio" ] || [ ! -x "$app/rvs" ]; then
    echo "install: rvs-studio and rvs were not found next to this script. Run it from the unpacked release." >&2
    exit 1
fi

# --- 1. the files must be exactly what was released --------------------------------------------------------------------
if [ "$verify" = 1 ]; then
    [ -f "$app/MANIFEST.sha256" ] || { echo "install: MANIFEST.sha256 is missing, so the files cannot be verified. Nothing was installed." >&2; exit 1; }
    command -v sha256sum >/dev/null 2>&1 || { echo "install: sha256sum is not available, so the files cannot be verified (use --skip-verify to install anyway)." >&2; exit 1; }
    (cd "$app" && sha256sum -c --quiet --strict MANIFEST.sha256) || {
        echo "install: some files differ from MANIFEST.sha256; the download is damaged or was altered. Nothing was installed." >&2
        exit 1
    }
    listed=$(cd "$app" && sed 's/^[0-9a-f]*  //' MANIFEST.sha256 | LC_ALL=C sort)
    present=$(cd "$app" && find . \( -type f -o -type l \) ! -name MANIFEST.sha256 ! -name .install-prefix | sed 's|^\./||' | LC_ALL=C sort)
    if [ "$listed" != "$present" ]; then
        echo "install: the folder holds files that are not in MANIFEST.sha256 (or lacks listed ones); nothing was installed." >&2
        exit 1
    fi
fi

# --- 2. copy next to the target, mark it as ours, then swap ----------------------------------------------------------------
staging="$prefix.new"
cleanup() { rm -rf "$staging"; }
trap cleanup EXIT INT TERM
mkdir -p "$(dirname "$prefix")"
rm -rf "$staging"
cp -R "$app" "$staging"
printf '%s\n' "$prefix" > "$staging/.install-prefix"
rm -rf "$prefix"
mv "$staging" "$prefix"
trap - EXIT INT TERM

# --- 3. launchers and menu entry ---------------------------------------------------------------------------------------------
bin="$HOME/.local/bin"
apps="$HOME/.local/share/applications"
mkdir -p "$bin" "$apps"
ln -sfn "$prefix/rvs-studio" "$bin/rvs-studio"
ln -sfn "$prefix/rvs" "$bin/rvs"
exec_path=$(printf '%s' "$prefix/rvs-studio" | sed 's/%/%%/g; s/\\/\\\\/g; s/"/\\"/g')
cat > "$apps/rvs-studio.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Requirements & Verification Studio
Comment=Offline requirements and verification management
Exec="$exec_path"
Terminal=false
Categories=Development;Engineering;
DESKTOP

echo "Installed to $prefix"
echo "Start it from the application menu or with: rvs-studio   (command line: rvs --help)"
case ":$PATH:" in *":$bin:"*) ;; *) echo "Note: add $bin to your PATH to use the 'rvs' command." ;; esac

if [ "$selftest" = 1 ]; then
    echo "Running the installation check ..."
    if [ "$verify" = 1 ]; then
        "$prefix/rvs" selftest --manifest "$prefix" || { echo "install: the installation check reported a problem (see above)." >&2; exit 1; }
    else
        "$prefix/rvs" selftest || { echo "install: the installation check reported a problem (see above)." >&2; exit 1; }
    fi
fi
