from pathlib import Path

from devil.discovery.probe import ReadOnlyFilesystemProbe


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
