"""Small, dependency-free read-only environment probes."""

from __future__ import annotations

from pathlib import Path


def detect_firmware_mode(sys_root: str = "/sys") -> str:
    """Return UEFI, BIOS, or UNKNOWN without modifying the system."""
    efi = Path(sys_root) / "firmware" / "efi"
    return "UEFI" if efi.exists() else "BIOS/UNKNOWN"
