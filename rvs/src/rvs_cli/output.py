"""Writing rendered output."""

import sys
from pathlib import Path

from rvs_core import atomicio


def emit(data: bytes, output: Path | None) -> None:
    """Write a rendered output to a file, or to standard output as UTF-8 whatever the console's own encoding is."""
    if output is not None:
        atomicio.write_bytes(output, data)  # a failed export leaves the previous file intact
    else:
        sys.stdout.flush()
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
