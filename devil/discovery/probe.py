"""Read-only filesystem probes for Live USB discovery.

Probes mount candidate filesystems read-only in a temporary directory, inspect
small well-known metadata files, and always attempt cleanup. No filesystem is
formatted, activated, or modified by this module.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from devil.models.discovery import OperatingSystem, Partition


@dataclass(frozen=True)
class ProbeResult:
    operating_systems: tuple[OperatingSystem, ...] = ()
    warnings: tuple[str, ...] = ()


class ReadOnlyFilesystemProbe:
    def __init__(self) -> None:
        self._mount = shutil.which("mount")
        self._umount = shutil.which("umount")

    def probe_linux(self, partitions: list[Partition], firmware_mode: str, esp_device: str | None) -> ProbeResult:
        if not self._mount or not self._umount:
            return ProbeResult(warnings=("Filesystem probing skipped: mount/umount unavailable",))
        if os.geteuid() != 0:
            return ProbeResult(warnings=("Filesystem probing skipped: root privileges are required for safe read-only mounts",))

        found: list[OperatingSystem] = []
        warnings: list[str] = []
        for part in partitions:
            if part.mountpoint or part.filesystem not in {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs"}:
                continue
            with self._mounted(part.device, part.filesystem) as (root, error):
                if error:
                    warnings.append(f"Could not probe {part.device}: {error}")
                    continue
                os_release = self._read_os_release(root)
                if not os_release:
                    continue
                if not self._looks_like_linux(os_release):
                    continue
                os_id_value = os_release.get("ID", "linux").lower()
                name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Linux"
                root_subvolume = self._btrfs_root_subvolume(root, part.filesystem)
                boot_device = part.device if (root / "boot").is_dir() else None
                found.append(
                    OperatingSystem(
                        os_id=f"probe-{os_id_value}-{part.uuid or part.device}",
                        name=name,
                        family="linux",
                        root_device=part.device,
                        root_mountpoint=None,
                        root_subvolume=root_subvolume,
                        boot_device=boot_device,
                        efi_device=esp_device,
                        firmware_mode=firmware_mode,
                        confidence="high",
                    )
                )
        return ProbeResult(tuple(found), tuple(warnings))

    def probe_windows_efi(self, esp: Partition | None, firmware_mode: str) -> ProbeResult:
        if esp is None:
            return ProbeResult()
        if not self._mount or not self._umount:
            return ProbeResult(warnings=("Windows EFI probing skipped: mount/umount unavailable",))
        if os.geteuid() != 0:
            return ProbeResult(warnings=("Windows EFI probing skipped: root privileges are required for safe read-only mounts",))
        with self._mounted(esp.device, esp.filesystem or "vfat") as (root, error):
            if error:
                return ProbeResult(warnings=(f"Could not probe EFI System Partition {esp.device}: {error}",))
            loader = root / "EFI" / "Microsoft" / "Boot" / "bootmgfw.efi"
            if not loader.is_file():
                return ProbeResult()
            return ProbeResult(
                operating_systems=(
                    OperatingSystem(
                        os_id="windows-efi",
                        name="Windows Boot Manager",
                        family="windows",
                        efi_device=esp.device,
                        firmware_mode=firmware_mode,
                        bootloaders=(r"EFI\Microsoft\Boot\bootmgfw.efi",),
                        confidence="high",
                    ),
                )
            )

    class _MountContext:
        def __init__(self, owner: "ReadOnlyFilesystemProbe", device: str, filesystem: str) -> None:
            self.owner = owner
            self.device = device
            self.filesystem = filesystem
            self.path: Path | None = None
            self.error: str | None = None

        def __enter__(self) -> tuple[Path | None, str | None]:
            self.path = Path(tempfile.mkdtemp(prefix="devil-probe-"))
            options = "ro,nosuid,nodev,noexec"
            result = subprocess.run(
                [self.owner._mount, "-o", options, self.device, str(self.path)],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            if result.returncode != 0:
                self.error = result.stderr.strip() or result.stdout.strip() or "mount failed"
                self._remove_temp()
                return None, self.error
            return self.path, None

        def __exit__(self, exc_type, exc, tb) -> None:
            if self.path:
                result = subprocess.run(
                    [self.owner._umount, "-R", str(self.path)],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                if result.returncode != 0:
                    subprocess.run(
                        [self.owner._umount, str(self.path)],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=30,
                    )
            self._remove_temp()

        def _remove_temp(self) -> None:
            if self.path:
                try:
                    self.path.rmdir()
                except OSError:
                    pass
                self.path = None

    def _mounted(self, device: str, filesystem: str) -> _MountContext:
        return self._MountContext(self, device, filesystem)

    @staticmethod
    def _read_os_release(root: Path) -> dict[str, str]:
        path = root / "etc" / "os-release"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
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

    @staticmethod
    def _looks_like_linux(os_release: dict[str, str]) -> bool:
        value = (os_release.get("ID") or "").lower()
        return bool(value) and value not in {"windows", "freebsd", "openbsd", "netbsd"}

    @staticmethod
    def _btrfs_root_subvolume(root: Path, filesystem: str | None) -> str | None:
        if (filesystem or "").lower() != "btrfs":
            return None
        marker = root / ".btrfs_subvolume"
        if marker.is_file():
            try:
                value = marker.read_text(encoding="utf-8", errors="replace").strip()
                if value and re.fullmatch(r"[A-Za-z0-9_.@/-]+", value):
                    return value
            except OSError:
                pass
        return "@" if (root / "@").is_dir() else None
