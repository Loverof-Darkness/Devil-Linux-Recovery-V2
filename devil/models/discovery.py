from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Partition:
    device: str
    parent_disk: str | None = None
    part_type: str | None = None
    filesystem: str | None = None
    label: str | None = None
    uuid: str | None = None
    size_bytes: int | None = None
    mountpoint: str | None = None
    partuuid: str | None = None
    boot: bool = False
    esp: bool = False


@dataclass(frozen=True)
class OperatingSystem:
    os_id: str
    name: str
    family: str
    root_device: str | None = None
    root_mountpoint: str | None = None
    root_subvolume: str | None = None
    boot_device: str | None = None
    efi_device: str | None = None
    firmware_mode: str | None = None
    bootloaders: tuple[str, ...] = ()
    confidence: str = "unknown"


@dataclass(frozen=True)
class EfiEntry:
    boot_number: str
    label: str
    path: str | None = None
    active: bool = False


@dataclass
class DiscoverySnapshot:
    firmware_mode: str = "unknown"
    disks: list[dict[str, Any]] = field(default_factory=list)
    partitions: list[Partition] = field(default_factory=list)
    operating_systems: list[OperatingSystem] = field(default_factory=list)
    efi_entries: list[EfiEntry] = field(default_factory=list)
    capabilities: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "firmware_mode": self.firmware_mode,
            "disks": self.disks,
            "partitions": [asdict(item) for item in self.partitions],
            "operating_systems": [asdict(item) for item in self.operating_systems],
            "efi_entries": [asdict(item) for item in self.efi_entries],
            "capabilities": self.capabilities,
            "warnings": self.warnings,
        }
