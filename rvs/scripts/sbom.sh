#!/bin/sh
# Release-time only; needs the `dev` extra in the *current* environment.
# The SBOM/licence report describe the RUNTIME install only (fresh venv with `pip install .`).
set -eu
rm -rf .venv-sbom dist/rvs-sbom.cdx.json dist/rvs-licenses.*
python -m venv .venv-sbom
.venv-sbom/bin/pip install -q .
mkdir -p dist
python -m cyclonedx_py environment --of JSON -o dist/rvs-sbom.cdx.json .venv-sbom
pip-licenses --python .venv-sbom/bin/python --format=json --output-file dist/rvs-licenses.json
pip-licenses --python .venv-sbom/bin/python --format=plain-vertical --with-license-file --no-license-path \
  --output-file dist/rvs-licenses.txt
rm -rf .venv-sbom
