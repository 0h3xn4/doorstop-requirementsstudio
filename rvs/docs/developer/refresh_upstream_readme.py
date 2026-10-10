"""Refresh the copy of the upstream Doorstop README that sits at the bottom of the repository's README.md.

The repository is a fork of doorstop-dev/doorstop. Its README.md has two parts: the RVS README on top and the original
Doorstop README below, between the markers ``<!-- BEGIN UPSTREAM README -->`` and ``<!-- END UPSTREAM README -->``.
The untouched upstream file is kept in ``docs/upstream/README.upstream.md``; this script copies it between the
markers, demoting every heading by one level so the table of contents stays clean. Nothing else is changed.

Usage (from the repository root):

    python rvs/docs/developer/refresh_upstream_readme.py            # rewrite README.md
    python rvs/docs/developer/refresh_upstream_readme.py --check    # exit 1 if README.md is out of date

See docs/developer/README.md ("Syncing with upstream") for the whole procedure.
"""

import argparse
import re
import sys
from pathlib import Path

BEGIN = "<!-- BEGIN UPSTREAM README -->"
END = "<!-- END UPSTREAM README -->"
ROOT = Path(__file__).resolve().parents[3]
UPSTREAM = ROOT / "docs" / "upstream" / "README.upstream.md"
README = ROOT / "README.md"


def demote(text: str) -> str:
    """Add one ``#`` to every Markdown heading outside fenced code blocks (six is the most Markdown allows)."""
    out: list[str] = []
    fence = ""
    for line in text.splitlines():
        marker = re.match(r"^(`{3,}|~{3,})", line)
        if marker:
            if not fence:
                fence = marker.group(1)[0] * 3
            elif line.startswith(fence):
                fence = ""
        elif not fence and re.match(r"^#{1,5} ", line):
            line = "#" + line
        out.append(line)
    return "\n".join(out) + "\n"


def render(readme: str, upstream: str) -> str:
    if BEGIN not in readme or END not in readme:
        raise SystemExit(f"README.md has no {BEGIN} / {END} markers")
    head, rest = readme.split(BEGIN, 1)
    tail = rest.split(END, 1)[1]
    return f"{head}{BEGIN}\n{demote(upstream)}{END}{tail}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="only report whether README.md is up to date")
    args = parser.parse_args()
    current = README.read_text(encoding="utf-8")
    wanted = render(current, UPSTREAM.read_text(encoding="utf-8"))
    if args.check:
        if current != wanted:
            print("README.md differs from docs/upstream/README.upstream.md: run this script without --check.")
            return 1
        print("README.md is up to date.")
        return 0
    README.write_text(wanted, encoding="utf-8", newline="\n")
    print("README.md refreshed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
