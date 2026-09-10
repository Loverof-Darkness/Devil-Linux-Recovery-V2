from dataclasses import replace

from devil.models.discovery import DiscoverySnapshot, OperatingSystem, Partition
from devil.planning.repair import build_repair_plan, render_repair_plan


def safe_target_snapshot() -> DiscoverySnapshot:
    return DiscoverySnapshot(
        firmware_mode="uefi",
        partitions=[
            Partition(device="/dev/sda1", filesystem="vfat", esp=True),
            Partition(device="/dev/sda2", filesystem="ext4", mountpoint="/mnt/linux"),
        ],
        operating_systems=[
            OperatingSystem(
                os_id="linux-1",
                name="Ubuntu",
                family="linux",
                root_device="/dev/sda2",
                root_mountpoint="/mnt/linux",
                efi_device="/dev/sda1",
                firmware_mode="uefi",
                confidence="high",
            )
        ],
    )


def test_build_repair_plan_has_guarded_steps():
    from devil.planning.target import resolve_target

    target = resolve_target(safe_target_snapshot(), "linux-1")
    plan = build_repair_plan(target)
    assert plan.supported is True
    assert plan.safe_to_execute is True
    assert plan.steps[0].step_id == "capture-state"
    assert any(step.step_id == "install-grub" and step.risk == "HIGH" for step in plan.steps)
    assert any(step.step_id == "promote-bootorder" and step.risk == "HIGH" for step in plan.steps)
    assert plan.steps[-1].mutates_system is False


def test_build_repair_plan_blocks_unsafe_target():
    from devil.planning.target import resolve_target

    snapshot = safe_target_snapshot()
    snapshot.operating_systems[0] = replace(snapshot.operating_systems[0], efi_device=None)
    snapshot.partitions.append(Partition(device="/dev/sdb1", filesystem="vfat", esp=True))
    target = resolve_target(snapshot, "linux-1")
    plan = build_repair_plan(target)
    assert plan.safe_to_execute is False
    assert plan.steps == ()
    assert any("multiple EFI" in reason for reason in plan.reasons)


def test_build_repair_plan_blocks_btrfs_without_root_subvolume():
    from devil.planning.target import resolve_target

    snapshot = safe_target_snapshot()
    snapshot.partitions[1] = replace(snapshot.partitions[1], filesystem="btrfs")
    snapshot.operating_systems[0] = replace(
        snapshot.operating_systems[0],
        root_subvolume=None,
    )
    target = resolve_target(snapshot, "linux-1")
    plan = build_repair_plan(target)
    assert plan.safe_to_execute is False
    assert plan.steps == ()
    assert any("Btrfs root subvolume" in reason for reason in plan.reasons)


def test_build_repair_plan_accepts_btrfs_with_root_subvolume():
    from devil.planning.target import resolve_target

    snapshot = safe_target_snapshot()
    snapshot.partitions[1] = replace(snapshot.partitions[1], filesystem="btrfs")
    snapshot.operating_systems[0] = replace(
        snapshot.operating_systems[0],
        root_subvolume="@",
    )
    target = resolve_target(snapshot, "linux-1")
    plan = build_repair_plan(target)
    assert plan.safe_to_execute is True
    assert plan.supported is True


def test_render_repair_plan_is_explainable():
    from devil.planning.target import resolve_target

    target = resolve_target(safe_target_snapshot(), "linux-1")
    rendered = render_repair_plan(build_repair_plan(target))
    assert "DEVIL Recovery Plan" in rendered
    assert "Install/reinstall GRUB" in rendered
    assert "HIGH" in rendered
