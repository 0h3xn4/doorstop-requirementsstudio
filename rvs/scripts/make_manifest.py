"""Write MANIFEST.sha256 for a built program folder:  python scripts/make_manifest.py dist/rvs-studio"""

import sys
from pathlib import Path

from rvs_core.diagnostics import write_manifest


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: make_manifest.py FOLDER", file=sys.stderr)
        return 2
    write_manifest(Path(argv[1]))
    print(f"wrote {argv[1]}/MANIFEST.sha256")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
