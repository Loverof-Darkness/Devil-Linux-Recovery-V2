"""Data structures for discovered storage and operating-system candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Partition:
    device: str
    filesystem: Optional[str] = None
    label: Optional[str] = None
    uuid: Optional[str] = None
    mountpoint: Optional[str] = None
    size_bytes: Optional[int] = None


@dataclass(frozen=True)
class OperatingSystem:
    name: str
    family: str
    root_device: Optional[str] = None
    root_filesystem: Optional[str] = None
    root_subvolume: Optional[str] = None
    boot_device: Optional[str] = None
    efi_device: Optional[str] = None
    efi_loader: Optional[str] = None
    confidence: float = 0.0
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def is_linux(self) -> bool:
        return self.family.lower() == "linux"


@dataclass(frozen=True)
class BootEntry:
    identifier: str
    label: str
    loader_path: Optional[str] = None
    active: bool = False


@dataclass(frozen=True)
class DiscoverySnapshot:
    firmware_mode: str
    partitions: tuple[Partition, ...] = field(default_factory=tuple)
    operating_systems: tuple[OperatingSystem, ...] = field(default_factory=tuple)
    boot_entries: tuple[BootEntry, ...] = field(default_factory=tuple)
