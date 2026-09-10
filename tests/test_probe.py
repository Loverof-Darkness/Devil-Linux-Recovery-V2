from pathlib import Path

from devil.discovery.probe import ReadOnlyFilesystemProbe
from devil.models.discovery import Partition


def test_read_os_release_parser(tmp_path: Path):
    etc = tmp_path / "etc"
    etc.mkdir()
    (etc / "os-release").write_text(
        'ID=ubuntu\nNAME="Ubuntu"\nPRETTY_NAME="Ubuntu 24.04 LTS"\n',
        encoding="utf-8",
    )
    data = ReadOnlyFilesystemProbe._read_os_release(tmp_path)
    assert data["ID"] == "ubuntu"
    assert data["PRETTY_NAME"] == "Ubuntu 24.04 LTS"


def test_linux_os_release_detection():
    assert ReadOnlyFilesystemProbe._looks_like_linux({"ID": "garuda"}) is True
    assert ReadOnlyFilesystemProbe._looks_like_linux({"ID": "windows"}) is False


def test_probe_linux_uses_existing_mountpoint_without_mounting(tmp_path: Path):
    root = tmp_path / "linux-root"
    (root / "etc").mkdir(parents=True)
    (root / "etc" / "os-release").write_text(
        'ID=garuda\nPRETTY_NAME="Garuda Linux"\n',
        encoding="utf-8",
    )
    probe = ReadOnlyFilesystemProbe()
    part = Partition(device="/dev/sda5", filesystem="btrfs", mountpoint=str(root))
    result = probe.probe_linux([part], "uefi", "/dev/sda1")
    assert len(result.operating_systems) == 1
    system = result.operating_systems[0]
    assert system.name == "Garuda Linux"
    assert system.root_device == "/dev/sda5"
    assert system.root_mountpoint == str(root)


def test_probe_linux_ignores_mounted_data_directory(tmp_path: Path):
    data = tmp_path / "var-tmp"
    data.mkdir()
    probe = ReadOnlyFilesystemProbe()
    part = Partition(device="/dev/sdb1", filesystem="ext4", mountpoint=str(data))
    result = probe.probe_linux([part], "uefi", "/dev/sda1")
    assert result.operating_systems == ()
