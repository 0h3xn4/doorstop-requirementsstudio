#!/bin/sh
# Remove the per-user installation made by install.sh. Projects and your settings (~/.config/rvs) are not touched;
# pass --purge-settings to remove the settings and crash reports as well.
set -eu
prefix="$HOME/.local/opt/rvs-studio"
purge=0
while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) prefix="$2"; shift 2 ;;
        --purge-settings) purge=1; shift ;;
        -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
        *) echo "uninstall: unknown option $1" >&2; exit 2 ;;
    esac
done
if [ -d "$prefix" ] && [ ! -f "$prefix/.install-prefix" ]; then
    echo "uninstall: $prefix was not installed by install.sh; refusing to delete it." >&2
    exit 1
fi
rm -rf "$prefix"
for link in "$HOME/.local/bin/rvs" "$HOME/.local/bin/rvs-studio"; do
    if [ -L "$link" ] && [ ! -e "$link" ]; then rm -f "$link"; fi
    case "$(readlink "$link" 2>/dev/null || true)" in "$prefix"/*) rm -f "$link" ;; esac
done
rm -f "$HOME/.local/share/applications/rvs-studio.desktop"
if [ "$purge" = 1 ]; then
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/rvs"
fi
echo "RVS was removed. Your projects were not touched."
