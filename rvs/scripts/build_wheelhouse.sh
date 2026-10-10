#!/bin/sh
# On a connected machine: vendor all runtime wheels for offline, reproducible installs.
set -eu
pip download -d wheelhouse .
pip wheel --no-deps -w wheelhouse .   # the project itself (pip download only fetches its dependencies)
# Offline install:  pip install --no-index --find-links wheelhouse rvs
