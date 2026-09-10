from __future__ import annotations

from typing import Any

from devil.discovery import blkid, efi, firmware, lsblk
from devil.discovery.commands import CommandRunner
from devil.discovery.probe import ReadOnlyFilesystemProbe
from devil.models.discovery import DiscoverySnapshot, OperatingSystem, Partition


_LINUX_FS = {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "bcachefs", "zfs"}
_EFI_FS = {"vfat", "fat16", "fat32"}


def _flatten(nodes: list[dict[str, Any]], parent_disk: str | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for node in nodes:
        node_parent = node.get("pkname") or parent_disk
        result.append({**node, "_parent_disk": parent_disk or (node_parent if node.get("type") == "disk" else None)})
        children = node.get("children") or []
        if node.get("type") == "disk":
            for child in children:
                result.extend(_flatten([child], node.get("path") or node.get("name")))
        else:
            result.extend(_flatten(children, parent_disk))
    return result


def _mountpoint(raw: Any) -> str | None:
    if isinstance(raw, list):
        values = [item for item in raw if item]
        return values[0] if values else None
    return raw or None


def scan(runner: CommandRunner | None = None, probe: ReadOnlyFilesystemProbe | None = None) -> DiscoverySnapshot:
    runner = runner or CommandRunner()
    probe = probe or ReadOnlyFilesystemProbe()
    snapshot = DiscoverySnapshot(firmware_mode=firmware.detect_firmware())

    nodes = lsblk.collect(runner)
    blkid_map = blkid.collect(runner)
    flat = _flatten(nodes)

    for node in flat:
        device = node.get("path") or node.get("name")
        if not device:
            continue
        fstype = node.get("fstype") or blkid_map.get(device, {}).get("TYPE")
        parttype = node.get("parttype")
        flags = str(node.get("partflags") or "").lower()
        esp = bool(
            fstype in _EFI_FS
            and (parttype or "").lower() in {"c12a7328-f81f-11d2-ba4b-00a0c93ec93b", "ef00"}
        ) or "esp" in flags
        partition = Partition(
            device=device,
            parent_disk=node.get("_parent_disk") or node.get("pkname"),
            part_type=parttype,
            filesystem=fstype,
            label=node.get("label") or blkid_map.get(device, {}).get("LABEL"),
            uuid=node.get("uuid") or blkid_map.get(device, {}).get("UUID"),
            size_bytes=int(node["size"]) if str(node.get("size", "")).isdigit() else None,
            mountpoint=_mountpoint(node.get("mountpoints") or node.get("mountpoint")),
            partuuid=node.get("partuuid") or blkid_map.get(device, {}).get("PARTUUID"),
            boot="boot" in flags,
            esp=esp,
        )
        snapshot.partitions.append(partition)
        if node.get("type") == "disk":
            snapshot.disks.append({
                "device": device,
                "size_bytes": partition.size_bytes,
                "model": node.get("model"),
                "serial": node.get("serial"),
            })

    snapshot.efi_entries = efi.collect(runner)
    snapshot.capabilities = {
        name: runner.available(name)
        for name in ("lsblk", "blkid", "btrfs", "efibootmgr")
    }
    snapshot.warnings = [
        f"Missing command: {name}"
        for name, available in snapshot.capabilities.items()
        if not available
    ]

    esp_parts = [p for p in snapshot.partitions if p.esp]
    unique_efi_device = esp_parts[0].device if len(esp_parts) == 1 else None

    # Identify Linux roots from actual filesystem evidence. This works for both
    # already-mounted installations and unmounted installations in a Live USB.
    result = probe.probe_linux(snapshot.partitions, snapshot.firmware_mode, unique_efi_device)
    seen_linux_devices: set[str] = set()
    for system in result.operating_systems:
        if system.root_device and system.root_device not in seen_linux_devices:
            snapshot.operating_systems.append(system)
            seen_linux_devices.add(system.root_device)
    snapshot.warnings.extend(result.warnings)

    # Probe every discovered ESP for the actual Microsoft loader. Multiple ESPs
    # remain ambiguous for repair, but their evidence is still useful.
    windows_found = False
    for esp in esp_parts:
        windows_probe = probe.probe_windows_efi(esp, snapshot.firmware_mode)
        for system in windows_probe.operating_systems:
            if not any(item.family.lower() == "windows" for item in snapshot.operating_systems):
                snapshot.operating_systems.append(system)
                windows_found = True
        snapshot.warnings.extend(windows_probe.warnings)

    # Firmware entries provide additional Windows evidence if the ESP cannot
    # currently be inspected.
    windows_entry_names = tuple(
        entry.label for entry in snapshot.efi_entries if "windows" in entry.label.lower()
    )
    if windows_entry_names and not windows_found and not any(
        item.family.lower() == "windows" for item in snapshot.operating_systems
    ):
        snapshot.operating_systems.append(
            OperatingSystem(
                os_id="windows-efi-entry",
                name="Windows Boot Manager",
                family="windows",
                efi_device=unique_efi_device,
                firmware_mode=snapshot.firmware_mode,
                bootloaders=windows_entry_names,
                confidence="medium",
            )
        )

    return snapshot
