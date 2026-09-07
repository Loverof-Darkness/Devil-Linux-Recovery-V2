"""Safe interactive OS selection; never mutates storage."""
from __future__ import annotations

from devil.models.system import OperatingSystem


def selectable_linux(systems: tuple[OperatingSystem, ...]) -> list[OperatingSystem]:
    return [system for system in systems if system.is_linux()]


def selection_block_reason(system: OperatingSystem) -> str | None:
    missing = []
    if not system.root_device:
        missing.append("root device")
    if not system.root_filesystem:
        missing.append("root filesystem")
    if system.confidence < 0.80:
        return "identification confidence is too low"
    if missing:
        return "missing " + ", ".join(missing)
    return None


def render_systems(systems: tuple[OperatingSystem, ...]) -> str:
    lines = ["Detected Operating Systems", ""]
    for index, system in enumerate(systems, start=1):
        lines.append(f"[{index}] {system.name}")
        lines.append(f"    Family: {system.family}")
        if system.root_device:
            lines.append(f"    Root:   {system.root_device}")
        if system.root_filesystem:
            lines.append(f"    FS:     {system.root_filesystem}")
        if system.root_subvolume:
            lines.append(f"    Subvol: {system.root_subvolume}")
        if system.efi_device:
            lines.append(f"    EFI:    {system.efi_device}")
        lines.append(f"    Confidence: {system.confidence:.0%}")
        reason = selection_block_reason(system)
        if reason:
            lines.append(f"    Status: NOT SAFE TO SELECT ({reason})")
        lines.append("")
    return "\n".join(lines).rstrip()


def choose_linux(systems: tuple[OperatingSystem, ...], answer: str) -> OperatingSystem | None:
    linux = selectable_linux(systems)
    try:
        index = int(answer.strip()) - 1
    except ValueError:
        return None
    if index < 0 or index >= len(linux):
        return None
    candidate = linux[index]
    return candidate if selection_block_reason(candidate) is None else None
