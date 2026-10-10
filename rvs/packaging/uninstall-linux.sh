#!/bin/sh
# Remove the per-user installation made by install.sh. Projects and your settings (~/.config/rvs) are not touched;
# pass --purge-settings to remove the settings and crash reports as well.
# Only a folder that holds the marker .install-prefix is ever deleted, and launchers only if they point into it.
set -eu
prefix="$HOME/.local/opt/rvs-studio"
purge=0
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) [ $# -ge 2 ] || { echo "uninstall: --prefix needs a folder" >&2; exit 2; }; prefix="$2"; shift 2 ;;
        --purge-settings) purge=1; shift ;;
        -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
        *) echo "uninstall: unknown option $1" >&2; exit 2 ;;
    esac
done
[ -n "$prefix" ] || { echo "uninstall: the prefix is empty." >&2; exit 2; }
case "$prefix" in /*) ;; *) prefix="$PWD/$prefix" ;; esac
while [ "$prefix" != "/" ] && [ "${prefix%/}" != "$prefix" ]; do prefix="${prefix%/}"; done
if [ ! -d "$prefix" ] || [ -L "$prefix" ] || [ ! -f "$prefix/.install-prefix" ]; then
    echo "uninstall: $prefix is not an installation made by install.sh; nothing was removed." >&2
    exit 1
fi
rm -rf "$prefix"
for link in "$HOME/.local/bin/rvs" "$HOME/.local/bin/rvs-studio"; do
    if [ -L "$link" ]; then
        case "$(readlink "$link")" in "$prefix"/*) rm -f "$link" ;; esac
    fi
done
desktop="$HOME/.local/share/applications/rvs-studio.desktop"
if [ -f "$desktop" ] && grep -qF "$prefix/rvs-studio" "$desktop"; then
    rm -f "$desktop"
fi
if [ "$purge" = 1 ]; then
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/rvs"
fi
echo "RVS was removed. Your projects were not touched."
