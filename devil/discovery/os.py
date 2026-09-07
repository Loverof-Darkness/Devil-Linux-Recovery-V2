"""Conservative OS identification helpers."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Iterable

from devil.models.system import OperatingSystem

OS_RELEASE_PATH = "etc/os-release"


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
    return fs in {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs"} or fs.startswith("linux")


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
        name = _linux_name(osr)
        evidence = [f"filesystem={item.get('fstype')}", f"mountpoint={root}"]
        if osr.get("ID"):
            evidence.append(f"id={osr['ID']}")
        found.append(
            OperatingSystem(
                name=name,
                family="Linux",
                root_device=item.get("path") or item.get("name"),
                root_filesystem=item.get("fstype"),
                confidence=0.98 if osr else 0.75,
                evidence=tuple(evidence),
            )
        )
    return found


def detect_windows_efi(efi_filesystems: Iterable[dict[str, Any]]) -> list[OperatingSystem]:
    """Recognize a Windows EFI loader from an existing EFI filesystem listing."""
    result: list[OperatingSystem] = []
    for item in efi_filesystems:
        loader = str(item.get("loader_path") or "")
        if re.search(r"Microsoft/Boot/bootmgfw\.efi$", loader, re.IGNORECASE):
            result.append(
                OperatingSystem(
                    name="Windows Boot Manager",
                    family="Windows",
                    efi_device=item.get("device"),
                    efi_loader=loader,
                    confidence=0.99,
                    evidence=("EFI loader: Microsoft/Boot/bootmgfw.efi",),
                )
            )
    return result
