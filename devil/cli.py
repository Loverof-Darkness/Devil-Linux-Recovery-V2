"""Command-line entry point for DEVIL V2 foundation."""

from __future__ import annotations

import argparse
import platform
import sys

from devil import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devil",
        description="DEVIL Linux Recovery V2 — discovery-first Linux boot recovery.",
    )
    parser.add_argument("--version", action="version", version=f"DEVIL V2 {__version__}")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="run read-only environment diagnostics",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show planned actions without making system changes",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    print(f"DEVIL Linux Recovery V2 {__version__}")
    print(f"Python: {platform.python_version()}")

    if args.diagnose:
        print("Read-only diagnostics engine: foundation stage")
        return 0

    if args.dry_run:
        print("Dry-run engine: foundation stage; no system changes made")
        return 0

    print("V2 foundation is installed. Recovery modules are being built in phases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
