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
