from __future__ import annotations

from pathlib import Path
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


def _normalize_mount_source(source: str) -> str:
    """Normalize findmnt SOURCE values, including Btrfs subvolume notation."""
    source = source.strip()
    if "[" in source and source.endswith("]"):
        source = source.split("[", 1)[0]
    return source


def _source_aliases(source: str, flat: list[dict[str, Any]]) -> set[str]:
    """Return equivalent source spellings used by lsblk and findmnt."""
    normalized = _normalize_mount_source(source)
    aliases = {normalized}
    for node in flat:
        path = str(node.get("path") or node.get("name") or "")
        if not path:
            continue
        node_path = _normalize_mount_source(path)
        if node_path == normalized:
            aliases.add(path)
        if path.startswith("/dev/") and path.rsplit("/", 1)[-1] == normalized.rsplit("/", 1)[-1]:
            aliases.add(path)
    return aliases


def _collect_mountpoints(runner: CommandRunner, flat: list[dict[str, Any]]) -> dict[str, str]:
    """Return device -> mountpoint mappings from the live mount table."""
    result = runner.run("findmnt", "-rn", "-o", "SOURCE,TARGET,FSTYPE")
    if result.returncode != 0:
        return {}

    mounts: dict[str, str] = {}
    for line in result.stdout.splitlines():
        fields = line.split(None, 2)
        if len(fields) < 2:
            continue
        source = _normalize_mount_source(fields[0])
        target = fields[1]
        if not source.startswith("/") or not target.startswith("/"):
            continue
        for alias in _source_aliases(source, flat):
            mounts.setdefault(alias, target)
    return mounts


def _collect_root_mount(runner: CommandRunner) -> tuple[str, str] | None:
    """Return the physical source and filesystem for the live `/` mount."""
    result = runner.run("findmnt", "-rn", "-o", "SOURCE,FSTYPE", "/")
    if result.returncode != 0:
        return None
    fields = result.stdout.strip().split(None, 1)
    if len(fields) != 2:
        return None
    source = _normalize_mount_source(fields[0])
    filesystem = fields[1].strip().lower()
    if not source.startswith("/dev/") or filesystem not in _LINUX_FS:
        return None
    return source, filesystem


def _os_release_from_root(root: Path) -> dict[str, str]:
    try:
        text = (root / "etc" / "os-release").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"').strip("'")
    return data


def scan(runner: CommandRunner | None = None, probe: ReadOnlyFilesystemProbe | None = None) -> DiscoverySnapshot:
    runner = runner or CommandRunner()
    probe = probe or ReadOnlyFilesystemProbe()
    snapshot = DiscoverySnapshot(firmware_mode=firmware.detect_firmware())

    nodes = lsblk.collect(runner)
    blkid_map = blkid.collect(runner)
    flat = _flatten(nodes)
    live_mounts = _collect_mountpoints(runner, flat)

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
        lsblk_mountpoint = _mountpoint(node.get("mountpoints") or node.get("mountpoint"))
        mountpoint = lsblk_mountpoint or live_mounts.get(device) or live_mounts.get(_normalize_mount_source(device))
        partition = Partition(
            device=device,
            parent_disk=node.get("_parent_disk") or node.get("pkname"),
            part_type=parttype,
            filesystem=fstype,
            label=node.get("label") or blkid_map.get(device, {}).get("LABEL"),
            uuid=node.get("uuid") or blkid_map.get(device, {}).get("UUID"),
            size_bytes=int(node["size"]) if str(node.get("size", "")).isdigit() else None,
            mountpoint=mountpoint,
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

    # The live root deserves an explicit path because it is the strongest
    # available mounted-Linux signal and can be represented differently by
    # lsblk/findmnt on Btrfs systems. It is only trusted when findmnt reports
    # a physical /dev source with a known Linux filesystem.
    root_mount = _collect_root_mount(runner)
    if root_mount:
        root_device, root_filesystem = root_mount
        matching = next((p for p in snapshot.partitions if _normalize_mount_source(p.device) == root_device), None)
        if matching is None:
            snapshot.partitions.append(
                Partition(
                    device=root_device,
                    filesystem=root_filesystem,
                    mountpoint="/",
                )
            )
        elif matching.mountpoint != "/":
            snapshot.partitions = [
                Partition(
                    device=p.device,
                    parent_disk=p.parent_disk,
                    part_type=p.part_type,
                    filesystem=p.filesystem,
                    label=p.label,
                    uuid=p.uuid,
                    size_bytes=p.size_bytes,
                    mountpoint="/" if _normalize_mount_source(p.device) == root_device else p.mountpoint,
                    partuuid=p.partuuid,
                    boot=p.boot,
                    esp=p.esp,
                )
                for p in snapshot.partitions
            ]

    snapshot.efi_entries = efi.collect(runner)
    snapshot.capabilities = {
        name: runner.available(name)
        for name in ("lsblk", "blkid", "findmnt", "btrfs", "efibootmgr")
    }
    snapshot.warnings = [
        f"Missing command: {name}"
        for name, available in snapshot.capabilities.items()
        if not available
    ]

    esp_parts = [p for p in snapshot.partitions if p.esp]
    unique_efi_device = esp_parts[0].device if len(esp_parts) == 1 else None

    result = probe.probe_linux(snapshot.partitions, snapshot.firmware_mode, unique_efi_device)
    seen_linux_devices: set[str] = set()
    for system in result.operating_systems:
        if system.root_device and system.root_device not in seen_linux_devices:
            snapshot.operating_systems.append(system)
            seen_linux_devices.add(system.root_device)
    snapshot.warnings.extend(result.warnings)

    # Explicitly inspect the physical live root when it was not discovered by
    # the general partition probe. This does not mount or modify anything.
    if root_mount and not any(item.family.lower() == "linux" and item.root_mountpoint == "/" for item in snapshot.operating_systems):
        root_device, root_filesystem = root_mount
        os_release = _os_release_from_root(Path("/"))
        if os_release and ReadOnlyFilesystemProbe._looks_like_linux(os_release):
            os_id_value = os_release.get("ID", "linux").lower()
            name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Linux"
            snapshot.operating_systems.append(
                OperatingSystem(
                    os_id=f"live-root-{os_id_value}-{root_device}",
                    name=name,
                    family="linux",
                    root_device=root_device,
                    root_mountpoint="/",
                    efi_device=unique_efi_device,
                    firmware_mode=snapshot.firmware_mode,
                    confidence="high",
                )
            )

    windows_found = False
    for esp in esp_parts:
        windows_probe = probe.probe_windows_efi(esp, snapshot.firmware_mode)
        for system in windows_probe.operating_systems:
            if not any(item.family.lower() == "windows" for item in snapshot.operating_systems):
                snapshot.operating_systems.append(system)
                windows_found = True
        snapshot.warnings.extend(windows_probe.warnings)

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
