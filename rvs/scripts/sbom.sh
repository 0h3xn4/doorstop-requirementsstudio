#!/bin/sh
# Release-time only; needs the `dev` extra (cyclonedx-bom) in the *current* environment.
# The SBOM and the licence report describe the RUNTIME install only: a throwaway venv with `pip install .` from a clean
# copy of the project (nothing is left behind in the working tree). Needs the package index or RVS_PIP_ARGS pointing at
# a wheelhouse (RVS_PIP_ARGS="--no-index --find-links wheelhouse").
#   dist/rvs-sbom.cdx.json    CycloneDX 1.6, reproducible (no random serial number or clock time)
#   dist/rvs-licenses.txt     licence texts of every package;  dist/rvs-licenses.json  names, versions, licences
set -eu
. "$(dirname "$0")/_common.sh"
rvs_enter_project
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT INT TERM
rvs_runtime_venv "$work/venv" "$work"
mkdir -p dist
rm -f dist/rvs-sbom.cdx.json dist/rvs-licenses.json dist/rvs-licenses.txt
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-$(git log -1 --format=%ct 2>/dev/null || echo 0)} \
    python -m cyclonedx_py environment --output-reproducible --pyproject pyproject.toml --of JSON \
    -o dist/rvs-sbom.cdx.json "$work/venv/bin/python"
python scripts/sbom_post.py dist/rvs-sbom.cdx.json
"$work/venv/bin/python" scripts/make_licences.py dist/rvs-licenses.txt --json dist/rvs-licenses.json --bundle
