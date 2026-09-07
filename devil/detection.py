"""Backward-compatible firmware probe.

The canonical firmware implementation lives in ``devil.discovery.firmware``.
This module preserves the original import path used by early V2 tests/tools.
"""

from __future__ import annotations

from pathlib import Path


def detect_firmware_mode(sys_root: str = "/sys") -> str:
    """Return UEFI or BIOS/UNKNOWN without modifying the system."""
    efi = Path(sys_root) / "firmware" / "efi"
    return "UEFI" if efi.is_dir() else "BIOS/UNKNOWN"
