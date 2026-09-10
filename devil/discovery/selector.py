"""Safe interactive OS selection; never mutates storage."""
from __future__ import annotations

from devil.models.discovery import OperatingSystem


_CONFIDENCE_RANK = {"unknown": 0, "low": 1, "medium": 2, "high": 3}


def selectable_linux(systems: list[OperatingSystem]) -> list[OperatingSystem]:
    return [system for system in systems if system.family.lower() == "linux"]


def selection_block_reason(system: OperatingSystem) -> str | None:
    if not system.root_device:
        return "missing root device"
    if _CONFIDENCE_RANK.get(system.confidence.lower(), 0) < _CONFIDENCE_RANK["medium"]:
        return "identification confidence is too low"
    return None


def render_systems(systems: list[OperatingSystem]) -> str:
    lines = ["Detected Operating Systems", ""]
    for index, system in enumerate(systems, start=1):
        lines.append(f"[{index}] {system.name}")
        lines.append(f"    Family: {system.family}")
        if system.root_device:
            lines.append(f"    Root:   {system.root_device}")
        if system.root_mountpoint:
            lines.append(f"    Mount:  {system.root_mountpoint}")
        else:
            lines.append("    Mount:  not currently mounted")
        if system.root_subvolume:
            lines.append(f"    Subvol: {system.root_subvolume}")
        if system.efi_device:
            lines.append(f"    EFI:    {system.efi_device}")
        if system.bootloaders:
            lines.append(f"    Boot:   {', '.join(system.bootloaders)}")
        lines.append(f"    Confidence: {system.confidence}")
        reason = selection_block_reason(system)
        lines.append("    Status: SAFE CANDIDATE" if reason is None else f"    Status: NOT SAFE TO SELECT ({reason})")
        lines.append("")
    return "\n".join(lines).rstrip()


def choose_linux(systems: list[OperatingSystem], answer: str) -> OperatingSystem | None:
    linux = selectable_linux(systems)
    try:
        index = int(answer.strip()) - 1
    except ValueError:
        return None
    if index < 0 or index >= len(linux):
        return None
    candidate = linux[index]
    return candidate if selection_block_reason(candidate) is None else None
