#!/bin/sh
# On a connected machine: vendor all runtime wheels for offline, reproducible installs.
set -eu
pip download -d wheelhouse .
# Offline install:  pip install --no-index --find-links wheelhouse rvs
