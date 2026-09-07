"""Human-readable rendering for the read-only target layout."""

from __future__ import annotations

from devil.planning.target import TargetLayout


def render_target(target: TargetLayout) -> str:
    lines = ["DEVIL Recovery Target", "", f"Target:       {target.os_name}", f"OS ID:        {target.os_id}"]
    lines.append(f"Root:         {target.root_device or 'UNRESOLVED'}")
    lines.append(f"Filesystem:   {target.root_filesystem or 'UNRESOLVED'}")
    if target.root_mountpoint:
        lines.append(f"Mount:        {target.root_mountpoint}")
    if target.root_subvolume:
        lines.append(f"Subvolume:     {target.root_subvolume}")
    lines.append(f"/boot device: {target.boot_device or 'not separately identified'}")
    lines.append(f"EFI:          {target.efi_device or 'UNRESOLVED'}")
    lines.append(f"Firmware:     {target.firmware_mode.upper()}")
    lines.append(
        f"Bootloader:   {', '.join(target.bootloader_candidates)}"
        if target.bootloader_candidates
        else "Bootloader:   not identified"
    )
    lines.append("")
    if target.safe:
        lines.append("Status: SAFE TARGET — planning may proceed; no changes have been made.")
    else:
        lines.append("Status: NOT SAFE — planning is blocked. No changes have been made.")
        lines.append("")
        lines.append("Reasons:")
        lines.extend(f"  - {reason}" for reason in target.reasons)
    return "\n".join(lines)
