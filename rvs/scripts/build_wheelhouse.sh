#!/bin/sh
# On a connected machine: vendor all runtime wheels for offline, reproducible installs into wheelhouse/.
# Works in a temporary folder, so the working tree gets no build/ or *.egg-info.
#   Offline install:  pip install --no-index --find-links wheelhouse rvs
set -eu
. "$(dirname "$0")/_common.sh"
rvs_enter_project
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT INT TERM
rvs_copy_source "$work/src"
mkdir -p wheelhouse
pip download -d wheelhouse "$work/src"              # the runtime dependencies (pip download does not build the project itself)
pip wheel --no-deps -w wheelhouse "$work/src"       # the project itself
# Build requirements (setuptools) for an offline `pip install .` / `python -m build --no-isolation`:
pip download -d wheelhouse "$(sed -n 's/^requires = \["\([^"]*\)"\].*$/\1/p' pyproject.toml)"
