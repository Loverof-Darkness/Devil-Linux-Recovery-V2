from devil.models.discovery import DiscoverySnapshot, EfiEntry, OperatingSystem, Partition
from devil.planning.target import resolve_selected_linux, resolve_target


def make_snapshot(*, esp_count: int = 1) -> DiscoverySnapshot:
    partitions = [
        Partition(
            device="/dev/nvme0n1p2",
            parent_disk="/dev/nvme0n1",
            filesystem="btrfs",
            label="Garuda Linux",
            mountpoint="/mnt/garuda",
        )
    ]
    for index in range(1, esp_count + 1):
        partitions.append(
            Partition(
                device=f"/dev/nvme0n1p{index}",
                parent_disk="/dev/nvme0n1",
                filesystem="vfat",
                esp=True,
            )
        )
    return DiscoverySnapshot(
        firmware_mode="uefi",
        partitions=partitions,
        operating_systems=[
            OperatingSystem(
                os_id="linux-1",
                name="Garuda Linux",
                family="linux",
                root_device="/dev/nvme0n1p2",
                root_mountpoint="/mnt/garuda",
                efi_device=None,
                firmware_mode="uefi",
                confidence="high",
            )
        ],
        efi_entries=[EfiEntry("0000", "garuda", r"\\EFI\\garuda\\grubx64.efi")],
    )


def test_resolve_target_finds_single_esp():
    target = resolve_target(make_snapshot(), "linux-1")
    assert target.safe is True
    assert target.root_device == "/dev/nvme0n1p2"
    assert target.root_filesystem == "btrfs"
    assert target.efi_device == "/dev/nvme0n1p1"
    assert target.firmware_mode == "uefi"


def test_resolve_target_rejects_ambiguous_esp():
    target = resolve_target(make_snapshot(esp_count=2), "linux-1")
    assert target.safe is False
    assert any("multiple EFI" in reason for reason in target.reasons)


def test_resolve_target_rejects_unknown_os():
    target = resolve_target(make_snapshot(), "missing")
    assert target.safe is False
    assert target.root_device is None
    assert target.reasons == ("target operating system was not uniquely identified",)


def test_resolve_selected_linux_uses_linux_only_index():
    snapshot = make_snapshot()
    target = resolve_selected_linux(snapshot, snapshot.operating_systems, 1)
    assert target is not None
    assert target.os_id == "linux-1"
