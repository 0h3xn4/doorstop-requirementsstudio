"""``rvs`` entry point. Subcommands (validate, export, ...) arrive in later milestones."""

import argparse
from collections.abc import Sequence

import rvs_core


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rvs", description="Requirements & Verification Studio")
    parser.add_argument("--version", action="store_true", help="print tool and framework versions")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(f"rvs {rvs_core.__version__} (doorstop {rvs_core.framework_version()})")
        return 0
    build_parser().print_help()
    return 0
