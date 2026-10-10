# Shared helpers for the release scripts (sourced, POSIX sh). Not meant to be run on its own.
#
#   rvs_enter_project    cd to the rvs project folder (the parent of scripts/) or stop if this is not it
#   rvs_copy_source DIR  copy the project, without build output or caches, to DIR (so pip never writes build/ or
#                        *.egg-info into the working tree)
#   rvs_runtime_venv V W create the venv V and install the project from a clean copy placed in W/src (runtime
#                        dependencies only; RVS_PIP_ARGS adds pip options, for example --no-index --find-links wheelhouse)

rvs_enter_project() {
    cd "$(dirname "$0")/.." || exit 1
    if [ ! -f pyproject.toml ] || [ ! -f packaging/rvs.spec ] || ! grep -q '^name = "rvs"$' pyproject.toml; then
        echo "$0: this script belongs to the rvs project folder (the one with pyproject.toml and packaging/rvs.spec)." >&2
        exit 1
    fi
}

rvs_copy_source() {
    mkdir -p "$1"
    tar --exclude=./build --exclude=./dist --exclude=./wheelhouse --exclude=./.git --exclude='./.venv*' \
        --exclude=__pycache__ --exclude=.pytest_cache --exclude=.mypy_cache --exclude=.ruff_cache \
        --exclude=.hypothesis --exclude=.rvs-cache --exclude='*.egg-info' -cf - . | tar -xf - -C "$1"
}

rvs_runtime_venv() {
    venv=$1
    work=$2
    rvs_copy_source "$work/src"
    python -m venv "$venv"
    # shellcheck disable=SC2086  # RVS_PIP_ARGS is a list of options
    "$venv/bin/python" -m pip install --quiet --disable-pip-version-check ${RVS_PIP_ARGS:-} "$work/src"
}
