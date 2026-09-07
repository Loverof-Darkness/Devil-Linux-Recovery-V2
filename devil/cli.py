"""Command-line entry point for DEVIL V2."""
from __future__ import annotations

import argparse
import json
import platform
import sys

from devil import __version__
from devil.discovery.commands import CommandRunner
from devil.discovery.scanner import scan
from devil.discovery.selector import choose_linux, render_systems


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devil",
        description="DEVIL Linux Recovery V2 — discovery-first Linux boot recovery.",
    )
    parser.add_argument("--version", action="version", version=f"DEVIL V2 {__version__}")
    parser.add_argument("--diagnose", action="store_true", help="run read-only system discovery")
    parser.add_argument("--json", action="store_true", help="emit discovery as JSON")
    parser.add_argument("--select", action="store_true", help="select a detected Linux installation for inspection")
    parser.add_argument("--dry-run", action="store_true", help="show discovery-only dry-run status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.dry_run and not (args.diagnose or args.json or args.select):
        print("DEVIL V2 dry-run: discovery only; no system changes are possible")
        return 0

    snapshot = scan(CommandRunner())

    if args.json:
        print(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True))
        return 0

    print(f"DEVIL Linux Recovery V2 {__version__}")
    print(f"Python: {platform.python_version()}")
    print(f"Firmware: {snapshot.firmware_mode.upper()}")
    print(f"Partitions discovered: {len(snapshot.partitions)}")
    print(f"EFI entries discovered: {len(snapshot.efi_entries)}")
    print()
    print(render_systems(snapshot.operating_systems) if snapshot.operating_systems else "No operating systems confidently identified from current mounts.")

    if snapshot.warnings:
        print("\nWarnings:")
        for warning in snapshot.warnings:
            print(f"  - {warning}")

    if args.select:
        linux = [item for item in snapshot.operating_systems if item.family.lower() == "linux"]
        if not linux:
            print("\nNo safe Linux recovery candidates are available.")
            return 2
        answer = input("\nSelect Linux installation [number]: ")
        selected = choose_linux(snapshot.operating_systems, answer)
        if selected is None:
            print("Selection rejected: invalid or unsafe candidate. No changes were made.")
            return 2
        print(f"\nSelected: {selected.name}")
        print(f"Root: {selected.root_device}")
        print(f"Mount: {selected.root_mountpoint}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
