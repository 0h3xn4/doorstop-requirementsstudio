#!/bin/sh
# Install Requirements & Verification Studio for the current user (no administrator rights, no network).
# Run from the unpacked release folder:   ./install.sh [--prefix DIR] [--no-selftest] [--skip-verify]
# Default prefix: ~/.local/opt/rvs-studio ; launchers in ~/.local/bin ; menu entry in ~/.local/share/applications.
# The prefix is only ever replaced if it is missing, empty, or was installed by this script (marker .install-prefix).
# Only folders this script created itself are ever deleted; a name that already exists is never reused for staging.
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
        -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
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
# staging = a fresh folder made by mktemp (so a folder that already has such a name is never touched);
# old     = a fresh folder that receives the previous installation during the swap.
# cleanup removes only those two, and puts the previous installation back if the swap was cut short.
staging=""
old=""
cleanup() {
    if [ -n "$old" ] && [ -d "$old/previous" ] && [ ! -e "$prefix" ]; then
        mv "$old/previous" "$prefix" 2>/dev/null || echo "install: the previous installation is in $old/previous" >&2
    fi
    if [ -n "$staging" ] && [ -d "$staging" ]; then rm -rf "$staging"; fi
    if [ -n "$old" ] && [ -d "$old" ] && [ ! -e "$old/previous" ]; then rm -rf "$old"; fi
    staging=""
    return 0
}
trap cleanup EXIT
trap 'cleanup; exit 1' INT TERM HUP
mkdir -p "$(dirname "$prefix")"
staging=$(mktemp -d "$prefix.XXXXXX")
mode=$(printf '%03o' $((0777 & ~$(umask))))
chmod "$mode" "$staging"                      # mktemp -d makes the folder private; installed files follow the umask
cp -R "$app/." "$staging/"
printf '%s\n' "$prefix" > "$staging/.install-prefix"
if [ -e "$prefix" ]; then
    old=$(mktemp -d "$prefix.XXXXXX")
    mv "$prefix" "$old/previous"
fi
if mv "$staging" "$prefix"; then
    staging=""
else
    echo "install: the new files could not be moved into place; the previous installation (if any) was restored." >&2
    exit 1
fi
if [ -n "$old" ]; then rm -rf "$old"; old=""; fi
trap - EXIT INT TERM HUP

# --- 3. launchers and menu entry ---------------------------------------------------------------------------------------------
bin="$HOME/.local/bin"
apps="$HOME/.local/share/applications"
mkdir -p "$bin" "$apps"
ln -sfn "$prefix/rvs-studio" "$bin/rvs-studio"
ln -sfn "$prefix/rvs" "$bin/rvs"
exec_path=$(printf '%s' "$prefix/rvs-studio" | sed 's/%/%%/g; s/\\/\\\\/g; s/"/\\"/g')
icon=""
for candidate in "$prefix/rvs-studio.png" "$prefix/rvs-studio.svg" "$prefix/_internal/rvs_gui/assets/rvs-studio.png" "$prefix/_internal/rvs_gui/assets/rvs-studio.svg"; do
    if [ -f "$candidate" ]; then icon="$candidate"; break; fi
done
{
    printf '[Desktop Entry]\nType=Application\nName=Requirements & Verification Studio\n'
    printf 'Comment=Offline requirements and verification management\n'
    printf 'Exec="%s"\n' "$exec_path"
    if [ -n "$icon" ]; then printf 'Icon=%s\n' "$icon"; fi
    printf 'Terminal=false\nCategories=Development;Engineering;\n'
} > "$apps/rvs-studio.desktop"

echo "Installed to $prefix"
echo "Start it from the application menu or with: rvs-studio   (command line: rvs --help)"
case ":$PATH:" in *":$bin:"*) ;; *) echo "Note: add $bin to your PATH to use the 'rvs' command." ;; esac

# --- 4. system libraries (a warning only: the program is installed either way) ---------------------------------------------
# The bundle needs the C library version it was built against and a few Qt platform libraries that no bundle can carry.
if [ -f "$prefix/GLIBC-MIN" ] && command -v getconf >/dev/null 2>&1; then
    need=$(sed -n '1p' "$prefix/GLIBC-MIN")
    have=$(getconf GNU_LIBC_VERSION 2>/dev/null | sed 's/^glibc //' || true)
    if [ -n "$need" ] && [ -n "$have" ]; then
        lowest=$(printf '%s\n%s\n' "$need" "$have" | sort -V 2>/dev/null | sed -n '1p' || true)
        if [ -n "$lowest" ] && [ "$lowest" != "$need" ]; then
            echo "WARNING: this system has glibc $have, but this build needs glibc $need or newer (it was built on Ubuntu 24.04)." >&2
            echo "         RVS will probably not start. On an older distribution install RVS from the wheelhouse with Python 3.11-3.13 instead (docs/RELEASE.md)." >&2
        fi
    fi
fi
xcb="$prefix/_internal/PySide6/Qt/plugins/platforms/libqxcb.so"
if [ -f "$xcb" ] && command -v ldd >/dev/null 2>&1; then
    missing=$(LD_LIBRARY_PATH="$prefix/_internal:$prefix/_internal/PySide6/Qt/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ldd "$xcb" 2>/dev/null | sed -n 's/^[[:space:]]*\([^ ]*\) => not found.*/\1/p' | LC_ALL=C sort -u || true)
    if [ -n "$missing" ]; then
        packages=""
        for lib in $missing; do
            case "$lib" in
                libEGL.so.1) pkg=libegl1 ;;
                libGL.so.1) pkg=libgl1 ;;
                libxkbcommon.so.0) pkg=libxkbcommon0 ;;
                libxkbcommon-x11.so.0) pkg=libxkbcommon-x11-0 ;;
                libfontconfig.so.1) pkg=libfontconfig1 ;;
                libdbus-1.so.3) pkg=libdbus-1-3 ;;
                libxcb-cursor.so.0) pkg=libxcb-cursor0 ;;
                libxcb-icccm.so.4) pkg=libxcb-icccm4 ;;
                libxcb-image.so.0) pkg=libxcb-image0 ;;
                libxcb-keysyms.so.1) pkg=libxcb-keysyms1 ;;
                libxcb-render-util.so.0) pkg=libxcb-render-util0 ;;
                libxcb-xkb.so.1) pkg=libxcb-xkb1 ;;
                libxcb-util.so.1) pkg=libxcb-util1 ;;
                *) pkg="" ;;
            esac
            packages="$packages ${pkg:-$lib}"
        done
        echo "WARNING: the graphical program will not start until these system libraries are installed:" >&2
        for lib in $missing; do echo "           $lib" >&2; done
        echo "         On Debian or Ubuntu:  sudo apt-get install$packages" >&2
        echo "         On other distributions install the packages that provide the files above. The 'rvs' command line does not need them." >&2
    fi
fi

if [ "$selftest" = 1 ]; then
    echo "Running the installation check ..."
    if [ "$verify" = 1 ]; then
        "$prefix/rvs" selftest --manifest "$prefix" || { echo "install: the installation check reported a problem (see above)." >&2; exit 1; }
    else
        "$prefix/rvs" selftest || { echo "install: the installation check reported a problem (see above)." >&2; exit 1; }
    fi
fi
