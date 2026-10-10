#!/bin/sh
# Write requirements-lock.txt: every runtime package including the transitive ones, pinned, with the hash of each
# distribution file, so that  pip install --require-hashes -r requirements-lock.txt  installs exactly what was reviewed.
# NEEDS NETWORK ACCESS to the package index (hashes are read from the index; they are never invented or typed in).
# Uses `uv` if it is installed, else pip-tools (`pip-compile`); with neither it prints what to install and stops.
# Review the result (git diff), commit it, and see docs/RELEASE.md ("Lock file") for how a release uses it.
set -eu
. "$(dirname "$0")/_common.sh"
rvs_enter_project
out=requirements-lock.txt
if command -v uv >/dev/null 2>&1; then
    # --universal: one file for Linux and Windows and every Python of requires-python
    uv pip compile pyproject.toml --universal --generate-hashes --no-header -o "$out"
elif command -v pip-compile >/dev/null 2>&1; then
    # pip-compile resolves for the Python that runs it; run this script once per supported Python if the files differ
    pip-compile --generate-hashes --strip-extras --resolver=backtracking -o "$out" pyproject.toml
else
    echo "make_lock: neither 'uv' nor 'pip-compile' is installed." >&2
    echo "  Install one of them (needs network):  pip install pip-tools     or     pip install uv" >&2
    echo "  Without them, by hand:  pip download --dest wheelhouse .   then record the hashes with  pip hash wheelhouse/*.whl" >&2
    echo "  and write them as --hash lines (sha256) yourself (do not copy hashes from anywhere you did not download from)." >&2
    exit 1
fi
echo "make_lock: wrote $out. Review it, commit it, and install releases with:"
echo "  pip install --require-hashes -r $out && pip install --no-deps ."
