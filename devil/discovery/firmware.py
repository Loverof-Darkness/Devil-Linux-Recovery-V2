from __future__ import annotations

from pathlib import Path


def detect_firmware() -> str:
    return "uefi" if Path("/sys/firmware/efi").is_dir() else "bios"
