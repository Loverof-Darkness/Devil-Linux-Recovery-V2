"""Conservative OS identification helpers compatible with the V2 model."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable

from devil.models.discovery import OperatingSystem

OS_RELEASE_PATH = "etc/os-release"
_LINUX_FS = {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "bcachefs", "zfs"}


def _read_os_release(root: str) -> dict[str, str]:
    path = Path(root) / OS_RELEASE_PATH
    data: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key] = value.strip().strip('"').strip("'")
    except (OSError, UnicodeError):
        return {}
    return data


def _linux_name(os_release: dict[str, str]) -> str:
    return os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Linux"


def _is_linux_partition(item: dict[str, Any]) -> bool:
    fs = str(item.get("fstype") or "").lower()
    return fs in _LINUX_FS or fs.startswith("linux")


def _walk(entries: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for item in entries:
        yield item
        children = item.get("children") or []
        if isinstance(children, list):
            yield from _walk(children)


def detect_from_mounts(partitions: Iterable[dict[str, Any]]) -> list[OperatingSystem]:
    """Identify mounted Linux installations without mounting anything."""
    found: list[OperatingSystem] = []
    for item in _walk(partitions):
        mountpoints = item.get("mountpoints") or []
        if not isinstance(mountpoints, list):
            mountpoints = [mountpoints]
        root_mounts = [str(m) for m in mountpoints if m == "/" or str(m).startswith("/mnt/")]
        if not root_mounts or not _is_linux_partition(item):
            continue
        root = root_mounts[0]
        osr = _read_os_release(root)
        found.append(
            OperatingSystem(
                os_id=f"mounted-{item.get('path') or item.get('name')}",
                name=_linux_name(osr),
                family="linux",
                root_device=item.get("path") or item.get("name"),
                root_mountpoint=root,
                firmware_mode=None,
                confidence="high" if osr else "medium",
            )
        )
    return found


def detect_windows_efi(efi_filesystems: Iterable[dict[str, Any]]) -> list[OperatingSystem]:
    """Recognize Windows from an existing EFI filesystem listing."""
    result: list[OperatingSystem] = []
    for item in efi_filesystems:
        loader = str(item.get("loader_path") or "")
        if re.search(r"Microsoft/Boot/bootmgfw\.efi$", loader, re.IGNORECASE):
            result.append(
                OperatingSystem(
                    os_id=f"windows-{item.get('device')}",
                    name="Windows Boot Manager",
                    family="windows",
                    efi_device=item.get("device"),
                    firmware_mode="uefi",
                    bootloaders=(loader,),
                    confidence="high",
                )
            )
    return result
