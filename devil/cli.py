"""Command-line entry point for DEVIL V2."""

from __future__ import annotations

import argparse
import json
import platform
import sys

from devil import __version__
from devil.discovery.commands import CommandRunner
from devil.discovery.scanner import scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devil",
        description="DEVIL Linux Recovery V2 — read-only discovery-first recovery.",
    )
    parser.add_argument("--version", action="version", version=f"DEVIL V2 {__version__}")
    parser.add_argument("--diagnose", action="store_true", help="run read-only system discovery")
    parser.add_argument("--json", action="store_true", help="emit discovery as JSON")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show that no mutation-capable recovery action is available yet",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.dry_run and not args.diagnose:
        print("DEVIL V2 dry-run: discovery only; no system changes are possible in V2.1")
        return 0

    if args.diagnose or args.json:
        snapshot = scan(CommandRunner())
        if args.json:
            print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True))
            return 0

        print(f"DEVIL Linux Recovery V2 {__version__}")
        print(f"Python: {platform.python_version()}")
        print(f"Firmware: {snapshot.firmware_mode.upper()}")
        print(f"Partitions discovered: {len(snapshot.partitions)}")
        print(f"EFI entries discovered: {len(snapshot.efi_entries)}")
        print("\nOperating systems:")
        if not snapshot.operating_systems:
            print("  (none confidently identified from current mounts)")
        for index, os_info in enumerate(snapshot.operating_systems, 1):
            print(f"  [{index}] {os_info.name} ({os_info.family})")
            if os_info.root_device:
                print(f"      root: {os_info.root_device}")
            if os_info.root_mountpoint:
                print(f"      mount: {os_info.root_mountpoint}")
            if os_info.efi_device:
                print(f"      EFI: {os_info.efi_device}")
            print(f"      confidence: {os_info.confidence}")
        if snapshot.warnings:
            print("\nWarnings:")
            for warning in snapshot.warnings:
                print(f"  - {warning}")
        return 0

    print(f"DEVIL Linux Recovery V2 {__version__}")
    print("Run 'devil --diagnose' for read-only system discovery.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
