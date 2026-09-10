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

    def probe_linux(
        self,
        partitions: list[Partition],
        firmware_mode: str,
        esp_device: str | None,
    ) -> ProbeResult:
        found: list[OperatingSystem] = []
        warnings: list[str] = []
        supported = {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs"}

        for part in partitions:
            filesystem = (part.filesystem or "").lower()
            if filesystem not in supported:
                continue

            # An already-mounted filesystem must never be remounted by the
            # discovery path. Inspect its existing mountpoint read-only instead.
            if part.mountpoint:
                os_release = self._read_os_release(Path(part.mountpoint))
                system = self._system_from_os_release(
                    part, os_release, firmware_mode, esp_device, root_mountpoint=part.mountpoint
                )
                if system is not None:
                    found.append(system)
                continue

            if not self._mount or not self._umount:
                continue
            if os.geteuid() != 0:
                warnings.append(
                    f"Could not probe {part.device}: root privileges are required for safe read-only mounts"
                )
                continue

            with self._mounted(part.device, filesystem) as (root, error):
                if error or root is None:
                    warnings.append(f"Could not probe {part.device}: {error}")
                    continue
                os_release = self._read_os_release(root)
                system = self._system_from_os_release(
                    part, os_release, firmware_mode, esp_device, root_mountpoint=None, root=root
                )
                if system is not None:
                    found.append(system)
        return ProbeResult(tuple(found), tuple(warnings))

    @staticmethod
    def _system_from_os_release(
        part: Partition,
        os_release: dict[str, str],
        firmware_mode: str,
        esp_device: str | None,
        *,
        root_mountpoint: str | None,
        root: Path | None = None,
    ) -> OperatingSystem | None:
        if not os_release or not ReadOnlyFilesystemProbe._looks_like_linux(os_release):
            return None
        os_id_value = os_release.get("ID", "linux").lower()
        name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Linux"
        root_subvolume = ReadOnlyFilesystemProbe._btrfs_root_subvolume(root, part.filesystem) if root else None
        return OperatingSystem(
            os_id=f"probe-{os_id_value}-{part.uuid or part.device}",
            name=name,
            family="linux",
            root_device=part.device,
            root_mountpoint=root_mountpoint,
            root_subvolume=root_subvolume,
            efi_device=esp_device,
            firmware_mode=firmware_mode,
            confidence="high",
        )

    def probe_windows_efi(self, esp: Partition | None, firmware_mode: str) -> ProbeResult:
        if esp is None:
            return ProbeResult()

        if esp.mountpoint:
            return self._identify_windows_loader(Path(esp.mountpoint), esp, firmware_mode)

        if not self._mount or not self._umount:
            return ProbeResult(warnings=("Windows EFI probing skipped: mount/umount unavailable",))
        if os.geteuid() != 0:
            return ProbeResult(
                warnings=(
                    "Windows EFI probing skipped: root privileges are required for safe read-only mounts",
                )
            )

        with self._mounted(esp.device, esp.filesystem or "vfat") as (root, error):
            if error or root is None:
                return ProbeResult(warnings=(f"Could not probe EFI System Partition {esp.device}: {error}",))
            return self._identify_windows_loader(root, esp, firmware_mode)

    @staticmethod
    def _identify_windows_loader(root: Path, esp: Partition, firmware_mode: str) -> ProbeResult:
        loader = root / "EFI" / "Microsoft" / "Boot" / "bootmgfw.efi"
        try:
            exists = loader.is_file()
        except (OSError, PermissionError) as exc:
            return ProbeResult(
                warnings=(
                    f"Could not inspect Windows loader on {esp.device}: {exc}",
                )
            )
        if not exists:
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
            command = [self.owner._mount, "-o", options]
            if self.filesystem:
                command.extend(["-t", self.filesystem])
            command.extend([self.device, str(self.path)])
            result = subprocess.run(
                command,
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
    def _btrfs_root_subvolume(root: Path | None, filesystem: str | None) -> str | None:
        if root is None or (filesystem or "").lower() != "btrfs":
            return None
        try:
            mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        target = str(root).replace(" ", r"\040").replace("\t", r"\011")
        for line in mountinfo.splitlines():
            fields = line.split(" ")
            if len(fields) < 7 or fields[4] != target or " - " not in line:
                continue
            suffix = line.split(" - ", 1)[1]
            match = re.search(r"(?:^|,)subvol=([^, ]+)", suffix)
            if match:
                value = match.group(1)
                return value if re.fullmatch(r"[A-Za-z0-9_.@/+:-]+", value) else None
        return None
