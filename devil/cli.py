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
from devil.planning.repair import build_repair_plan, render_repair_plan
from devil.planning.render import render_target
from devil.planning.target import resolve_selected_linux
from devil.recovery.executor import RecoveryExecutor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devil",
        description="DEVIL Linux Recovery V2 — discovery-first Linux boot recovery.",
    )
    parser.add_argument("--version", action="version", version=f"DEVIL V2 {__version__}")
    parser.add_argument("--diagnose", action="store_true", help="run read-only system discovery")
    parser.add_argument("--json", action="store_true", help="emit discovery as JSON")
    parser.add_argument("--select", action="store_true", help="select a detected Linux installation for inspection")
    parser.add_argument("--plan", action="store_true", help="select a Linux installation and resolve its read-only target layout")
    parser.add_argument("--repair-plan", action="store_true", help="build an executable repair plan without changing the system")
    parser.add_argument("--repair", action="store_true", help="execute the supported repair plan after explicit confirmation")
    parser.add_argument("--yes", action="store_true", help="with --repair, accept the explicit REPAIR confirmation token non-interactively")
    parser.add_argument("--report", help="write a JSON repair report to this path")
    parser.add_argument("--dry-run", action="store_true", help="show discovery-only dry-run status")
    return parser


def _safe_int(value: str) -> int:
    try:
        return int(value.strip())
    except ValueError:
        return -1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.dry_run and not (args.diagnose or args.json or args.select or args.plan or args.repair_plan or args.repair):
        print("DEVIL V2 dry-run: discovery only; no system changes are possible")
        return 0

    if args.repair and not args.yes and not sys.stdin.isatty():
        print("Repair requires an interactive confirmation or --yes.", file=sys.stderr)
        return 2

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
    print(
        render_systems(snapshot.operating_systems)
        if snapshot.operating_systems
        else "No operating systems confidently identified from current mounts."
    )

    if snapshot.warnings:
        print("\nWarnings:")
        for warning in snapshot.warnings:
            print(f"  - {warning}")

    if not (args.select or args.plan or args.repair_plan or args.repair):
        return 0

    linux = [item for item in snapshot.operating_systems if item.family.lower() == "linux"]
    if not linux:
        print("\nNo Linux recovery candidates are available.")
        return 2

    answer = input("\nSelect Linux installation [number]: ")
    index = _safe_int(answer)
    target = resolve_selected_linux(snapshot, snapshot.operating_systems, index)
    if target is None:
        print("Selection rejected: invalid Linux candidate. No changes were made.")
        return 2

    if args.select:
        selected = choose_linux(snapshot.operating_systems, answer)
        if selected is None:
            print("Selection rejected: invalid or unsafe candidate. No changes were made.")
            return 2
        print(f"\nSelected: {selected.name}")
        print(f"Root: {selected.root_device}")
        print(f"Mount: {selected.root_mountpoint}")
        return 0

    print()
    print(render_target(target))
    if args.plan and not (args.repair_plan or args.repair):
        return 0 if target.safe else 2

    plan = build_repair_plan(target)
    print("\n" + render_repair_plan(plan))
    if args.repair_plan and not args.repair:
        return 0 if plan.safe_to_execute else 2

    if not plan.safe_to_execute:
        print("\nRepair blocked. No changes were made.", file=sys.stderr)
        return 2

    confirmation = "REPAIR" if args.yes else input("\nType REPAIR to continue: ")
    if confirmation.strip() != "REPAIR":
        print("Confirmation rejected. No changes were made.")
        return 2

    report = RecoveryExecutor().execute(plan, confirmation=confirmation, report_path=args.report)
    print("\nRepair result: " + ("SUCCESS" if report.success else "FAILED"))
    for step in report.steps:
        print(f"  [{step['status']}] {step['step']}: {step['detail']}")
    for warning in report.warnings:
        print(f"  WARNING: {warning}")
    if args.report:
        print(f"Report: {args.report}")
    return 0 if report.success else 2


if __name__ == "__main__":
    sys.exit(main())
