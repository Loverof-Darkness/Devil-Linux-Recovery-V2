from __future__ import annotations

from devil.discovery.commands import CommandResult, CommandRunner
from devil.discovery import efi
from devil.discovery.scanner import scan
from devil.models.discovery import DiscoverySnapshot


class FakeRunner(CommandRunner):
    def __init__(self, outputs: dict[str, tuple[int, str, str]]) -> None:
        super().__init__(allow=set(outputs))
        self.outputs = outputs

    def available(self, command: str) -> bool:
        return command in self.outputs

    def run(self, command: str, *args: str, timeout: int = 15) -> CommandResult:
        rc, stdout, stderr = self.outputs.get(command, (127, "", "missing"))
        return CommandResult(rc, stdout, stderr)


def test_efi_parser_extracts_entries() -> None:
    runner = FakeRunner({
        "efibootmgr": (0, "Boot0000* ubuntu\tHD(1,GPT,abc)/File(\\EFI\\ubuntu\\shimx64.efi)\nBoot0001  Windows Boot Manager\tHD(1,GPT,abc)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)\n", "")
    })
    entries = efi.collect(runner)
    assert entries[0].boot_number == "0000"
    assert entries[0].label == "ubuntu"
    assert entries[0].active is True
    assert "Windows Boot Manager" in entries[1].label


def test_scan_builds_linux_and_windows_candidates(monkeypatch) -> None:
    import devil.discovery.scanner as scanner

    monkeypatch.setattr(scanner.firmware, "detect_firmware", lambda: "uefi")
    runner = FakeRunner({
        "lsblk": (0, '{"blockdevices": [{"name":"nvme0n1","path":"/dev/nvme0n1","type":"disk","size":1000,"children":[{"name":"nvme0n1p1","path":"/dev/nvme0n1p1","type":"part","fstype":"vfat","parttype":"c12a7328-f81f-11d2-ba4b-00a0c93ec93b","size":512},{"name":"nvme0n1p2","path":"/dev/nvme0n1p2","type":"part","fstype":"ext4","label":"Ubuntu","mountpoints":["/mnt/ubuntu"],"size":900}]}]}', ""),
        "blkid": (0, 'DEVNAME=/dev/nvme0n1p1\nTYPE=vfat\n\nDEVNAME=/dev/nvme0n1p2\nTYPE=ext4\nLABEL=Ubuntu\n\n', ""),
        "efibootmgr": (0, 'Boot0000* ubuntu\tHD(1,GPT,abc)/File(\\EFI\\ubuntu\\shimx64.efi)\nBoot0001  Windows Boot Manager\tHD(1,GPT,abc)/File(\\EFI\\Microsoft\\Boot\\bootmgfw.efi)\n', ""),
        "btrfs": (127, "", "missing"),
    })

    snapshot = scan(runner)
    assert isinstance(snapshot, DiscoverySnapshot)
    assert snapshot.firmware_mode == "uefi"
    assert any(item.name == "Ubuntu" for item in snapshot.operating_systems)
    assert any(item.family == "windows" for item in snapshot.operating_systems)
    assert any(item.esp for item in snapshot.partitions)
