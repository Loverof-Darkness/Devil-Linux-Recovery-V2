"""Resolve a selected Linux installation into a safe repair target.

This module is intentionally read-only. It does not mount, chroot, alter EFI
entries, or modify bootloader files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from devil.models.discovery import DiscoverySnapshot, OperatingSystem, Partition


@dataclass(frozen=True)
class TargetLayout:
    os_id: str
    os_name: str
    root_device: str | None
    root_filesystem: str | None
    root_mountpoint: str | None
    root_subvolume: str | None
    boot_device: str | None
    efi_device: str | None
    firmware_mode: str
    bootloader_candidates: tuple[str, ...] = ()
    safe: bool = False
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _linux_partitions(snapshot: DiscoverySnapshot) -> list[Partition]:
    return [
        part
        for part in snapshot.partitions
        if part.filesystem
        and part.filesystem.lower() in {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "bcachefs", "zfs"}
    ]


def _find_partition(snapshot: DiscoverySnapshot, device: str | None) -> Partition | None:
    if not device:
        return None
    return next((part for part in snapshot.partitions if part.device == device), None)


def _root_candidate(snapshot: DiscoverySnapshot, system: OperatingSystem) -> Partition | None:
    part = _find_partition(snapshot, system.root_device)
    if part is not None:
        return part
    mounted = [
        part for part in _linux_partitions(snapshot)
        if part.mountpoint and part.mountpoint == system.root_mountpoint
    ]
    return mounted[0] if len(mounted) == 1 else None


def resolve_target(snapshot: DiscoverySnapshot, os_id: str) -> TargetLayout:
    matches = [system for system in snapshot.operating_systems if system.os_id == os_id]
    if len(matches) != 1:
        return TargetLayout(
            os_id=os_id,
            os_name="Unknown",
            root_device=None,
            root_filesystem=None,
            root_mountpoint=None,
            root_subvolume=None,
            boot_device=None,
            efi_device=None,
            firmware_mode=snapshot.firmware_mode,
            reasons=("target operating system was not uniquely identified",),
        )

    system = matches[0]
    reasons: list[str] = []
    root = _root_candidate(snapshot, system)

    if system.family.lower() != "linux":
        reasons.append("selected target is not Linux")
    if root is None:
        reasons.append("Linux root partition could not be uniquely resolved")

    efi_parts = [part for part in snapshot.partitions if part.esp]
    efi_device = system.efi_device
    if efi_device:
        if _find_partition(snapshot, efi_device) is None:
            reasons.append("selected EFI device is not present in discovered partitions")
    elif snapshot.firmware_mode.lower() == "uefi":
        if len(efi_parts) == 1:
            efi_device = efi_parts[0].device
        elif not efi_parts:
            reasons.append("UEFI system has no discovered EFI System Partition")
        else:
            reasons.append("multiple EFI System Partitions are present; EFI target is ambiguous")

    boot_device = system.boot_device
    if boot_device and _find_partition(snapshot, boot_device) is None:
        reasons.append("selected /boot device is not present in discovered partitions")

    if snapshot.firmware_mode.lower() not in {"uefi", "bios"}:
        reasons.append("firmware mode is unknown")

    confidence = system.confidence.lower()
    if confidence not in {"medium", "high"}:
        reasons.append("operating-system identification confidence is insufficient")

    safe = not reasons
    return TargetLayout(
        os_id=system.os_id,
        os_name=system.name,
        root_device=root.device if root else system.root_device,
        root_filesystem=root.filesystem if root else None,
        root_mountpoint=root.mountpoint if root else system.root_mountpoint,
        root_subvolume=system.root_subvolume,
        boot_device=boot_device,
        efi_device=efi_device,
        firmware_mode=snapshot.firmware_mode,
        bootloader_candidates=system.bootloaders,
        safe=safe,
        reasons=tuple(reasons),
    )


def resolve_selected_linux(snapshot: DiscoverySnapshot, systems: Iterable[OperatingSystem], index: int) -> TargetLayout | None:
    candidates = [system for system in systems if system.family.lower() == "linux"]
    if index < 1 or index > len(candidates):
        return None
    return resolve_target(snapshot, candidates[index - 1].os_id)
