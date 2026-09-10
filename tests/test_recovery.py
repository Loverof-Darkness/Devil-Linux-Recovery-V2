from pathlib import Path

import pytest

from devil.planning.repair import build_repair_plan
from devil.planning.target import TargetLayout
from devil.recovery.executor import RecoveryError, RecoveryExecutor


def supported_plan():
    target = TargetLayout(
        os_id="linux-1",
        os_name="Test Linux",
        root_device="/dev/sda2",
        root_filesystem="ext4",
        root_mountpoint=None,
        root_subvolume=None,
        boot_device=None,
        efi_device="/dev/sda1",
        firmware_mode="uefi",
        safe=True,
    )
    return build_repair_plan(target)


def test_executor_rejects_missing_confirmation(monkeypatch):
    monkeypatch.setattr("devil.recovery.executor.os.geteuid", lambda: 0)
    with pytest.raises(RecoveryError, match="confirmation"):
        RecoveryExecutor().execute(supported_plan())


def test_executor_rejects_non_dev_targets(monkeypatch):
    monkeypatch.setattr("devil.recovery.executor.os.geteuid", lambda: 0)
    target = TargetLayout(
        os_id="linux-1",
        os_name="Test Linux",
        root_device="sda2",
        root_filesystem="ext4",
        root_mountpoint=None,
        root_subvolume=None,
        boot_device=None,
        efi_device="/dev/sda1",
        firmware_mode="uefi",
        safe=True,
    )
    with pytest.raises(RecoveryError, match="absolute /dev"):
        RecoveryExecutor().execute(build_repair_plan(target), confirmation="REPAIR")


def test_recovery_plan_contains_bootorder_step():
    plan = supported_plan()
    assert any(step.step_id == "promote-bootorder" for step in plan.steps)


def test_btrfs_mount_uses_resolved_root_subvolume(tmp_path: Path, monkeypatch):
    target = TargetLayout(
        os_id="garuda",
        os_name="Garuda Linux",
        root_device="/dev/sda5",
        root_filesystem="btrfs",
        root_mountpoint="/",
        root_subvolume="@",
        boot_device=None,
        efi_device="/dev/sda1",
        firmware_mode="uefi",
        safe=True,
    )
    plan = build_repair_plan(target)
    executor = RecoveryExecutor()
    transaction = tmp_path / "transaction"
    transaction.mkdir()
    monkeypatch.setattr("devil.recovery.executor.tempfile.mkdtemp", lambda prefix: str(transaction))

    commands: list[tuple[str, ...]] = []

    def capture(argv, label):
        commands.append(tuple(argv))

    monkeypatch.setattr(executor, "_run_checked", capture)
    executor._mount_target(plan, type("Report", (), {"add": lambda *args: None})())

    root_mount = next(command for command in commands if command[0] == "mount" and "/dev/sda5" in command)
    assert root_mount == (
        "mount",
        "-o",
        "rw,subvol=@",
        "/dev/sda5",
        str(transaction / "root"),
    )
