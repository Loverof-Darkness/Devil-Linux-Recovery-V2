"""Guarded executor for the first real DEVIL repair workflow.

The executor is deliberately narrow: UEFI + GRUB only, a previously resolved
safe target, explicit confirmation, and transactional cleanup. It never
formats partitions, deletes EFI files, edits Windows loaders, or uses a shell.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence

from devil.planning.repair import RepairPlan


class RecoveryError(RuntimeError):
    """Raised when a guarded recovery operation cannot safely continue."""


@dataclass
class RepairReport:
    started_at: str
    finished_at: str | None = None
    target_os: str = ""
    success: bool = False
    steps: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, step: str, status: str, detail: str = "") -> None:
        self.steps.append({"step": step, "status": status, "detail": detail})

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


CommandFn = Callable[[Sequence[str], Path | None], subprocess.CompletedProcess[str]]


class RecoveryExecutor:
    """Execute only the supported UEFI repair plan after explicit confirmation."""

    def __init__(self, command: CommandFn | None = None) -> None:
        self._command = command or self._run
        self._mounted: list[Path] = []
        self._temp_root: Path | None = None
        self._efi_before = ""

    @staticmethod
    def _run(argv: Sequence[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def execute(
        self,
        plan: RepairPlan,
        *,
        confirmation: str = "",
        report_path: str | None = None,
    ) -> RepairReport:
        self._validate(plan, confirmation)
        started = datetime.now(timezone.utc).isoformat()
        report = RepairReport(started_at=started, target_os=plan.target.os_name)
        try:
            self._require_tools()
            self._capture_state(report)
            self._mount_target(plan, report)
            self._backup_efi(report)
            self._install_grub(report)
            self._promote_boot_order(report)
            self._regenerate_config(report)
            self._verify(report)
            report.success = True
        except Exception as exc:
            report.add("recovery", "failed", str(exc))
            report.warnings.append("Repair stopped at first failure; inspect the report before retrying.")
            report.warnings.append("Existing EFI files are preserved; no Windows loader deletion is attempted.")
        finally:
            self._cleanup(report)
            report.finished_at = datetime.now(timezone.utc).isoformat()
            if report_path:
                Path(report_path).write_text(
                    json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8"
                )
        return report

    def _validate(self, plan: RepairPlan, confirmation: str) -> None:
        if not plan.supported or not plan.safe_to_execute:
            raise RecoveryError("repair plan is blocked and cannot be executed")
        if plan.target.firmware_mode.lower() != "uefi":
            raise RecoveryError("only UEFI recovery is currently executable")
        if not plan.target.root_device or not plan.target.efi_device:
            raise RecoveryError("target root and EFI devices are required")
        if not plan.target.efi_device.startswith("/dev/") or not plan.target.root_device.startswith("/dev/"):
            raise RecoveryError("target devices must be absolute /dev paths")
        if os.geteuid() != 0:
            raise RecoveryError("recovery execution requires root privileges")
        if confirmation.strip() != "REPAIR":
            raise RecoveryError("explicit confirmation token REPAIR is required")

    def _require_tools(self) -> None:
        required = ("mount", "umount", "chroot", "efibootmgr", "tar")
        missing = [tool for tool in required if shutil.which(tool) is None]
        if missing:
            raise RecoveryError("missing required host tools: " + ", ".join(missing))

    def _capture_state(self, report: RepairReport) -> None:
        result = self._command(("efibootmgr", "--verbose"), None)
        if result.returncode != 0:
            raise RecoveryError(f"efibootmgr pre-check failed: {result.stderr.strip()}")
        self._efi_before = result.stdout
        report.add("capture-state", "ok", "captured current EFI variables")

    def _mount_target(self, plan: RepairPlan, report: RepairReport) -> None:
        self._temp_root = Path(tempfile.mkdtemp(prefix="devil-recovery-"))
        root = self._temp_root / "root"
        root.mkdir()

        if plan.target.root_filesystem and plan.target.root_filesystem.lower() == "btrfs" and plan.target.root_subvolume:
            root_options = f"rw,subvol={plan.target.root_subvolume}"
        else:
            root_options = "rw"
        self._run_checked(
            ("mount", "-o", root_options, plan.target.root_device, str(root)),
            "mount Linux root",
        )
        self._mounted.append(root)

        boot_target = root / "boot"
        boot_target.mkdir(exist_ok=True)
        if plan.target.boot_device:
            self._run_checked(
                ("mount", "-o", "rw", plan.target.boot_device, str(boot_target)),
                "mount /boot",
            )
            self._mounted.append(boot_target)

        efi_target = boot_target / "efi"
        efi_target.mkdir(exist_ok=True)
        self._run_checked(
            ("mount", "-o", "rw", plan.target.efi_device, str(efi_target)),
            "mount EFI System Partition",
        )
        self._mounted.append(efi_target)

        for directory in ("/dev", "/dev/pts", "/proc", "/sys", "/run"):
            destination = root / directory.lstrip("/")
            destination.mkdir(parents=True, exist_ok=True)
            self._run_checked(
                ("mount", "--rbind", directory, str(destination)),
                f"bind {directory}",
            )
            self._run_checked(
                ("mount", "--make-rslave", str(destination)),
                f"isolate {directory}",
            )
            self._mounted.append(destination)
        report.add("mount-target", "ok", f"mounted target under {root}")

    def _backup_efi(self, report: RepairReport) -> None:
        assert self._temp_root is not None
        backup = (
            self._temp_root
            / "root"
            / "var"
            / "lib"
            / "devil"
            / "backups"
            / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        )
        backup.mkdir(parents=True, exist_ok=True)
        efi = self._temp_root / "root" / "boot" / "efi"
        archive = backup / "efi-tree.tar"
        result = self._command(("tar", "-cpf", str(archive), "-C", str(efi), "."), None)
        if result.returncode != 0:
            raise RecoveryError(f"EFI backup failed: {result.stderr.strip()}")
        report.add("backup-efi", "ok", str(archive))

    def _install_grub(self, report: RepairReport) -> None:
        assert self._temp_root is not None
        root = self._temp_root / "root"
        for inside_path in ("/usr/sbin/grub-install", "/usr/bin/grub-install"):
            if not self._inside_exists(root, inside_path):
                continue
            result = self._command(
                (
                    "chroot",
                    str(root),
                    inside_path,
                    "--target=x86_64-efi",
                    "--efi-directory=/boot/efi",
                    "--bootloader-id=DEVIL-GRUB",
                    "--recheck",
                ),
                None,
            )
            if result.returncode == 0:
                report.add("install-grub", "ok", f"installed UEFI loader DEVIL-GRUB via {inside_path}")
                return
            detail = result.stderr.strip() or result.stdout.strip()
            raise RecoveryError(f"GRUB installation failed: {detail}")
        raise RecoveryError("target installation does not contain grub-install")

    def _promote_boot_order(self, report: RepairReport) -> None:
        result = self._command(("efibootmgr", "--verbose"), None)
        if result.returncode != 0:
            raise RecoveryError(f"EFI entry read failed after GRUB installation: {result.stderr.strip()}")
        match = re.search(r"^Boot([0-9A-Fa-f]{4})[ *]+DEVIL-GRUB(?:\s|$)", result.stdout, re.MULTILINE | re.IGNORECASE)
        if not match:
            raise RecoveryError("DEVIL-GRUB EFI entry was not found after installation")
        devil_number = match.group(1).upper()
        order_match = re.search(r"^BootOrder:\s*([0-9A-Fa-f,]+)", result.stdout, re.MULTILINE)
        if not order_match:
            raise RecoveryError("firmware BootOrder was not reported")
        current = [item.upper() for item in order_match.group(1).split(",") if item]
        new_order = [devil_number] + [item for item in current if item != devil_number]
        if current == new_order:
            report.add("promote-bootorder", "ok", f"DEVIL-GRUB {devil_number} was already first")
            return
        set_result = self._command(("efibootmgr", "-o", ",".join(new_order)), None)
        if set_result.returncode != 0:
            raise RecoveryError(f"BootOrder update failed: {set_result.stderr.strip()}")
        report.add("promote-bootorder", "ok", f"BootOrder set to {','.join(new_order)}")

    def _regenerate_config(self, report: RepairReport) -> None:
        assert self._temp_root is not None
        root = self._temp_root / "root"
        candidates = (
            "/usr/sbin/update-grub",
            "/usr/bin/update-grub",
            "/usr/sbin/grub-mkconfig",
            "/usr/bin/grub-mkconfig",
            "/usr/sbin/grub2-mkconfig",
            "/usr/bin/grub2-mkconfig",
        )
        for inside_path in candidates:
            if not self._inside_exists(root, inside_path):
                continue
            if inside_path.endswith("update-grub"):
                argv = ("chroot", str(root), inside_path)
            elif "grub2-mkconfig" in inside_path:
                argv = ("chroot", str(root), inside_path, "-o", "/boot/grub2/grub.cfg")
            else:
                argv = ("chroot", str(root), inside_path, "-o", "/boot/grub/grub.cfg")
            result = self._command(argv, None)
            if result.returncode == 0:
                report.add("regenerate-config", "ok", inside_path)
                return
            detail = result.stderr.strip() or result.stdout.strip()
            raise RecoveryError(f"GRUB configuration generation failed: {detail}")
        raise RecoveryError("target installation does not contain a GRUB configuration generator")

    def _verify(self, report: RepairReport) -> None:
        after = self._command(("efibootmgr", "--verbose"), None)
        if after.returncode != 0:
            raise RecoveryError("EFI verification failed")
        lower = after.stdout.lower()
        if "devil-grub" not in lower:
            raise RecoveryError("new DEVIL-GRUB EFI entry was not observed")
        if "windows boot manager" in self._efi_before.lower() and "windows boot manager" not in lower:
            raise RecoveryError("Windows Boot Manager disappeared during repair")
        order_match = re.search(r"^BootOrder:\s*([0-9A-Fa-f,]+)", after.stdout, re.MULTILINE)
        devil_match = re.search(r"^Boot([0-9A-Fa-f]{4})[ *]+DEVIL-GRUB(?:\s|$)", after.stdout, re.MULTILINE | re.IGNORECASE)
        if not order_match or not devil_match or order_match.group(1).split(",")[0].upper() != devil_match.group(1).upper():
            raise RecoveryError("DEVIL-GRUB is not first in firmware BootOrder after repair")
        report.add(
            "verify-efi",
            "ok",
            "DEVIL-GRUB present and first in BootOrder; pre-existing Windows entry preserved when detected",
        )

    @staticmethod
    def _inside_exists(root: Path, path: str) -> bool:
        return (root / path.lstrip("/")).exists()

    def _run_checked(self, argv: Sequence[str], label: str) -> None:
        result = self._command(argv, None)
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RecoveryError(f"{label} failed: {detail}")

    def _cleanup(self, report: RepairReport) -> None:
        for mountpoint in reversed(self._mounted):
            result = self._command(("umount", "-R", str(mountpoint)), None)
            if result.returncode != 0:
                result = self._command(("umount", str(mountpoint)), None)
                if result.returncode != 0:
                    report.warnings.append(
                        f"Could not unmount {mountpoint}: {result.stderr.strip()}"
                    )
        self._mounted.clear()
        if self._temp_root:
            try:
                shutil.rmtree(self._temp_root)
            except OSError as exc:
                report.warnings.append(
                    f"Could not remove temporary directory {self._temp_root}: {exc}"
                )
            self._temp_root = None
